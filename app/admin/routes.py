from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, abort
from flask_login import login_required, current_user

from app.clubs import CLUBS, get_club
from app.extensions import db, limiter
from app.models import User, RegistrationToken, CreditTransaction, Match
from app.utils.email import send_user_welcome_email

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
def dashboard():
    pending_users = (
        User.query.filter_by(is_approved=False).order_by(User.created_at.asc()).all()
    )
    all_users = User.query.order_by(User.created_at.desc()).all()
    matches = (
        Match.query.order_by(Match.club_slug.asc(), Match.kickoff_at.asc().nullslast()).all()
    )

    return render_template(
        "admin/dashboard.html",
        pending_users=pending_users,
        all_users=all_users,
        matches=matches,
        clubs=CLUBS,
    )


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def approve_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_approved:
        flash(f"{user.email} was already approved.", "error")
        return redirect(url_for("admin.dashboard"))

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
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/users/<int:user_id>/decline", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def decline_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_approved:
        flash(f"{user.email} is already approved - can't decline an active account.", "error")
        return redirect(url_for("admin.dashboard"))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f"Declined and removed the registration request from {email}.", "success")
    return redirect(url_for("admin.dashboard"))


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
        return redirect(url_for("admin.dashboard"))

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
    return redirect(url_for("admin.dashboard"))


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
        return redirect(url_for("admin.dashboard"))

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
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@limiter.limit("100 per minute", key_func=lambda: str(current_user.get_id()))
@admin_required
def delete_user(user_id):
    user = db.session.query(User).with_for_update().get(user_id)
    if not user:
        abort(404)

    if user.is_admin:
        flash("Can't delete an admin account here.", "error")
        return redirect(url_for("admin.dashboard"))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f"Deleted {email} and all their data.", "success")
    return redirect(url_for("admin.dashboard"))


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
        return redirect(url_for("admin.dashboard"))

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
            return redirect(url_for("admin.dashboard"))

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
    return redirect(url_for("admin.dashboard"))


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
    return redirect(url_for("admin.dashboard"))
