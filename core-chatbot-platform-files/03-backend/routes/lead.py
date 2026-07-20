"""Φόρμα lead με honeypot πεδίο 'website' — τα bots το συμπληρώνουν, οι άνθρωποι όχι."""
from flask import Blueprint, jsonify, request

from middleware.rate_limiter import rate_limit
from platform_config import Config
from services.chat_service import load_client
from services.lead_service import create_lead
from utils.validators import clean_str, origin_allowed, valid_email

lead_bp = Blueprint("lead", __name__, url_prefix="/api/v1/lead")


@lead_bp.post("/<client_id>")
@rate_limit(Config.RATE_LIMIT_LEAD)
def submit_lead(client_id):
    origin = request.headers.get("Origin", "")
    client = load_client(client_id)
    if client is None:
        return jsonify({"error": "Άγνωστος πελάτης"}), 404
    if not origin_allowed(origin, client["allowed_domain"]):
        return jsonify({"error": "Μη επιτρεπτό domain"}), 403

    data = request.get_json(silent=True) or {}

    # Honeypot: αν το κρυφό πεδίο έχει τιμή → bot. Απαντάμε "ok" χωρίς αποθήκευση.
    if clean_str(data.get("website"), 200):
        return jsonify({"ok": True}), 200

    name = clean_str(data.get("name"), 255)
    email = clean_str(data.get("email"), 255)
    phone = clean_str(data.get("phone"), 64)
    message = clean_str(data.get("message"), 2000)

    if not (email or phone):
        return jsonify({"error": "Χρειάζεται email ή τηλέφωνο"}), 400
    if email and not valid_email(email):
        return jsonify({"error": "Μη έγκυρο email"}), 400

    lead_id = create_lead(client_id, name, email, phone, message)
    resp = jsonify({"ok": True, "lead_id": lead_id})
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    return resp, 201
