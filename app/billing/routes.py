import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, CreditTransaction, BankTransferRequest
from app.utils.email import send_admin_bank_transfer_email, send_user_credits_added_email

billing_bp = Blueprint("billing", __name__)

PRESET_PACKAGES = [10, 25, 50, 100]

UNLIMITED_MONTH_PRICE = 1500  # GBP, flat price
UNLIMITED_MONTH_DAYS = 30


@billing_bp.route("/buy", methods=["GET"])
@login_required
def buy_credits_page():
    return render_template(
        "billing/buy_credits.html",
        presets=PRESET_PACKAGES,
        unlimited_price=UNLIMITED_MONTH_PRICE,
        bank=current_app.config["BANK_TRANSFER_DETAILS"],
    )


@billing_bp.route("/checkout", methods=["POST"])
@login_required
def create_transfer_request():
    product = request.form.get("product", "credits")

    if product == "unlimited_month":
        kind = "unlimited_month"
        credits = UNLIMITED_MONTH_PRICE
    else:
        kind = "credits"
        try:
            credits = int(request.form.get("credits", 0))
        except (TypeError, ValueError):
            credits = 0

        if credits < 1 or credits > 10000:
            flash("Enter a valid number of credits (1-10,000).", "error")
            return redirect(url_for("billing.buy_credits_page"))

    transfer = BankTransferRequest(
        user_id=current_user.id,
        credits=credits,
        kind=kind,
        reference=f"TS-{secrets.token_hex(4).upper()}",
        token=secrets.token_urlsafe(32),
    )
    db.session.add(transfer)
    db.session.commit()

    confirm_url = url_for("billing.confirm_transfer", token=transfer.token, _external=True)
    try:
        send_admin_bank_transfer_email(current_user, transfer, confirm_url)
    except Exception as exc:  # noqa: BLE001 - surface but don't crash the request
        current_app.logger.error("Failed to send admin bank transfer email: %s", exc)
        flash(
            "Your request was saved, but we couldn't notify our admin automatically. "
            "Please contact support with your payment reference once you've sent the transfer.",
            "error",
        )

    return redirect(url_for("billing.transfer_pending", reference=transfer.reference))


@billing_bp.route("/pending/<reference>")
@login_required
def transfer_pending(reference):
    transfer = BankTransferRequest.query.filter_by(
        reference=reference, user_id=current_user.id
    ).first_or_404()
    return render_template(
        "billing/transfer_pending.html",
        transfer=transfer,
        bank=current_app.config["BANK_TRANSFER_DETAILS"],
    )


@billing_bp.route("/admin/confirm/<token>", methods=["GET", "POST"])
def confirm_transfer(token):
    """Admin clicks this from the notification email once the bank transfer
    has actually landed in the account - credits are only ever added here,
    never automatically, since a bank transfer can't be verified in-app.

    GET only ever displays the pending transfer, so a mail scanner or
    link-preview bot fetching this URL from the admin's inbox can't
    silently add credits - the admin has to submit the form below (a real
    POST) for anything to happen."""
    transfer = BankTransferRequest.query.filter_by(token=token).first()

    if not transfer:
        return render_template("billing/confirm_invalid.html"), 400

    if transfer.status == "confirmed":
        return render_template("billing/transfer_confirmed.html", transfer=transfer, already=True)

    if request.method == "GET":
        return render_template(
            "billing/confirm_transfer.html", transfer=transfer, bank=current_app.config["BANK_TRANSFER_DETAILS"]
        )

    # Lock the transfer row itself so a double-submit (or two admins
    # confirming at once) can't both pass the status check above and add
    # credits twice - the second one blocks here, then sees "confirmed"
    # once the first commits.
    transfer = BankTransferRequest.query.with_for_update().filter_by(token=token).first()
    if not transfer:
        return render_template("billing/confirm_invalid.html"), 400
    if transfer.status == "confirmed":
        return render_template("billing/transfer_confirmed.html", transfer=transfer, already=True)

    user = db.session.query(User).with_for_update().get(transfer.user_id)

    if transfer.kind == "unlimited_month":
        # Extend from the current expiry if they're already unlimited and
        # it hasn't lapsed yet, otherwise start the 30 days from now.
        base = user.unlimited_until if user.has_unlimited else datetime.utcnow()
        user.unlimited_until = base + timedelta(days=UNLIMITED_MONTH_DAYS)
        transaction_description = (
            f"Unlimited access for {UNLIMITED_MONTH_DAYS} days via bank transfer "
            f"(£{transfer.credits}, {transfer.reference})"
        )
        transaction_amount = 0
        transaction_type = "unlimited"
    else:
        user.credits += transfer.credits
        transaction_description = f"Purchased {transfer.credits} credit(s) via bank transfer ({transfer.reference})"
        transaction_amount = transfer.credits
        transaction_type = "purchase"

    transfer.status = "confirmed"
    transfer.confirmed_at = datetime.utcnow()

    db.session.add(user)
    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type=transaction_type,
            amount=transaction_amount,
            description=transaction_description,
            bank_reference=transfer.reference,
        )
    )
    db.session.commit()

    try:
        send_user_credits_added_email(user, transfer)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Failed to send credits-added email: %s", exc)

    return render_template("billing/transfer_confirmed.html", transfer=transfer, already=False)
