from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    credits = db.Column(db.Integer, default=0, nullable=False)

    # Set when a customer buys the unlimited-for-1-month pass instead of
    # credits - while this is in the future, run_link_job() skips the
    # credit check/deduction entirely rather than reading `credits`.
    unlimited_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def has_unlimited(self):
        return self.unlimited_until is not None and self.unlimited_until > datetime.utcnow()

    registration_tokens = db.relationship(
        "RegistrationToken", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    transactions = db.relationship(
        "CreditTransaction", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    payment_requests = db.relationship(
        "PaymentRequest", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    link_logs = db.relationship(
        "LinkGenerationLog", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def is_active(self):
        # Flask-Login uses this - customers can't log in until admin approves them
        return self.is_approved

    def __repr__(self):
        return f"<User {self.email}>"


class RegistrationToken(db.Model):
    __tablename__ = "registration_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    def is_valid(self):
        return self.used_at is None and self.expires_at > datetime.utcnow()


class CreditTransaction(db.Model):
    __tablename__ = "credit_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # purchase | consume | refund
    amount = db.Column(db.Integer, nullable=False)  # positive for purchase, negative for consume
    description = db.Column(db.String(255), nullable=True)
    payment_reference = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PaymentRequest(db.Model):
    """A customer's checkout attempt, paid via Stripe or PayPal. Credits (or
    unlimited access) are only ever added once the provider has confirmed
    the payment actually succeeded (Stripe's webhook; PayPal's order
    capture/webhook) - never by the browser redirect back to our site alone,
    since that can be skipped, replayed, or spoofed."""

    __tablename__ = "payment_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # For kind="credits", this is the number of credits bought (GBP 1 =
    # 1 credit). For kind="unlimited_month", this is just the GBP price
    # paid (UNLIMITED_MONTH_PRICE) - no credits are granted, an expiry is
    # set on the user instead.
    credits = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), default="credits", nullable=False)  # credits | unlimited_month
    reference = db.Column(db.String(32), unique=True, nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending | confirmed
    provider = db.Column(db.String(20), default="stripe", nullable=False)  # stripe | paypal
    stripe_checkout_session_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    paypal_order_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    paypal_capture_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)


class LinkGenerationLog(db.Model):
    __tablename__ = "link_generation_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    request_payload = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    generated_link = db.Column(db.Text, nullable=True)
    credits_consumed = db.Column(db.Integer, default=0, nullable=False)
    external_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    club_slug = db.Column(db.String(50), nullable=False, index=True)
    home_team = db.Column(db.String(120), nullable=False)
    away_team = db.Column(db.String(120), nullable=False)
    kickoff_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def name(self):
        return f"{self.home_team} v {self.away_team}"

    def __repr__(self):
        return f"<Match {self.name}>"


class GeneratedTicket(db.Model):
    """A successfully generated ticket link, kept so it can be shown again
    on the account page and so re-submitting the same account for the same
    match doesn't spend a second credit."""

    __tablename__ = "generated_tickets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    account_email = db.Column(db.String(255), nullable=False)
    match_name = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.DateTime, nullable=True)
    ticket_link = db.Column(db.Text, nullable=False)
    club_slug = db.Column(db.String(50), nullable=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "account_email", "match_name", name="uq_user_account_match"),
    )

    def __repr__(self):
        return f"<GeneratedTicket {self.match_name} - {self.account_email}>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)

    id_unique = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    supporter_id = db.Column(db.String(100))
    event_name = db.Column(db.String(255))
    event_date = db.Column(db.String(20))
    area_name = db.Column(db.String(255))
    row_name = db.Column(db.String(255))
    seat_name = db.Column(db.String(255))
    nfc = db.Column(db.String(255))
    owner_name = db.Column(db.String(255))