import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, abort, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.clubs import CLUBS, get_club
from app.extensions import db, limiter
from app.models import User, RegistrationToken, CreditTransaction, Match, Broker
from app.utils.email import send_user_welcome_email
from app.admin import analytics as admin_analytics

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/")
@admin_required
def index():
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        active_nav="dashboard",
        overview=admin_analytics.compute_overview(),
        revenue_series=admin_analytics.compute_revenue_series(),
        topup=admin_analytics.compute_topup_analytics(),
        club_analytics=admin_analytics.compute_club_analytics(),
        recent_transactions=admin_analytics.compute_recent_transactions(limit=5),
        recent_links=admin_analytics.compute_recent_link_generations(limit=5),
    )


@admin_bp.route("/users")
@admin_required
def users():
    pending_users = (
        User.query.filter_by(is_approved=False).order_by(User.created_at.asc()).all()
    )
    all_users = User.query.order_by(User.created_at.desc()).all()

    return render_template(
        "admin/users.html",
        active_nav="users",
        pending_users=pending_users,
        all_users=all_users,
        user_activity=admin_analytics.compute_user_activity(),
    )


@admin_bp.route("/brokers")
@admin_required
def brokers():
    return render_template(
        "admin/brokers.html",
        active_nav="brokers",
        brokers=Broker.query.order_by(Broker.created_at.desc()).all(),
    )


@admin_bp.route("/transactions")
@admin_required
def transactions():
    return render_template(
        "admin/transactions.html",
        active_nav="transactions",
        recent_transactions=admin_analytics.compute_recent_transactions(limit=100),
    )


@admin_bp.route("/credit-sales")
@admin_required
def credit_sales():
    return render_template(
        "admin/credit_sales.html",
        active_nav="credit_sales",
        topup=admin_analytics.compute_topup_analytics(),
    )


@admin_bp.route("/club-analytics")
@admin_required
def club_analytics():
    return render_template(
        "admin/club_analytics.html",
        active_nav="club_analytics",
        club_analytics=admin_analytics.compute_club_analytics(),
    )


@admin_bp.route("/link-generations")
@admin_required
def link_generations():
    return render_template(
        "admin/link_generations.html",
        active_nav="link_generations",
        recent_links=admin_analytics.compute_recent_link_generations(limit=100),
    )


@admin_bp.route("/reports")
@admin_required
def reports():
    return render_template("admin/reports.html", active_nav="reports")


@admin_bp.route("/reports/export/<dataset>")
@limiter.limit("30 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def export_report(dataset):
    buf = io.StringIO()
    writer = csv.writer(buf)

    if dataset == "users":
        writer.writerow(["Name", "Email", "Total Spent (GBP)", "Credits Purchased", "Top-ups", "Last Purchase", "Links Generated", "Most Generated Club"])
        for row in admin_analytics.compute_user_activity():
            writer.writerow([row["name"], row["email"], row["total_spent"], row["credits_purchased"], row["topup_count"], row["last_purchase"], row["links_generated"], row["most_club"]])
    elif dataset == "transactions":
        writer.writerow(["User", "Email", "Amount (GBP)", "Product", "Date", "Status", "Provider"])
        for row in admin_analytics.compute_recent_transactions(limit=5000):
            writer.writerow([row["user_name"], row["user_email"], row["amount"], row["kind"], row["date"], row["status"], row["provider"]])
    elif dataset == "link-generations":
        writer.writerow(["User", "Email", "Club", "Date/time"])
        for row in admin_analytics.compute_recent_link_generations(limit=5000):
            writer.writerow([row["user_name"], row["user_email"], row["club"], row["date"]])
    elif dataset == "clubs":
        writer.writerow(["Club", "Links", "Percentage", "Users"])
        for row in admin_analytics.compute_club_analytics():
            writer.writerow([row["name"], row["links"], row["percentage"], row["users"]])
    else:
        abort(404)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={dataset}.csv"},
    )


@admin_bp.route("/settings")
@admin_required
def settings():
    matches = (
        Match.query.order_by(Match.club_slug.asc(), Match.kickoff_at.asc().nullslast()).all()
    )
    return render_template(
        "admin/settings.html",
        active_nav="settings",
        matches=matches,
        clubs=CLUBS,
    )


@admin_bp.route("/settings/password", methods=["POST"])
@limiter.limit("10 per hour", key_func=lambda: str(current_user.get_id()))
@admin_required
def change_password():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""

    if not check_password_hash(current_user.password_hash, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("admin.settings"))

    if len(new_password) < 8:
        flash("New password must be at least 8 characters.", "error")
        return redirect(url_for("admin.settings"))

    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash("Password updated.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def approve_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_approved:
        flash(f"{user.email} was already approved.", "error")
        return redirect(url_for("admin.users"))

    user.is_approved = True
    user.approved_at = datetime.utcnow()
    RegistrationToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": datetime.utcnow()}, synchronize_session=False
    )
    db.session.commit()

    try:
        send_user_welcome_email(user)
    except Exception as exc:  # noqa: BLE001 - approval already succeeded, don't fail the request
        current_app.logger.error("Failed to send welcome email: %s", exc)

    flash(f"Approved {user.email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/decline", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def decline_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_approved:
        flash(f"{user.email} is already approved - can't decline an active account.", "error")
        return redirect(url_for("admin.users"))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f"Declined and removed the registration request from {email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/credits", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def adjust_credits(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    try:
        delta = int(request.form.get("delta", "0"))
    except ValueError:
        delta = 0

    if delta == 0:
        flash("Enter a non-zero number of credits to adjust.", "error")
        return redirect(url_for("admin.users"))

    user.credits += delta
    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type="admin_adjustment",
            amount=delta,
            description=f"Admin {'added' if delta > 0 else 'removed'} {abs(delta)} credit(s)",
        )
    )
    db.session.commit()

    flash(
        f"{'Added' if delta > 0 else 'Removed'} {abs(delta)} credit(s) for {user.email}. "
        f"New balance: {user.credits}.",
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/unlimited", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def grant_unlimited(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    try:
        days = int(request.form.get("days", "30"))
    except ValueError:
        days = 0

    if days <= 0:
        flash("Enter a positive number of days.", "error")
        return redirect(url_for("admin.users"))

    base = user.unlimited_until if user.has_unlimited else datetime.utcnow()
    user.unlimited_until = base + timedelta(days=days)
    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type="admin_grant",
            amount=0,
            description=f"Admin granted {days} day(s) of unlimited access",
        )
    )
    db.session.commit()

    flash(
        f"Granted {days} day(s) of unlimited access to {user.email}, "
        f"now until {user.unlimited_until.strftime('%d %b %Y')}.",
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def delete_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_admin:
        flash("Can't delete an admin account here.", "error")
        return redirect(url_for("admin.users"))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f"Deleted {email} and all their data.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/matches", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def add_match():
    club_slug = (request.form.get("club_slug") or "").strip()
    away_team = (request.form.get("away_team") or "").strip()
    kickoff_raw = (request.form.get("kickoff_at") or "").strip()

    club = get_club(club_slug)
    if not club or not away_team:
        flash("Fill in the club and the opponent.", "error")
        return redirect(url_for("admin.settings"))

    # This club is always the home side here - tickets for an away fixture
    # aren't sold through this club's own automation/portal, so away
    # fixtures are never entered under a club's slug.
    home_team = club["name"]

    kickoff_at = None
    if kickoff_raw:
        try:
            kickoff_at = datetime.strptime(kickoff_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Couldn't read that kickoff date/time.", "error")
            return redirect(url_for("admin.settings"))

    db.session.add(
        Match(
            club_slug=club_slug,
            home_team=home_team,
            away_team=away_team,
            kickoff_at=kickoff_at,
            is_active=True,
        )
    )
    db.session.commit()
    flash(f"Added {home_team} v {away_team}.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/matches/<int:match_id>/toggle", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def toggle_match(match_id):
    match = db.session.query(Match).with_for_update().get(match_id)
    if not match:
        abort(404)

    match.is_active = not match.is_active
    db.session.commit()
    flash(f"{match.name} is now {'active' if match.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/brokers", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def add_broker():
    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    notes = (request.form.get("notes") or "").strip()

    if not name or not phone:
        flash("Enter a name and phone number.", "error")
        return redirect(url_for("admin.brokers"))

    db.session.add(Broker(name=name, phone=phone, notes=notes or None))
    db.session.commit()
    flash(f"Added {name}.", "success")
    return redirect(url_for("admin.brokers"))


@admin_bp.route("/brokers/<int:broker_id>/notes", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def update_broker_notes(broker_id):
    broker = db.session.query(Broker).with_for_update().get(broker_id)
    if not broker:
        abort(404)

    broker.notes = (request.form.get("notes") or "").strip() or None
    db.session.commit()
    flash(f"Updated notes for {broker.name}.", "success")
    return redirect(url_for("admin.brokers"))


@admin_bp.route("/brokers/<int:broker_id>/delete", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def delete_broker(broker_id):
    broker = db.session.query(Broker).with_for_update().get(broker_id)
    if not broker:
        abort(404)

    name = broker.name
    db.session.delete(broker)
    db.session.commit()
    flash(f"Removed {name}.", "success")
    return redirect(url_for("admin.brokers"))
