import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Match, User, Ticket
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
    """Add Manchester United's 2026/27 season HOME fixtures (all competitions,
    Old Trafford only - away games aren't sold through this platform) as
    upcoming matches. Safe to re-run - skips any fixture already present for
    the same opponent/kickoff. Times are UK local, converted from the US
    broadcast times published by ESPN.
    Run with: flask --app wsgi.py add-manutd-fixtures"""
    # (away_team, kickoff_at) - home_team is always Manchester United
    home_fixtures = [
        ("Everton", datetime(2026, 9, 6, 14, 0)),
        ("Brighton & Hove Albion", datetime(2026, 9, 16, 20, 0)),
        ("Tottenham Hotspur", datetime(2026, 10, 10, 17, 30)),
        ("AFC Bournemouth", datetime(2026, 10, 25, 15, 0)),
        ("AS Roma", datetime(2026, 11, 3, 20, 0)),
        ("Aston Villa", datetime(2026, 11, 7, 15, 0)),
        ("Brentford", datetime(2026, 11, 28, 15, 0)),
        ("Coventry City", datetime(2026, 12, 5, 15, 0)),
        ("RB Leipzig", datetime(2026, 12, 8, 20, 0)),
        ("Nottingham Forest", datetime(2026, 12, 26, 15, 0)),
        ("Sunderland", datetime(2026, 12, 30, 20, 0)),
        ("Newcastle United", datetime(2027, 1, 6, 20, 0)),
        ("Bayern Munich", datetime(2027, 1, 20, 20, 0)),
        ("Liverpool", datetime(2027, 1, 23, 15, 0)),
        ("Chelsea", datetime(2027, 2, 6, 15, 0)),
        ("Brighton & Hove Albion", datetime(2027, 2, 10, 20, 0)),
        ("Arsenal", datetime(2027, 2, 27, 15, 0)),
        ("Everton", datetime(2027, 3, 13, 15, 0)),
        ("Hull City", datetime(2027, 4, 10, 15, 0)),
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


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=int(os.environ.get("PORT", 3001)))
