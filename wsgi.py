import os
import click
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Match, User, Ticket
from app.utils.linkgen import call_link_generation_api
from werkzeug.security import generate_password_hash

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create any missing tables in PostgreSQL / SQLite - leaves existing tables/data untouched.
    Run with: flask --app wsgi.py init-db"""
    with app.app_context():
        db.create_all()

    print("Database tables created.")


@app.cli.command("seed-db")
def seed_db():
    """Seed sample matches, a demo user, and sample tickets for local development.
    Run with: flask --app wsgi.py seed-db"""
    with app.app_context():
        db.create_all()
        # Seed sample matches
        if Match.query.count() == 0:
            sample_matches = [
                Match(
                    club_slug="man-utd",
                    home_team="Manchester United",
                    away_team="Ipswich Town",
                    kickoff_at=datetime.utcnow() + timedelta(days=5),
                    is_active=True,
                ),
                Match(
                    club_slug="arsenal",
                    home_team="Arsenal",
                    away_team="Chelsea",
                    kickoff_at=datetime.utcnow() + timedelta(days=7),
                    is_active=True,
                ),
                Match(
                    club_slug="liverpool",
                    home_team="Liverpool",
                    away_team="Manchester City",
                    kickoff_at=datetime.utcnow() + timedelta(days=10),
                    is_active=True,
                ),
                Match(
                    club_slug="chelsea",
                    home_team="Chelsea",
                    away_team="Tottenham Hotspur",
                    kickoff_at=datetime.utcnow() + timedelta(days=12),
                    is_active=True,
                ),
            ]
            db.session.add_all(sample_matches)
            print(f"Seeded {len(sample_matches)} sample matches.")

        # Seed sample ticket for instant local link generation testing
        if not Ticket.query.filter_by(id_unique="DEMO-MU-001").first():
            demo_ticket = Ticket(
                id_unique="DEMO-MU-001",
                supporter_id="1234567",
                event_name="Manchester United v Ipswich Town",
                event_date="15/09/2026 15:00",
                area_name="Sir Alex Ferguson Stand Tier 2",
                row_name="12",
                seat_name="45",
                nfc="https://tickets.manutd.com/digital-pass/MUFC-1234567-IPS",
                owner_name="Demo Supporter",
            )
            db.session.add(demo_ticket)
            print("Seeded sample ticket for Supporter ID 1234567.")

        # Seed demo user
        demo_user = User.query.filter_by(email="demo@genlinklab.com").first()
        if not demo_user:
            demo_user = User(
                name="Demo User",
                email="demo@genlinklab.com",
                phone="+44 7000 000000",
                password_hash=generate_password_hash("password123"),
                is_approved=True,
                approved_at=datetime.utcnow(),
                credits=25,
            )
            db.session.add(demo_user)
            print("Created demo user: demo@genlinklab.com (password: password123, credits: 25)")
        else:
            print("Demo user already exists.")

        db.session.commit()
        print("Database seeded successfully.")


@app.cli.command("add-manutd-fixtures")
def add_manutd_fixtures():
    """Add Manchester United's 2026/27 Premier League HOME fixtures (Old
    Trafford only - away games aren't sold through this platform) as
    upcoming matches. Safe to re-run - skips any fixture already present for
    the same opponent/kickoff. Kickoff times are UK local.
    Run with: flask --app wsgi.py add-manutd-fixtures"""
    # (away_team, kickoff_at) - home_team is always Manchester United
    home_fixtures = [
        ("Ipswich Town", datetime(2026, 8, 29, 15, 0)),
        ("Manchester City", datetime(2026, 9, 12, 15, 0)),
        ("Tottenham Hotspur", datetime(2026, 10, 10, 15, 0)),
        ("AFC Bournemouth", datetime(2026, 10, 24, 15, 0)),
        ("Aston Villa", datetime(2026, 11, 7, 15, 0)),
        ("Brentford", datetime(2026, 11, 28, 15, 0)),
        ("Coventry City", datetime(2026, 12, 5, 15, 0)),
        ("Nottingham Forest", datetime(2026, 12, 26, 15, 0)),
        ("Sunderland", datetime(2026, 12, 30, 15, 0)),
        ("Newcastle United", datetime(2027, 1, 6, 20, 0)),
        ("Liverpool", datetime(2027, 1, 23, 15, 0)),
        ("Chelsea", datetime(2027, 2, 6, 15, 0)),
        ("Brighton & Hove Albion", datetime(2027, 2, 10, 20, 0)),
        ("Arsenal", datetime(2027, 2, 27, 15, 0)),
        ("Everton", datetime(2027, 3, 13, 15, 0)),
        ("Hull City", datetime(2027, 4, 10, 16, 0)),
        ("Crystal Palace", datetime(2027, 4, 24, 15, 0)),
        ("Leeds United", datetime(2027, 5, 15, 15, 0)),
        ("Fulham", datetime(2027, 5, 30, 16, 0)),
    ]
    fixtures = [("Manchester United", away_team, kickoff_at) for away_team, kickoff_at in home_fixtures]

    with app.app_context():
        existing = {
            (m.home_team, m.away_team, m.kickoff_at)
            for m in Match.query.filter_by(club_slug="man-utd").all()
        }

        added = 0
        for home_team, away_team, kickoff_at in fixtures:
            if (home_team, away_team, kickoff_at) in existing:
                continue
            db.session.add(
                Match(
                    club_slug="man-utd",
                    home_team=home_team,
                    away_team=away_team,
                    kickoff_at=kickoff_at,
                    is_active=True,
                )
            )
            added += 1

        db.session.commit()
        print(f"Added {added} fixture(s). {len(fixtures) - added} already existed and were skipped.")


@app.cli.command("add-chelsea-spurs-fixtures")
def add_chelsea_spurs_fixtures():
    """Add a handful of Chelsea (Stamford Bridge) and Spurs (Tottenham
    Hotspur Stadium) HOME fixtures as upcoming matches, same pattern as
    add-manutd-fixtures - safe to re-run, skips fixtures already present.
    These two clubs use the manual "record a ticket link" flow, not an
    automated API, so this only needs enough real matches to test against.
    Run with: flask --app wsgi.py add-chelsea-spurs-fixtures"""
    fixtures = [
        ("chelsea", "Chelsea", "Brighton & Hove Albion", datetime(2026, 8, 29, 15, 0)),
        ("chelsea", "Chelsea", "Hull City", datetime(2026, 9, 12, 15, 0)),
        ("chelsea", "Chelsea", "Tottenham Hotspur", datetime(2026, 10, 24, 15, 0)),
        ("chelsea", "Chelsea", "Manchester United", datetime(2026, 10, 31, 15, 0)),
        ("chelsea", "Chelsea", "Liverpool", datetime(2026, 12, 5, 15, 0)),
        ("chelsea", "Chelsea", "Newcastle United", datetime(2027, 1, 2, 15, 0)),
        ("spurs", "Tottenham Hotspur", "Newcastle United", datetime(2026, 8, 29, 15, 0)),
        ("spurs", "Tottenham Hotspur", "Everton", datetime(2026, 9, 12, 17, 30)),
        ("spurs", "Tottenham Hotspur", "Aston Villa", datetime(2026, 9, 19, 12, 30)),
        ("spurs", "Tottenham Hotspur", "Crystal Palace", datetime(2026, 10, 31, 17, 30)),
        ("spurs", "Tottenham Hotspur", "Arsenal", datetime(2026, 12, 5, 15, 0)),
        ("spurs", "Tottenham Hotspur", "AFC Bournemouth", datetime(2026, 12, 26, 15, 0)),
    ]

    with app.app_context():
        existing = {
            (m.club_slug, m.home_team, m.away_team, m.kickoff_at)
            for m in Match.query.filter(Match.club_slug.in_(["chelsea", "spurs"])).all()
        }

        added = 0
        for club_slug, home_team, away_team, kickoff_at in fixtures:
            if (club_slug, home_team, away_team, kickoff_at) in existing:
                continue
            db.session.add(
                Match(
                    club_slug=club_slug,
                    home_team=home_team,
                    away_team=away_team,
                    kickoff_at=kickoff_at,
                    is_active=True,
                )
            )
            added += 1

        db.session.commit()
        print(f"Added {added} fixture(s). {len(fixtures) - added} already existed and were skipped.")


@app.cli.command("migrate-stripe-billing")
def migrate_stripe_billing():
    """One-time migration for the bank-transfer -> Stripe billing switch:
    renames the bank_transfer_requests table to payment_requests, renames
    credit_transactions.bank_reference to payment_reference, and adds the
    two new stripe_* columns. Safe to re-run - every step checks first and
    skips if already done. All existing rows (including past confirmed
    bank-transfer payments) are kept - nothing is dropped or reset.
    Run with: flask --app wsgi.py migrate-stripe-billing"""
    from sqlalchemy import inspect, text

    with app.app_context():
        def table_names():
            return inspect(db.engine).get_table_names()

        def column_names(table):
            return {c["name"] for c in inspect(db.engine).get_columns(table)}

        names = table_names()

        if "bank_transfer_requests" in names and "payment_requests" not in names:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE bank_transfer_requests RENAME TO payment_requests"))
            print("Renamed bank_transfer_requests -> payment_requests.")
        elif "payment_requests" in names:
            print("payment_requests already exists - skipping table rename.")
        else:
            print("No existing bank_transfer_requests table - nothing to rename (fresh database).")

        if "payment_requests" in table_names():
            cols = column_names("payment_requests")
            with db.engine.begin() as conn:
                if "stripe_checkout_session_id" not in cols:
                    conn.execute(text("ALTER TABLE payment_requests ADD COLUMN stripe_checkout_session_id VARCHAR(255)"))
                    print("Added payment_requests.stripe_checkout_session_id.")
                if "stripe_payment_intent_id" not in cols:
                    conn.execute(text("ALTER TABLE payment_requests ADD COLUMN stripe_payment_intent_id VARCHAR(255)"))
                    print("Added payment_requests.stripe_payment_intent_id.")

        if "credit_transactions" in table_names():
            cols = column_names("credit_transactions")
            if "bank_reference" in cols and "payment_reference" not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE credit_transactions RENAME COLUMN bank_reference TO payment_reference"))
                print("Renamed credit_transactions.bank_reference -> payment_reference.")
            elif "payment_reference" in cols:
                print("credit_transactions.payment_reference already exists - skipping.")

        db.create_all()  # fills in payment_requests (and anything else) if this is a brand-new database
        print("Migration complete.")


@app.cli.command("check-config")
def check_config():
    """Quick sanity check of the current .env - catches the mistakes that
    fail silently (mail suppressed, a placeholder secret left in, mock mode
    left on) instead of needing a debugging session to notice. Safe to run
    any time, touches nothing.
    Run with: flask --app wsgi.py check-config"""
    problems = []
    warnings = []

    if app.config.get("MAIL_SUPPRESS_SEND"):
        warnings.append("MAIL_SUPPRESS_SEND is true - no emails are actually being sent right now.")

    mail_password = app.config.get("MAIL_PASSWORD") or ""
    mail_server = app.config.get("MAIL_SERVER") or ""
    if not mail_password or "unused" in mail_password.lower() or "replace" in mail_password.lower():
        problems.append("MAIL_PASSWORD looks unset/placeholder - mail will fail to send.")
    elif "gmail.com" in mail_server and " " not in mail_password and len(mail_password) != 16:
        problems.append(
            "MAIL_PASSWORD doesn't look like a Gmail App Password (16 characters) - "
            "if this is your regular account password, Gmail will reject it."
        )

    if app.config.get("SECRET_KEY") == "dev-secret-change-me":
        problems.append("SECRET_KEY is the dev default - must be a real random value anywhere but local dev.")

    db_url = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if db_url.startswith("sqlite"):
        warnings.append(f"Database is SQLite ({db_url}) - fine for local dev, must be real Postgres for anything real.")
    elif not db_url:
        problems.append("DATABASE_URL is not set.")

    if app.config.get("ENABLE_MOCK_TICKET_LOOKUP"):
        warnings.append(
            "ENABLE_MOCK_TICKET_LOOKUP is on - link generation is faked, not calling the real API. "
            "Must be off anywhere real users can reach the app."
        )

    if not app.config.get("LINKGEN_API_KEY"):
        warnings.append("LINKGEN_API_KEY is not set.")

    stripe_secret = app.config.get("STRIPE_SECRET_KEY") or ""
    if not stripe_secret or "replace" in stripe_secret.lower():
        problems.append("STRIPE_SECRET_KEY looks unset/placeholder - checkout will fail.")
    elif stripe_secret.startswith("sk_live_"):
        warnings.append("STRIPE_SECRET_KEY is a LIVE key - real money will be charged.")

    if not app.config.get("STRIPE_WEBHOOK_SECRET"):
        problems.append("STRIPE_WEBHOOK_SECRET is not set - the webhook will reject every event Stripe sends.")

    if not app.config.get("SESSION_COOKIE_SECURE"):
        warnings.append("SESSION_COOKIE_SECURE is off - correct for local http://, must be on anywhere real.")

    print("=== Config check ===")
    if not problems and not warnings:
        print("Nothing looks wrong.")
    for p in problems:
        print(f"[BROKEN] {p}")
    for w in warnings:
        print(f"[WARN]   {w}")


@app.cli.command("test-linkgen")
@click.option("--email", required=True, help="Ticketing account email or Supporter ID")
@click.option("--password", required=True, help="Ticketing account password")
@click.option("--match-name", required=True, help='Exact match name, e.g. "Manchester United v Everton"')
@click.option("--proxy", default=None, help="Optional proxy, e.g. user:pass@host:port")
def test_linkgen(email, password, match_name, proxy):
    """One-off real call to LINKGEN_API_URL, using the exact same request/
    response code (app/utils/linkgen.py) that /api/generate-link uses in
    production - no credits touched, nothing written to the database. Run
    this against your real LINKGEN_API_URL/LINKGEN_API_KEY before going
    live, to confirm the real API is reachable and its response actually
    parses the way this app expects.
    Run with: flask --app wsgi.py test-linkgen --email ACCOUNT --password PASS --match-name "Manchester United v Everton" """
    with app.app_context():
        payload = {"email": email, "password": password, "match_name": match_name, "proxy": proxy}
        print(f"Calling {app.config['LINKGEN_API_URL']} ...")
        result = call_link_generation_api(payload, app.config)
        print(f"success:     {result.success}")
        print(f"link:        {result.link}")
        print(f"match_name:  {result.match_name}")
        print(f"event_date:  {result.event_date}")
        print(f"raw response: {result.raw}")


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=int(os.environ.get("PORT", 3001)))
