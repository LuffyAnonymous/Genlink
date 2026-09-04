import secrets
from datetime import datetime, timedelta

import stripe
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app

from flask_login import login_required, current_user

from app.extensions import db, csrf
from app.models import User, CreditTransaction, PaymentRequest
from app.utils.email import send_user_credits_added_email

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
    )


@billing_bp.route("/checkout", methods=["POST"])
@login_required
def create_checkout_session():
    product = request.form.get("product", "credits")

    if product == "unlimited_month":
        kind = "unlimited_month"
        credits = UNLIMITED_MONTH_PRICE
        product_name = f"Genlinklab unlimited access ({UNLIMITED_MONTH_DAYS} days)"
    else:
        kind = "credits"
        try:
            credits = int(request.form.get("credits", 0))
        except (TypeError, ValueError):
            credits = 0

        if credits < 1 or credits > 10000:
            flash("Enter a valid number of credits (1-10,000).", "error")
            return redirect(url_for("billing.buy_credits_page"))

        product_name = f"{credits} Genlinklab credit(s)"

    payment = PaymentRequest(
        user_id=current_user.id,
        credits=credits,
        kind=kind,
        reference=f"TS-{secrets.token_hex(4).upper()}",
        token=secrets.token_urlsafe(32),
    )
    db.session.add(payment)
    db.session.commit()

    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {"name": product_name},
                    "unit_amount": credits * 100,  # Stripe wants pence, not pounds
                },
                "quantity": 1,
            }],
            client_reference_id=payment.reference,
            metadata={"reference": payment.reference, "user_id": current_user.id, "kind": kind},
            success_url=url_for("billing.stripe_return", reference=payment.reference, _external=True),
            cancel_url=url_for("billing.buy_credits_page", _external=True),
        )
    except stripe.error.StripeError as exc:
        current_app.logger.error("Stripe checkout session creation failed: %s", exc)
        flash("Couldn't start checkout - please try again shortly.", "error")
        return redirect(url_for("billing.buy_credits_page"))

    payment.stripe_checkout_session_id = session.id
    db.session.commit()

    return redirect(session.url, code=303)


@billing_bp.route("/return/<reference>")
@login_required
def stripe_return(reference):
    """Where Stripe sends the customer back after checkout. Only ever
    displays status - never grants credits itself, since that would let
    anyone who guesses/replays this URL get free credits. The webhook
    below is the only place that actually confirms a payment."""
    payment = PaymentRequest.query.filter_by(
        reference=reference, user_id=current_user.id
    ).first_or_404()

    if payment.status == "confirmed":
        return render_template("billing/transfer_confirmed.html", transfer=payment, already=False)

    # Rare race: the browser redirect landed before Stripe's webhook call
    # did. It'll confirm within moments - this just says so.
    return render_template("billing/stripe_processing.html", transfer=payment)


@billing_bp.route("/webhook/stripe", methods=["POST"])
@csrf.exempt  # Stripe calls this server-to-server - there's no browser session/CSRF cookie to check
def stripe_webhook():
    """Stripe's server calls this directly when a payment's status
    changes. The signature check below is the only thing authenticating
    this request - without it, anyone could POST a fake "payment
    succeeded" event and get free credits, so it is never optional."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config["STRIPE_WEBHOOK_SECRET"]
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        current_app.logger.warning("Rejected webhook: invalid payload/signature (%s)", exc)
        return "", 400

    # checkout.session.completed fires as soon as the customer finishes
    # checkout - for instant methods (card) that means paid, but Stripe
    # also offers delayed methods where the session "completes" while the
    # payment is still processing (payment_status stays "unpaid" until
    # Stripe later sends async_payment_succeeded/failed). Fulfilling on
    # .completed alone without checking payment_status would grant credits
    # before the money has actually arrived on those methods.
    if event["type"] not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return "", 200  # not an event we care about - acknowledge and ignore

    # The Stripe SDK's event objects only support bracket/attribute access,
    # not .get() - calling .get() directly on one raises AttributeError,
    # crashing this handler on every real delivery. .to_dict() converts it
    # (recursively, including `metadata`) to a plain dict first.
    session = event["data"]["object"].to_dict()

    if session.get("payment_status") != "paid":
        return "", 200  # still processing - the async_payment_succeeded event will fulfill it once it lands

    reference = session.get("client_reference_id") or (session.get("metadata") or {}).get("reference")

    if not reference:
        current_app.logger.error("Webhook checkout.session.completed had no reference - session %s", session.get("id"))
        return "", 200  # nothing we can look up - acknowledge so Stripe doesn't retry forever

    # Row lock so a duplicate webhook delivery for the same event (Stripe
    # explicitly says these can happen and to handle them idempotently)
    # can't credit the account twice.
    payment = PaymentRequest.query.with_for_update().filter_by(reference=reference).first()
    if not payment:
        current_app.logger.error("Webhook referenced unknown PaymentRequest %s", reference)
        return "", 200

    if payment.status == "confirmed":
        return "", 200  # already handled - this is a duplicate delivery

    user = db.session.query(User).with_for_update().get(payment.user_id)

    if payment.kind == "unlimited_month":
        base = user.unlimited_until if user.has_unlimited else datetime.utcnow()
        user.unlimited_until = base + timedelta(days=UNLIMITED_MONTH_DAYS)
        transaction_description = (
            f"Unlimited access for {UNLIMITED_MONTH_DAYS} days via Stripe (£{payment.credits}, {payment.reference})"
        )
        transaction_amount = 0
        transaction_type = "unlimited"
    else:
        user.credits += payment.credits
        transaction_description = f"Purchased {payment.credits} credit(s) via Stripe ({payment.reference})"
        transaction_amount = payment.credits
        transaction_type = "purchase"

    payment.status = "confirmed"
    payment.confirmed_at = datetime.utcnow()
    payment.stripe_payment_intent_id = session.get("payment_intent")

    db.session.add(user)
    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type=transaction_type,
            amount=transaction_amount,
            description=transaction_description,
            payment_reference=payment.reference,
        )
    )
    db.session.commit()

    try:
        send_user_credits_added_email(user, payment)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Failed to send credits-added email: %s", exc)

    return "", 200
