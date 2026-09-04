import io
from datetime import datetime, timedelta
from sqlalchemy import or_
from app.clubs import CLUBS, get_club
from app.extensions import db
from app.services.link_jobs import run_link_job
from app.services.manual_link import record_manual_link
from flask_login import login_required, current_user
from app.models import CreditTransaction, Match, GeneratedTicket
from app.utils.csv_tools import generate_template_csv, parse_accounts_csv, CsvValidationError
from flask import Blueprint, render_template, redirect, url_for, abort, request, flash, Response, current_app



main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.ticket_manager"))
    return render_template("main/index.html")


@main_bp.route("/account")
@login_required
def account():
    transactions = (
        CreditTransaction.query.filter_by(user_id=current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(10)
        .all()
    )

    now = datetime.utcnow()
    all_tickets = (
        GeneratedTicket.query.filter_by(user_id=current_user.id)
        .order_by(GeneratedTicket.generated_at.desc())
        .all()
    )
    # Tickets with no event date are shown alongside upcoming ones - the
    # match hasn't been ruled out as past, so treating it as unknown/soon
    # is safer than hiding it or filing it under "previous".
    upcoming_tickets = [
        t for t in all_tickets if t.event_date is None or t.event_date >= now
    ]
    previous_tickets = [
        t for t in all_tickets if t.event_date is not None and t.event_date < now
    ]
    upcoming_tickets.sort(key=lambda t: (t.event_date is None, t.event_date or now))
    previous_tickets.sort(key=lambda t: t.event_date, reverse=True)

    return render_template(
        "main/account.html",
        transactions=transactions,
        upcoming_tickets=upcoming_tickets,
        previous_tickets=previous_tickets,
    )


@main_bp.route("/tickets")
@login_required
def ticket_manager():
    return render_template("main/ticket_manager.html", clubs=CLUBS)


def _get_club_or_404(slug):
    club = get_club(slug)
    if not club:
        abort(404)
    return club


# How long after kickoff a match still counts as "upcoming" - covers a full
# 90 minutes plus stoppage/extra time, so it doesn't disappear mid-game.
MATCH_GRACE_PERIOD = timedelta(hours=3)


def _not_finished():
    cutoff = datetime.utcnow() - MATCH_GRACE_PERIOD
    return or_(Match.kickoff_at.is_(None), Match.kickoff_at >= cutoff)


def _get_match_or_404(slug, match_id):
    match = Match.query.filter(
        Match.id == match_id,
        Match.club_slug == slug,
        Match.is_active.is_(True),
        _not_finished(),
    ).first()
    if not match:
        abort(404)
    return match


@main_bp.route("/tickets/<slug>")
@login_required
def club_matches(slug):
    club = _get_club_or_404(slug)
    matches = (
        Match.query.filter(
            Match.club_slug == slug,
            Match.is_active.is_(True),
            _not_finished(),
        )
        .order_by(Match.kickoff_at.asc().nullslast())
        .all()
    )
    return render_template("main/club_matches.html", club=club, matches=matches)


@main_bp.route("/tickets/<slug>/<int:match_id>")
@login_required
def match_generate(slug, match_id):
    club = _get_club_or_404(slug)
    match = _get_match_or_404(slug, match_id)
    return render_template("main/match_generate.html", club=club, match=match)


@main_bp.route("/tickets/<slug>/<int:match_id>/manual", methods=["POST"])
@login_required
def match_manual_submit(slug, match_id):
    """For clubs without an automated login API (currently Chelsea and
    Spurs) - records a ticket link the customer already found by hand,
    e.g. via linkgen_service/multi_club_linkgen.py. Manchester United
    keeps using match_generate's existing /api/generate-link flow; this
    route is untouched by and doesn't touch that one."""
    club = _get_club_or_404(slug)
    match = _get_match_or_404(slug, match_id)

    account_email = (request.form.get("account_email") or "").strip()
    ticket_link = (request.form.get("ticket_link") or "").strip()

    if not account_email or not ticket_link:
        flash("Enter the Supporter ID/email and the ticket link.", "error")
        return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))

    result = record_manual_link(
        current_user.id,
        {
            "email": account_email,
            "match_name": match.name,
            "link": ticket_link,
            "club": slug,
        },
        current_app.config,
        event_date=match.kickoff_at,
    )

    if result.get("success"):
        if result.get("reused"):
            flash("That account already has a link for this match - no credit was charged.", "success")
        else:
            flash(f"Link recorded for {account_email}. Balance: {result['credits_remaining']} credits.", "success")
    else:
        flash(result.get("message", "Couldn't record that link."), "error")

    return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))


@main_bp.route("/tickets/<slug>/<int:match_id>/csv-template")
@login_required
def csv_template(slug, match_id):
    club = _get_club_or_404(slug)
    match = _get_match_or_404(slug, match_id)
    csv_text = generate_template_csv(match.name)
    filename = f"{club['slug']}-{match.id}-accounts-template.csv"
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@main_bp.route("/tickets/<slug>/<int:match_id>/bulk", methods=["POST"])
@login_required
def match_bulk_submit(slug, match_id):
    club = _get_club_or_404(slug)
    match = _get_match_or_404(slug, match_id)

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("Choose a CSV file to upload first.", "error")
        return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))

    if not file.filename.lower().endswith(".csv"):
        flash("Please upload a .csv file.", "error")
        return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))

    try:
        stream = io.TextIOWrapper(file.stream, encoding="utf-8-sig")
        accounts = parse_accounts_csv(stream, match.name)
    except CsvValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))
    except UnicodeDecodeError:
        flash("Couldn't read that file - please upload a plain CSV (UTF-8).", "error")
        return redirect(url_for("main.match_generate", slug=slug, match_id=match_id))

    results = []
    for account in accounts:
        account["club"] = slug
        try:
            result = run_link_job(current_user.id, account, current_app.config)
        except Exception as exc:
            # One bad row (e.g. a timeout or DB hiccup) shouldn't take down
            # the rest of the batch - record it as failed and keep going.
            db.session.rollback()
            result = {
                "success": False,
                "error": "link_generation_failed",
                "message": "That attempt failed. No credit was charged.",
                "details": {"error": str(exc)},
                "credits_remaining": current_user.credits,
                "email": account.get("email"),
            }

        results.append(result)
        if result.get("error") == "insufficient_credits":
            break  # stop the batch once the balance runs out, rest are untried

    return render_template(
        "main/bulk_results.html",
        club=club,
        match=match,
        results=results,
        total=len(accounts),
    )
