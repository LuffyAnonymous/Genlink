"""
Minimal standalone Flask + SQLAlchemy setup so LinkGeni.py can import
`app`, `db`, `Ticket` on its own (it's a separate service, not part of the
main Genlinklab Flask app). Points at the same database and the same
`tickets` table schema as the main app's Ticket model.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    id_unique = db.Column(db.String(255), unique=True, nullable=False, index=True)
    supporter_id = db.Column(db.String(100))
    event_name = db.Column(db.String(255))
    event_date = db.Column(db.String(20))
    area_name = db.Column(db.String(255))
    row_name = db.Column(db.String(255))
    seat_name = db.Column(db.String(255))
    nfc = db.Column(db.String(255))
    owner_name = db.Column(db.String(255))
