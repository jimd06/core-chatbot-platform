"""Φόρμα lead (site + widget) με honeypot, CORS ανά πελάτη και email ειδοποίηση.

- Honeypot πεδίο 'website': τα bots το συμπληρώνουν, οι άνθρωποι όχι.
- OPTIONS preflight: η φόρμα στέλνει JSON από άλλο origin, άρα ο browser
  κάνει ΠΑΝΤΑ preflight πριν το POST — ίδιο pattern με το chat.py.
- Δέχεται και τα πεδία της φόρμας του site desmar: business_name (→ στήλη
  name), industry, site_url, utm_source/medium/campaign → αποθηκεύονται
  στο Lead.extra_data (JSONB). Το client_id έρχεται από το URL — τυχόν
  client_id μέσα στο body αγνοείται.
- Μετά την αποθήκευση: best-effort email ειδοποίηση στο notification_email
  του πελάτη (services/notify_service.py) — ποτέ δεν μπλοκάρει το request.
"""
from flask import Blueprint, jsonify, request

from middleware.rate_limiter import rate_limit
from platform_config import Config
from services.chat_service import load_client
from services.lead_service import create_lead, get_notification_email
from services.notify_service import send_async
from utils.validators import clean_str, origin_allowed, valid_email

lead_bp = Blueprint("lead", __name__, url_prefix="/api/v1/lead")

# Πεδία της φόρμας του site που πάνε στο extra_data (JSONB).
EXTRA_FIELDS = ("industry", "site_url", "utm_source", "utm_medium", "utm_campaign")


def _with_cors(response, origin):
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def _check_client_and_origin(client_id):
    """Επιστρέφει (client_dict, origin, error_response) — ίδιο pattern με chat.py."""
    origin = request.headers.get("Origin", "")
    client = load_client(client_id)
    if client is None:
        return None, origin, (jsonify({"error": "Άγνωστος πελάτης"}), 404)
    if not origin_allowed(origin, client["allowed_domain"]):
        return None, origin, (jsonify({"error": "Μη επιτρεπτό domain"}), 403)
    return client, origin, None


@lead_bp.route("/<client_id>", methods=["OPTIONS"])
def preflight(client_id):
    client, origin, error = _check_client_and_origin(client_id)
    if error:
        return error
    return _with_cors(jsonify({}), origin), 204


@lead_bp.post("/<client_id>")
@rate_limit(Config.RATE_LIMIT_LEAD)
def submit_lead(client_id):
    client, origin, error = _check_client_and_origin(client_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}

    # Honeypot: αν το κρυφό πεδίο έχει τιμή → bot. Απαντάμε "ok" χωρίς αποθήκευση.
    if clean_str(data.get("website"), 200):
        return _with_cors(jsonify({"ok": True}), origin), 200

    # business_name (φόρμα site) ή name (widget/άλλες πηγές) → στήλη name.
    name = clean_str(data.get("name") or data.get("business_name"), 255)
    email = clean_str(data.get("email"), 255)
    phone = clean_str(data.get("phone"), 64)
    message = clean_str(data.get("message"), 2000)

    extra_data = {}
    for field in EXTRA_FIELDS:
        value = clean_str(data.get(field), 512)
        if value:
            extra_data[field] = value

    if not (email or phone):
        return _with_cors(jsonify({"error": "Χρειάζεται email ή τηλέφωνο"}), origin), 400
    if email and not valid_email(email):
        return _with_cors(jsonify({"error": "Μη έγκυρο email"}), origin), 400

    lead_id = create_lead(client_id, name, email, phone, message, extra_data)

    # Ειδοποίηση email (best-effort, background) στο notification_email του πελάτη.
    recipient = get_notification_email(client_id)
    if recipient:
        lines = [f"Νέο lead #{lead_id} για τον πελάτη «{client_id}»", ""]
        if name:
            lines.append(f"Επωνυμία/Όνομα: {name}")
        if email:
            lines.append(f"Email: {email}")
        if phone:
            lines.append(f"Τηλέφωνο: {phone}")
        if message:
            lines.append(f"Μήνυμα: {message}")
        for field in EXTRA_FIELDS:
            if extra_data.get(field):
                lines.append(f"{field}: {extra_data[field]}")
        send_async(recipient,
                   f"Νέο lead — {name or email or phone}",
                   "\n".join(lines))

    return _with_cors(jsonify({"ok": True, "lead_id": lead_id}), origin), 201
