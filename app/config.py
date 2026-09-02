import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3001")

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Mail (used for the admin registration-confirmation email + user welcome email)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.mail.us-east-1.awsapps.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 465))

    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", False)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", True)

    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "admin@genlinklab.co.uk")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Genlinklab <admin@genlinklab.co.uk>")

    MAIL_SUPPRESS_SEND = _env_bool("MAIL_SUPPRESS_SEND", False)

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@genlinklab.co.uk")
    REGISTRATION_TOKEN_EXPIRY_DAYS = int(os.environ.get("REGISTRATION_TOKEN_EXPIRY_DAYS", 7))

    # --- Bank transfer (manual) ---
    CREDIT_PRICE_GBP_PENCE = 100  # 1 credit = GBP 1.00, fixed per the spec
    BANK_TRANSFER_DETAILS = {
        "account_number": os.environ.get("BANK_ACCOUNT_NUMBER"),
        "iban": os.environ.get("BANK_IBAN"),
        "currency": os.environ.get("BANK_CURRENCY", "GBP"),
        "bic_swift": os.environ.get("BANK_BIC_SWIFT"),
    }

    # --- Link generation API (your existing ticket-link generator) ---
    LINKGEN_API_URL = os.environ.get("LINKGEN_API_URL", "http://127.0.0.1:4000/api/manutd")
    LINKGEN_API_KEY = os.environ.get("LINKGEN_API_KEY")
    LINKGEN_COST_CREDITS = int(os.environ.get("LINKGEN_COST_CREDITS", 1))

    # Cap request body size (mainly relevant to the CSV bulk upload)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB

    WTF_CSRF_TIME_LIMIT = None
