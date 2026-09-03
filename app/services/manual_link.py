"""
Records a ticket link that a customer found by hand - e.g. via a local,
human-driven browser session for a club that isn't wired to an automated
link-generation API (currently Chelsea and Spurs; Manchester United keeps
using run_link_job() / call_link_generation_api() completely unchanged).

Deliberately a separate function from run_link_job() in link_jobs.py rather
than a branch inside it, so the automated Man United path is never touched
by this. It mirrors the same credit/dedup/storage rules - a manually
recorded ticket looks identical everywhere in the app to an automatically
generated one - it just skips the "call an external API" step, since the
link was already found by the customer.
"""
import json

from app.extensions import db
from app.models import User, CreditTransaction, LinkGenerationLog, GeneratedTicket

SENSITIVE_KEYS = {"password", "account_password"}


def _redact(payload: dict) -> dict:
    return {k: ("***redacted***" if k in SENSITIVE_KEYS else v) for k, v in payload.items()}


def record_manual_link(user_id: int, payload: dict, app_config, event_date=None) -> dict:
    """payload must contain `email` (the ticketing account/Supporter ID),
    `match_name`, and `link` (the ticket link the customer found). `club`
    is optional and only used for record-keeping (GeneratedTicket.club_slug).
    Returns the same shape of dict run_link_job() does, so callers can
    reuse the same success/error handling."""
    account_email = (payload.get("email") or "").strip()
    match_name = payload.get("match_name")
    link = (payload.get("link") or "").strip()

    if not account_email or not link:
        return {
            "success": False,
            "error": "missing_fields",
            "message": "An account/Supporter ID and the ticket link are both required.",
        }

    # Row lock so concurrent submissions from the same user can't both pass
    # the balance check and overspend - same protection run_link_job() uses.
    user = db.session.query(User).with_for_update().get(user_id)
    cost = 0 if user.has_unlimited else app_config["LINKGEN_COST_CREDITS"]

    existing = GeneratedTicket.query.filter_by(
        user_id=user_id,
        account_email=account_email,
        match_name=match_name,
    ).first()

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

    if user.credits < cost:
        return {
            "success": False,
            "error": "insufficient_credits",
            "message": f"You need at least {cost} credit(s) to record this.",
            "credits_remaining": user.credits,
            "email": account_email,
        }

    user.credits -= cost
    db.session.add(user)

    db.session.add(
        CreditTransaction(
            user_id=user.id,
            type="consume",
            amount=-cost,
            description=f"Ticket link recorded ({match_name})",
        )
    )

    db.session.add(
        GeneratedTicket(
            user_id=user.id,
            account_email=account_email,
            match_name=match_name,
            event_date=event_date,
            ticket_link=link,
            club_slug=payload.get("club"),
        )
    )

    db.session.add(
        LinkGenerationLog(
            user_id=user.id,
            request_payload=json.dumps(_redact(payload))[:5000],
            success=True,
            generated_link=link,
            credits_consumed=cost,
            external_response=json.dumps({"source": "manual_browser_capture"})[:5000],
        )
    )

    db.session.commit()

    return {
        "success": True,
        "reused": False,
        "unlimited": user.has_unlimited,
        "link": link,
        "credits_consumed": cost,
        "credits_remaining": user.credits,
        "email": account_email,
    }
