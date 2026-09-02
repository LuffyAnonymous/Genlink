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


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=int(os.environ.get("PORT", 3001)))
