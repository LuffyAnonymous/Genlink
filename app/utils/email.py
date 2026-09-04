import requests
from flask import current_app, render_template


def _send_email(subject, recipients, html):
    """All app email goes through Resend's HTTP API (https://resend.com),
    not raw SMTP - Render (and most PaaS hosts) block outbound SMTP
    entirely to prevent spam abuse, which raw smtplib has no way around.
    HTTPS to Resend's API is never blocked the way SMTP ports are."""
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info("MAIL_SUPPRESS_SEND is on - not sending: %r to %s", subject, recipients)
        return

    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}"},
        json={
            "from": current_app.config["MAIL_DEFAULT_SENDER"],
            "to": recipients,
            "subject": subject,
            "html": html,
        },
        timeout=15,
    )
    response.raise_for_status()


def send_admin_registration_email(user, confirm_url):
    """Sent to admin@genlinklab.co.uk (or ADMIN_EMAIL) with the new
    customer's details and a one-click link to approve the account."""
    _send_email(
        subject=f"New Genlinklab registration - {user.name}",
        recipients=[current_app.config["ADMIN_EMAIL"]],
        html=render_template("emails/admin_new_registration.html", user=user, confirm_url=confirm_url),
    )


def send_user_welcome_email(user):
    """Sent to the customer once the admin has approved their account."""
    _send_email(
        subject="Your Genlinklab account is approved",
        recipients=[user.email],
        html=render_template(
            "emails/user_welcome.html", user=user, login_url=current_app.config["APP_BASE_URL"] + "/login"
        ),
    )


def send_user_credits_added_email(user, transfer):
    """Sent to the customer once Stripe confirms their payment succeeded
    (triggered from the /credits/webhook/stripe handler)."""
    _send_email(
        subject="Your Genlinklab credits have been added",
        recipients=[user.email],
        html=render_template(
            "emails/user_credits_added.html",
            user=user,
            transfer=transfer,
            account_url=current_app.config["APP_BASE_URL"] + "/account",
        ),
    )
