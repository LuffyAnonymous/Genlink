from flask import current_app, render_template
from flask_mail import Message
from app.extensions import mail


def send_admin_registration_email(user, confirm_url):
    """Sent to admin@genlinklab.co.uk (or ADMIN_EMAIL) with the new
    customer's details and a one-click link to approve the account."""
    msg = Message(
        subject=f"New Genlinklab registration - {user.name}",
        recipients=[current_app.config["ADMIN_EMAIL"]],
    )
    msg.html = render_template(
        "emails/admin_new_registration.html", user=user, confirm_url=confirm_url
    )
    mail.send(msg)


def send_user_welcome_email(user):
    """Sent to the customer once the admin has approved their account."""
    msg = Message(
        subject="Your Genlinklab account is approved",
        recipients=[user.email],
    )
    msg.html = render_template(
        "emails/user_welcome.html", user=user, login_url=current_app.config["APP_BASE_URL"] + "/login"
    )
    mail.send(msg)


def send_admin_bank_transfer_email(user, transfer, confirm_url):
    """Sent to admin@genlinklab.co.uk when a customer declares they're
    sending a bank transfer, with a one-click link to confirm receipt and
    credit the account."""
    msg = Message(
        subject=f"Bank transfer expected - {user.name} ({transfer.reference})",
        recipients=[current_app.config["ADMIN_EMAIL"]],
    )
    msg.html = render_template(
        "emails/admin_bank_transfer.html", user=user, transfer=transfer, confirm_url=confirm_url
    )
    mail.send(msg)


def send_user_credits_added_email(user, transfer):
    """Sent to the customer once the admin has confirmed their bank transfer
    arrived and credited their account."""
    msg = Message(
        subject="Your Genlinklab credits have been added",
        recipients=[user.email],
    )
    msg.html = render_template(
        "emails/user_credits_added.html",
        user=user,
        transfer=transfer,
        account_url=current_app.config["APP_BASE_URL"] + "/account",
    )
    mail.send(msg)
