"""
Read-only business-intelligence calculations for the admin analytics
dashboard (app/admin/routes.py's `analytics` view). Deliberately does all
aggregation in plain Python over full query results rather than complex
grouped/conditional SQL - at this business's realistic data volume (a
handful of clients, hundreds of transactions) that's simpler to get right
and easier to debug than fighting SQLAlchemy's case()/group_by syntax for
marginal performance that doesn't matter here.
"""
from collections import Counter
from datetime import datetime, timedelta

from app.models import User, PaymentRequest, GeneratedTicket, Broker
from app.clubs import get_club


def _club_display_name(slug):
    club = get_club(slug)
    return club["name"] if club else (slug or "Unknown")


def compute_overview():
    confirmed = PaymentRequest.query.filter_by(status="confirmed").all()
    total_revenue = sum(float(p.credits) for p in confirmed)
    total_credits_sold = sum(float(p.credits) for p in confirmed if p.kind == "credits")

    return {
        "total_revenue": total_revenue,
        "total_users": User.query.count(),
        "total_brokers": Broker.query.count(),
        "total_credits_sold": total_credits_sold,
        "total_topups": len(confirmed),
        "total_links_generated": GeneratedTicket.query.count(),
    }


def _build_series(rows, now, days_back=None, hours_back=None, bucket_days=None, bucket_hours=None, label_fmt="%d %b"):
    start = now - (timedelta(hours=hours_back) if hours_back else timedelta(days=days_back))
    delta = timedelta(hours=bucket_hours) if bucket_hours else timedelta(days=bucket_days)
    num_buckets = max(1, int((now - start) / delta))

    labels = []
    cursor = start
    for _ in range(num_buckets):
        labels.append(cursor.strftime(label_fmt))
        cursor += delta

    values = [0.0] * num_buckets
    for when, amount in rows:
        if when is None or when < start:
            continue
        idx = int((when - start) / delta)
        if 0 <= idx < num_buckets:
            values[idx] += float(amount)

    return {"labels": labels, "values": values}


def compute_revenue_series():
    now = datetime.utcnow()
    window_start = now - timedelta(days=365)
    rows = [
        (p.confirmed_at, p.credits)
        for p in PaymentRequest.query.filter(
            PaymentRequest.status == "confirmed", PaymentRequest.confirmed_at >= window_start
        ).all()
    ]

    return {
        "today": _build_series(rows, now, hours_back=24, bucket_hours=1, label_fmt="%H:00"),
        "7d": _build_series(rows, now, days_back=7, bucket_days=1, label_fmt="%d %b"),
        "30d": _build_series(rows, now, days_back=30, bucket_days=1, label_fmt="%d %b"),
        "3m": _build_series(rows, now, days_back=90, bucket_days=7, label_fmt="%d %b"),
        "1y": _build_series(rows, now, days_back=365, bucket_days=30, label_fmt="%b"),
    }


def compute_topup_analytics():
    confirmed = PaymentRequest.query.filter_by(status="confirmed").all()
    total_amount = sum(float(p.credits) for p in confirmed)
    count = len(confirmed)
    average = total_amount / count if count else 0.0

    package_counter = Counter(p.credits for p in confirmed if p.kind == "credits")
    most_popular = "No purchases yet"
    if package_counter:
        amount, freq = package_counter.most_common(1)[0]
        most_popular = f"{amount} credits ({freq} purchase{'s' if freq != 1 else ''})"

    now = datetime.utcnow()
    rows = [(p.confirmed_at, 1) for p in confirmed]
    series = _build_series(rows, now, days_back=30, bucket_days=1, label_fmt="%d %b")

    return {
        "total_amount": total_amount,
        "count": count,
        "average": average,
        "most_popular": most_popular,
        "series": series,
    }


def compute_user_activity():
    payments = PaymentRequest.query.filter_by(status="confirmed").all()
    tickets = GeneratedTicket.query.all()

    spent = Counter()
    credits_purchased = Counter()
    topup_count = Counter()
    last_purchase = {}

    for p in payments:
        spent[p.user_id] += float(p.credits)
        if p.kind == "credits":
            credits_purchased[p.user_id] += float(p.credits)
        topup_count[p.user_id] += 1
        when = p.confirmed_at
        if when and (p.user_id not in last_purchase or when > last_purchase[p.user_id]):
            last_purchase[p.user_id] = when

    links_generated = Counter()
    clubs_by_user = {}
    for t in tickets:
        links_generated[t.user_id] += 1
        clubs_by_user.setdefault(t.user_id, Counter())[t.club_slug] += 1

    activity = []
    for user in User.query.order_by(User.created_at.desc()).all():
        club_counter = clubs_by_user.get(user.id)
        most_club = _club_display_name(club_counter.most_common(1)[0][0]) if club_counter else "-"
        last = last_purchase.get(user.id)

        activity.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "total_spent": spent.get(user.id, 0.0),
            "credits_purchased": credits_purchased.get(user.id, 0.0),
            "topup_count": topup_count.get(user.id, 0),
            "last_purchase": last.strftime("%d %b %Y") if last else "-",
            "last_purchase_sort": last.isoformat() if last else "",
            "links_generated": links_generated.get(user.id, 0),
            "most_club": most_club,
        })

    return activity


def compute_club_analytics():
    tickets = GeneratedTicket.query.all()
    club_counter = Counter(t.club_slug for t in tickets)
    users_by_club = {}
    for t in tickets:
        users_by_club.setdefault(t.club_slug, set()).add(t.user_id)

    total = sum(club_counter.values()) or 1
    rows = []
    for slug, count in club_counter.most_common():
        rows.append({
            "slug": slug,
            "name": _club_display_name(slug),
            "links": count,
            "users": len(users_by_club.get(slug, ())),
            "percentage": round(count / total * 100, 1),
        })
    return rows


def compute_recent_transactions(limit=15):
    rows = (
        PaymentRequest.query.order_by(PaymentRequest.created_at.desc()).limit(limit).all()
    )
    out = []
    for payment in rows:
        user = User.query.get(payment.user_id)
        out.append({
            "user_name": user.name if user else "Deleted user",
            "user_email": user.email if user else "-",
            "amount": float(payment.credits),
            "kind": "Unlimited pass" if payment.kind == "unlimited_month" else "Credits",
            "date": (payment.confirmed_at or payment.created_at).strftime("%d %b %Y, %H:%M"),
            "status": payment.status,
            "provider": payment.provider,
        })
    return out


def compute_recent_link_generations(limit=15):
    rows = GeneratedTicket.query.order_by(GeneratedTicket.generated_at.desc()).limit(limit).all()
    out = []
    for ticket in rows:
        user = User.query.get(ticket.user_id)
        out.append({
            "user_name": user.name if user else "Deleted user",
            "user_email": user.email if user else "-",
            "club": _club_display_name(ticket.club_slug),
            "date": ticket.generated_at.strftime("%d %b %Y, %H:%M"),
        })
    return out
