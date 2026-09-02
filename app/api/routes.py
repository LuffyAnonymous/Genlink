from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.services.link_jobs import run_link_job

api_bp = Blueprint("api", __name__)


@api_bp.route("/generate-link", methods=["POST"])
@login_required
def generate_link():
    payload = request.get_json(silent=True) or {}

    if not payload.get("email") or not payload.get("password"):
        return jsonify({"success": False, "error": "missing_fields", "message": "Email and password are required."}), 400

    result = run_link_job(current_user.id, payload, current_app.config)

    if result["success"]:
        return jsonify(result), 200
    if result.get("error") == "insufficient_credits":
        return jsonify(result), 402
    return jsonify(result), 502


@api_bp.route("/credits/balance", methods=["GET"])
@login_required
def credits_balance():
    return jsonify({"credits": current_user.credits})
