import os
from dotenv import load_dotenv

from app.clubs import CLUBS

load_dotenv()


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3001")

    # Cookie hardening. SESSION_COOKIE_SECURE defaults on since the app is
    # meant to sit behind HTTPS (see ProxyFix in app/__init__.py) - turn it
    # off only for local http:// development, where a Secure cookie would
    # never get sent back by the browser.
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Mail (admin registration-confirmation email + user welcome email) ---
    # Sent via Resend's HTTP API (app/utils/email.py), not SMTP - most PaaS
    # hosts (Render included) block outbound SMTP entirely to prevent spam
    # abuse, which no SMTP port/credential change can work around.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Genlinklab <admin@genlinklab.co.uk>")
    MAIL_SUPPRESS_SEND = _env_bool("MAIL_SUPPRESS_SEND", False)

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@genlinklab.co.uk")
    REGISTRATION_TOKEN_EXPIRY_DAYS = int(os.environ.get("REGISTRATION_TOKEN_EXPIRY_DAYS", 7))

    # --- Payments ---
    # PAYMENTS_ENABLED is the single kill switch for the whole buy-credits
    # flow - when off, the buy-credits page shows a "temporarily
    # unavailable" notice instead of a checkout button, and both provider
    # routes below refuse to start a new payment even if hit directly.
    # PAYMENT_PROVIDER picks which one actually runs when enabled - flip
    # this (and PAYMENTS_ENABLED) once the new provider is ready, no code
    # changes needed.
    PAYMENTS_ENABLED = _env_bool("PAYMENTS_ENABLED", True)
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "stripe")  # "stripe" | "paypal"

    # --- Stripe (credit/unlimited-pass checkout) ---
    # Test-mode keys (sk_test_.../whsec_...) for local dev; swap for live
    # keys (sk_live_...) only in production. Never hard-code these -
    # STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET must only ever live in
    # .env (gitignored), same as LINKGEN_API_KEY.
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

    # --- PayPal (credit/unlimited-pass checkout) ---
    # PAYPAL_MODE "sandbox" hits api-m.sandbox.paypal.com for testing;
    # "live" hits api-m.paypal.com for real payments. PAYPAL_WEBHOOK_ID
    # comes from the webhook's details page in the PayPal Developer
    # Dashboard once a real webhook endpoint is registered there.
    PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
    PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET")
    PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID")

    # --- Link generation API (your existing ticket-link generator) ---
    # LINKGEN_API_URL/KEY below are the default (currently Man Utd's).
    # Any other club can plug in its own automation independently, without
    # touching this file or the shared app code at all, by setting
    # LINKGEN_API_URL_<SLUG> / LINKGEN_API_KEY_<SLUG> in .env - slug
    # uppercased with hyphens turned to underscores, e.g. a service for
    # "aston-villa" is LINKGEN_API_URL_ASTON_VILLA. call_link_generation_api()
    # looks up the club from the request payload and uses that club's
    # override if one is set, falling back to LINKGEN_API_URL/KEY otherwise.
    LINKGEN_API_URL = os.environ.get("LINKGEN_API_URL", "http://127.0.0.1:4000/api/manutd")
    LINKGEN_API_KEY = os.environ.get("LINKGEN_API_KEY")
    LINKGEN_COST_CREDITS = int(os.environ.get("LINKGEN_COST_CREDITS", 1))

    LINKGEN_CLUBS = {}
    for _club in CLUBS:
        _env_slug = _club["slug"].upper().replace("-", "_")
        _club_url = os.environ.get(f"LINKGEN_API_URL_{_env_slug}")
        if _club_url:
            LINKGEN_CLUBS[_club["slug"]] = {
                "url": _club_url,
                "key": os.environ.get(f"LINKGEN_API_KEY_{_env_slug}"),
            }

    # Local-dev-only shortcut: when on, run_link_job() will hand out a link
    # straight from the `tickets` table (seeded by `flask seed-db`) instead
    # of calling LINKGEN_API_URL, so you can test the full credit/dedup flow
    # without a real link-generation API running. Leave this off anywhere
    # real users can reach the app - it skips password verification and the
    # actual API call entirely.
    ENABLE_MOCK_TICKET_LOOKUP = _env_bool("ENABLE_MOCK_TICKET_LOOKUP", False)

    # Cap request body size (mainly relevant to the CSV bulk upload)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB

    WTF_CSRF_TIME_LIMIT = None

    # --- Rate limiting (Flask-Limiter) ---
    # In-memory by default - fine for a single worker, but limits aren't
    # shared across gunicorn workers. Point this at Redis (e.g.
    # redis://localhost:6379) once you run more than one worker and want
    # exact limits rather than "roughly N workers x the stated rate."
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
