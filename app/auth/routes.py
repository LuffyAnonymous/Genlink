import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, RegistrationToken
from app.auth.forms import RegistrationForm, LoginForm
from app.utils.email import send_admin_registration_email, send_user_welcome_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.ticket_manager"))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Try logging in instead.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            password_hash=generate_password_hash(form.password.data),
            is_approved=False,
        )
        db.session.add(user)
        db.session.commit()

        token_value = secrets.token_urlsafe(32)
        token = RegistrationToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.utcnow()
            + timedelta(days=current_app.config["REGISTRATION_TOKEN_EXPIRY_DAYS"]),
        )
        db.session.add(token)
        db.session.commit()

        confirm_url = url_for("auth.confirm_registration", token=token_value, _external=True)
        try:
            send_admin_registration_email(user, confirm_url)
        except Exception as exc:  # noqa: BLE001 - surface but don't crash registration
            current_app.logger.error("Failed to send admin registration email: %s", exc)
            flash(
                "Your details were saved, but we couldn't email the admin automatically. "
                "Please contact support to complete your registration.",
                "error",
            )

        return redirect(url_for("auth.pending"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/register/pending")
def pending():
    return render_template("auth/pending.html")


@auth_bp.route("/admin/confirm/<token>")
def confirm_registration(token):
    record = RegistrationToken.query.filter_by(token=token).first()

    if not record or not record.is_valid():
        return render_template("auth/confirm_invalid.html"), 400

    user = record.user
    user.is_approved = True
    user.approved_at = datetime.utcnow()
    record.used_at = datetime.utcnow()
    db.session.commit()

    try:
        send_user_welcome_email(user)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Failed to send welcome email: %s", exc)

    return render_template("auth/confirmed.html", user=user)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.ticket_manager"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash("Invalid email or password.", "error")
        elif not user.is_approved:
            flash(
                "Your account is still awaiting confirmation from our team. "
                "You'll receive an email as soon as it's approved.",
                "error",
            )
        else:
            login_user(user)
            return redirect(url_for("main.ticket_manager"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))
