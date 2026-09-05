"""
Thin wrapper around PayPal's REST API (Orders v2 + webhook verification),
using plain HTTP calls rather than PayPal's SDK - same approach as
app/utils/email.py's Resend integration.

Built to PayPal's documented API contract, but NOT yet tested against a
real sandbox account (no credentials were available while writing this -
see PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET in app/config.py). Run a real
sandbox checkout (and a real webhook delivery, e.g. via PayPal's webhook
simulator) before relying on this in production, the same way the Stripe
integration was verified with real signed webhook payloads before launch.
"""
import requests


def _base_url(config):
    return "https://api-m.paypal.com" if config.get("PAYPAL_MODE") == "live" else "https://api-m.sandbox.paypal.com"


def _get_access_token(config):
    response = requests.post(
        f"{_base_url(config)}/v1/oauth2/token",
        auth=(config["PAYPAL_CLIENT_ID"], config["PAYPAL_CLIENT_SECRET"]),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def create_order(reference, amount_gbp, description, return_url, cancel_url, config):
    """Creates a PayPal order (intent=CAPTURE) and returns the parsed
    response - use get_approve_url() on the result to find where to send
    the customer."""
    token = _get_access_token(config)
    response = requests.post(
        f"{_base_url(config)}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference,
                "custom_id": reference,
                "amount": {"currency_code": "GBP", "value": f"{amount_gbp:.2f}"},
                "description": description,
            }],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW",
                "brand_name": "Genlinklab",
            },
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_approve_url(order):
    for link in order.get("links", []):
        if link.get("rel") == "approve":
            return link.get("href")
    return None


def capture_order(order_id, config):
    """Captures an approved order. Returns (status_code, body) rather than
    raising on a non-200 - PayPal uses 4xx for legitimate outcomes here
    (e.g. ORDER_ALREADY_CAPTURED), which the caller needs to see, not just
    a generic exception."""
    token = _get_access_token(config)
    response = requests.post(
        f"{_base_url(config)}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body


def get_capture_id(capture_response):
    try:
        return capture_response["purchase_units"][0]["payments"]["captures"][0]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def verify_webhook_signature(headers, webhook_event, config):
    token = _get_access_token(config)
    response = requests.post(
        f"{_base_url(config)}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
            "cert_url": headers.get("PAYPAL-CERT-URL"),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": config["PAYPAL_WEBHOOK_ID"],
            "webhook_event": webhook_event,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("verification_status") == "SUCCESS"


def order_id_from_webhook_event(event):
    """CHECKOUT.ORDER.APPROVED's resource *is* the order (resource.id).
    PAYMENT.CAPTURE.COMPLETED's resource is the capture, which carries the
    order id at resource.supplementary_data.related_ids.order_id instead -
    there's no single field name common to both, so the event type decides
    which path to read."""
    event_type = event.get("event_type")
    resource = event.get("resource") or {}

    if event_type == "CHECKOUT.ORDER.APPROVED":
        return resource.get("id")
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        return (resource.get("supplementary_data") or {}).get("related_ids", {}).get("order_id")
    return None
