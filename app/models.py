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

    credits = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    registration_tokens = db.relationship(
        "RegistrationToken", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    transactions = db.relationship(
        "CreditTransaction", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    bank_transfer_requests = db.relationship(
        "BankTransferRequest", backref="user", lazy=True, cascade="all, delete-orphan"
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
    bank_reference = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class BankTransferRequest(db.Model):
    """A customer's declared intent to pay by bank transfer. Credits are only
    added once an admin manually confirms the funds arrived (via the emailed
    confirm link) - there is no automated way to verify a bank transfer."""

    __tablename__ = "bank_transfer_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    reference = db.Column(db.String(32), unique=True, nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending | confirmed
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