"""
Single place where a "job" (one ticketing account attempted against one
match) is turned into a call to your link generation API, with a credit
only ever deducted when that call succeeds AND produces a genuinely new
ticket link.

Used by both:
  - the single-account form on the match page (via /api/generate-link)
  - the CSV bulk uploader (one call per row)
so the credit/logging/dedup logic can't drift between the two entry points.
"""
from datetime import datetime
import json

from app.extensions import db
from app.models import User, CreditTransaction, LinkGenerationLog, GeneratedTicket, Ticket
from app.utils.linkgen import call_link_generation_api

# Fields that must never be written to the database or logs in plaintext.
SENSITIVE_KEYS = {"password", "account_password"}


def _redact(payload: dict) -> dict:
    return {k: ("***redacted***" if k in SENSITIVE_KEYS else v) for k, v in payload.items()}


def run_link_job(user_id: int, payload: dict, app_config) -> dict:
    """payload is expected to contain at least `email`/`password` (the
    customer's ticketing account) and `match_name`; `proxy` and `club` are
    optional. Returns a plain dict - callers turn it into a jsonify()
    response or a row in a results table as needed."""
    account_email = payload.get("email")
    match_name = payload.get("match_name")

    # Row lock so concurrent submissions from the same user (e.g. a fast
    # CSV loop) can't both pass the balance/dedup check and overspend.
    user = db.session.query(User).with_for_update().get(user_id)

    # A customer with an active unlimited-month pass never has a credit
    # cost - zeroing it here means every balance check and deduction below
    # (both branches) is automatically a no-op, without special-casing each.
    cost = 0 if user.has_unlimited else app_config["LINKGEN_COST_CREDITS"]

    # Dedup: if this exact account already has a generated link for this
    # match, reuse it instead of calling the API again or spending a credit.

    existing = None

    if account_email and match_name:
        existing = GeneratedTicket.query.filter_by(
            user_id=user_id,
            account_email=account_email,
            match_name=match_name
        ).first()


    # Already generated
    if existing:
        return {
            "success": True,
            "reused": True,
            "link": existing.ticket_link,
            "credits_consumed": 0,
            "credits_remaining": user.credits,
            "email": account_email,
            "message": "A link for this account and match already exists - no credit was charged.",
        }


    # Local-dev-only mock: hand out a link straight from the `tickets`
    # table instead of calling the real API, so the full flow can be
    # tested without a link-generation API running. Off by default - see
    # ENABLE_MOCK_TICKET_LOOKUP in app/config.py. This still skips password
    # verification and the real API call entirely, so it must never be on
    # anywhere real users can reach the app.
    if app_config.get("ENABLE_MOCK_TICKET_LOOKUP"):
        ticket = Ticket.query.filter_by(
            supporter_id=account_email,
            event_name=match_name
        ).first()

        if ticket:
            if user.credits < cost:
                return {
                    "success": False,
                    "error": "insufficient_credits",
                    "message": f"You need at least {cost} credit(s) to generate this ticket.",
                    "credits_remaining": user.credits,
                    "email": account_email,
                }

            link = ticket.nfc
            try:
                event_date = datetime.strptime(ticket.event_date, "%d/%m/%Y %H:%M")
            except (TypeError, ValueError):
                event_date = None

            db.session.add(
                GeneratedTicket(
                    user_id=user_id,
                    account_email=account_email,
                    match_name=ticket.event_name,
                    event_date=event_date,
                    ticket_link=link,
                    club_slug=payload.get("club"),
                )
            )

            user.credits -= cost

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return {
                    "success": False,
                    "error": "database_error",
                    "message": str(e),
                    "credits_remaining": user.credits + cost,
                    "email": account_email,
                }

            return {
                "success": True,
                "reused": False,
                "unlimited": user.has_unlimited,
                "link": link,
                "credits_consumed": cost,
                "credits_remaining": user.credits,
                "email": account_email,
                "message": "Ticket link generated successfully.",
            }

    if user.credits < cost:
        return {
            "success": False,
            "error": "insufficient_credits",
            "message": f"You need at least {cost} credit(s) to run this.",
            "credits_remaining": user.credits,
            "email": account_email,
        }

    # Your existing Manunited() generation logic here

    result = call_link_generation_api(payload, app_config)

    log = LinkGenerationLog(
        user_id=user.id,
        request_payload=json.dumps(_redact(payload))[:5000],
        success=result.success,
        generated_link=result.link,
        external_response=json.dumps(result.raw)[:5000],
    )

    if result.success:
        user.credits -= cost
        log.credits_consumed = cost
        db.session.add(user)

        resolved_match_name = result.match_name or match_name or "Unknown match"
        description = f"Ticket link generated ({resolved_match_name})"
        db.session.add(
            CreditTransaction(user_id=user.id, type="consume", amount=-cost, description=description)
        )

        db.session.add(
            GeneratedTicket(
                user_id=user.id,
                account_email=account_email or "unknown",
                match_name=resolved_match_name,
                event_date=result.event_date,
                ticket_link=result.link,
                club_slug=payload.get("club"),
            )
        )

    db.session.add(log)
    db.session.commit()

    if result.success:
        return {
            "success": True,
            "reused": False,
            "unlimited": user.has_unlimited,
            "link": result.link,
            "credits_consumed": cost,
            "credits_remaining": user.credits,
            "email": account_email,
        }

    return {
        "success": False,
        "error": "link_generation_failed",
        "message": result.raw.get("message") or result.raw.get("error") or "That attempt failed. No credit was charged.",
        "details": result.raw,
        "credits_remaining": user.credits,
        "email": account_email,
    }
