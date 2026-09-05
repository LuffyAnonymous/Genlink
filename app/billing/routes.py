import secrets
from datetime import datetime, timedelta

import requests
import stripe
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app

from flask_login import login_required, current_user

from app.extensions import db, csrf, limiter
from app.models import User, CreditTransaction, PaymentRequest
from app.utils import paypal as paypal_api
from app.utils.email import send_user_credits_added_email

billing_bp = Blueprint("billing", __name__)

PRESET_PACKAGES = [10, 25, 50, 100]

UNLIMITED_MONTH_PRICE = 1500  # GBP, flat price
UNLIMITED_MONTH_DAYS = 30


def _fulfill_payment(payment):
    """Grants credits/unlimited access for a payment_request row. Caller
    must have already locked the row (with_for_update) and set any
    provider-specific id fields on it before calling this - this only
    commits once, covering both. Idempotent: a second call on an
    already-confirmed row is a no-op, so duplicate webhook deliveries or
    a webhook racing the browser return can't double-credit an account."""
    if payment.status == "confirmed":
        return False

    user = db.session.query(User).with_for_update().get(payment.user_id)
    provider_name = {"stripe": "Stripe", "paypal": "PayPal"}.get(payment.provider, payment.provider.capitalize())

    if payment.kind == "unlimited_month":
        base = user.unlimited_until if user.has_unlimited else datetime.utcnow()
        user.unlimited_until = base + timedelta(days=UNLIMITED_MONTH_DAYS)
        description = (
            f"Unlimited access for {UNLIMITED_MONTH_DAYS} days via "
            f"{provider_name} (£{payment.credits}, {payment.reference})"
        )
        amount = 0
        tx_type = "unlimited"
    else:
        user.credits += payment.credits
        description = f"Purchased {payment.credits} credit(s) via {provider_name} ({payment.reference})"
        amount = payment.credits
        tx_type = "purchase"

    payment.status = "confirmed"
    payment.confirmed_at = datetime.utcnow()

    db.session.add(user)
    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type=tx_type,
            amount=amount,
            description=description,
            payment_reference=payment.reference,
        )
    )
    db.session.commit()

    try:
        send_user_credits_added_email(user, payment)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Failed to send credits-added email: %s", exc)

    return True


@billing_bp.route("/buy", methods=["GET"])
@login_required
def buy_credits_page():
    return render_template(
        "billing/buy_credits.html",
        presets=PRESET_PACKAGES,
        unlimited_price=UNLIMITED_MONTH_PRICE,
        payments_enabled=current_app.config.get("PAYMENTS_ENABLED"),
        payment_provider=current_app.config.get("PAYMENT_PROVIDER"),
    )


def _read_product_selection(form):
    """Shared by both providers' checkout-start routes - returns
    (kind, credits, product_name) or (None, None, None) if invalid, in
    which case a flash message has already been set."""
    product = form.get("product", "credits")

    if product == "unlimited_month":
        return "unlimited_month", UNLIMITED_MONTH_PRICE, f"Genlinklab unlimited access ({UNLIMITED_MONTH_DAYS} days)"

    try:
        credits = int(form.get("credits", 0))
    except (TypeError, ValueError):
        credits = 0

    if credits < 1 or credits > 10000:
        flash("Enter a valid number of credits (1-10,000).", "error")
        return None, None, None

    return "credits", credits, f"{credits} Genlinklab credit(s)"


@billing_bp.route("/checkout", methods=["POST"])
@limiter.limit("10 per hour", key_func=lambda: str(current_user.get_id()))
@login_required
def create_checkout_session():
    if not current_app.config.get("PAYMENTS_ENABLED") or current_app.config.get("PAYMENT_PROVIDER") != "stripe":
        flash("Card payments are temporarily unavailable - please check back soon.", "error")
        return redirect(url_for("billing.buy_credits_page"))

    kind, credits, product_name = _read_product_selection(request.form)
    if kind is None:
        return redirect(url_for("billing.buy_credits_page"))

    payment = PaymentRequest(
        user_id=current_user.id,
        credits=credits,
        kind=kind,
        provider="stripe",
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

    payment.stripe_payment_intent_id = session.get("payment_intent")
    _fulfill_payment(payment)

    return "", 200


@billing_bp.route("/paypal/checkout", methods=["POST"])
@limiter.limit("10 per hour", key_func=lambda: str(current_user.get_id()))
@login_required
def create_paypal_order():
    if not current_app.config.get("PAYMENTS_ENABLED") or current_app.config.get("PAYMENT_PROVIDER") != "paypal":
        flash("Payments are temporarily unavailable - please check back soon.", "error")
        return redirect(url_for("billing.buy_credits_page"))

    kind, credits, product_name = _read_product_selection(request.form)
    if kind is None:
        return redirect(url_for("billing.buy_credits_page"))

    payment = PaymentRequest(
        user_id=current_user.id,
        credits=credits,
        kind=kind,
        provider="paypal",
        reference=f"TS-{secrets.token_hex(4).upper()}",
        token=secrets.token_urlsafe(32),
    )
    db.session.add(payment)
    db.session.commit()

    try:
        order = paypal_api.create_order(
            reference=payment.reference,
            amount_gbp=credits,
            description=product_name,
            return_url=url_for("billing.paypal_return", reference=payment.reference, _external=True),
            cancel_url=url_for("billing.buy_credits_page", _external=True),
            config=current_app.config,
        )
    except requests.RequestException as exc:
        current_app.logger.error("PayPal order creation failed: %s", exc)
        flash("Couldn't start checkout - please try again shortly.", "error")
        return redirect(url_for("billing.buy_credits_page"))

    approve_url = paypal_api.get_approve_url(order)
    if not approve_url:
        current_app.logger.error("PayPal order had no approve link: %s", order)
        flash("Couldn't start checkout - please try again shortly.", "error")
        return redirect(url_for("billing.buy_credits_page"))

    payment.paypal_order_id = order.get("id")
    db.session.commit()

    return redirect(approve_url, code=303)


@billing_bp.route("/paypal/return/<reference>")
@login_required
def paypal_return(reference):
    """Unlike Stripe's return route, this one does capture the payment
    itself - PayPal's /capture call is a direct authenticated server-to-
    server request to PayPal, so its response is authoritative (not
    something the customer's browser could spoof), unlike Stripe
    Checkout's redirect which carries no such confirmation. The webhook
    below still exists as a fallback for the customer never coming back
    (e.g. they approve on PayPal's app and close the tab)."""
    payment = PaymentRequest.query.filter_by(
        reference=reference, user_id=current_user.id
    ).first_or_404()

    if payment.status == "confirmed":
        return render_template("billing/transfer_confirmed.html", transfer=payment, already=False)

    order_id = request.args.get("token") or payment.paypal_order_id
    if not order_id:
        return render_template("billing/stripe_processing.html", transfer=payment)

    payment = PaymentRequest.query.with_for_update().filter_by(
        reference=reference, user_id=current_user.id
    ).first()
    if payment.status == "confirmed":
        return render_template("billing/transfer_confirmed.html", transfer=payment, already=False)

    try:
        status_code, body = paypal_api.capture_order(order_id, current_app.config)
    except requests.RequestException as exc:
        current_app.logger.error("PayPal capture failed: %s", exc)
        return render_template("billing/stripe_processing.html", transfer=payment)

    if status_code == 200 and body.get("status") == "COMPLETED":
        payment.paypal_capture_id = paypal_api.get_capture_id(body)
        _fulfill_payment(payment)
        return render_template("billing/transfer_confirmed.html", transfer=payment, already=False)

    # Not completed yet, or the customer backed out - the webhook will
    # still fulfill it if PayPal confirms the payment later.
    current_app.logger.info("PayPal capture for %s returned %s: %s", reference, status_code, body)
    return render_template("billing/stripe_processing.html", transfer=payment)


@billing_bp.route("/webhook/paypal", methods=["POST"])
@csrf.exempt  # PayPal calls this server-to-server - there's no browser session/CSRF cookie to check
def paypal_webhook():
    body_dict = request.get_json(silent=True) or {}

    try:
        verified = paypal_api.verify_webhook_signature(request.headers, body_dict, current_app.config)
    except requests.RequestException as exc:
        current_app.logger.error("PayPal webhook signature check failed: %s", exc)
        return "", 400

    if not verified:
        current_app.logger.warning("Rejected PayPal webhook: signature verification failed")
        return "", 400

    event_type = body_dict.get("event_type")
    if event_type not in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
        return "", 200  # not an event we care about - acknowledge and ignore

    order_id = paypal_api.order_id_from_webhook_event(body_dict)
    if not order_id:
        current_app.logger.error("PayPal webhook had no order id we recognize - event %s", body_dict.get("id"))
        return "", 200

    payment = PaymentRequest.query.with_for_update().filter_by(paypal_order_id=order_id).first()
    if not payment:
        current_app.logger.error("PayPal webhook referenced unknown order %s", order_id)
        return "", 200

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        payment.paypal_capture_id = (body_dict.get("resource") or {}).get("id")

    _fulfill_payment(payment)
    return "", 200
