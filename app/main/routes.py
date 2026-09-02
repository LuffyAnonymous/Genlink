import io
import json
from datetime import datetime
from app.clubs import CLUBS, get_club
from app.extensions import db
from app.services.link_jobs import run_link_job
from flask_login import login_required, current_user
from app.models import CreditTransaction, LinkGenerationLog, Match, GeneratedTicket
from app.utils.csv_tools import generate_template_csv, parse_accounts_csv, CsvValidationError
from flask import Blueprint, render_template, redirect, url_for, abort, request, flash, Response, current_app



main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("main/index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    transactions = (
        CreditTransaction.query.filter_by(user_id=current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(10)
        .all()
    )
    links = (
        LinkGenerationLog.query.filter_by(user_id=current_user.id)
        .order_by(LinkGenerationLog.created_at.desc())
        .limit(5)
        .all()
    )
    # request_payload is stored as a JSON string - parse it here so the
    # template can read .email / .match_name directly instead of getting
    # Undefined back from attribute access on a plain string.
    for link in links:
        try:
            link.payload_data = json.loads(link.request_payload) if link.request_payload else {}
        except (TypeError, ValueError):
            link.payload_data = {}

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
        "main/dashboard.html",
        transactions=transactions,
        links=links,
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


def _get_match_or_404(slug, match_id):
    match = Match.query.filter_by(id=match_id, club_slug=slug, is_active=True).first()
    if not match:
        abort(404)
    return match


@main_bp.route("/tickets/<slug>")
@login_required
def club_matches(slug):
    club = _get_club_or_404(slug)
    matches = (
        Match.query.filter_by(club_slug=slug, is_active=True)
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
