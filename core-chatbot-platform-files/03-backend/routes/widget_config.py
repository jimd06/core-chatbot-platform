"""Δημόσιο configuration εμφάνισης του widget (χρώματα, welcome, logo)."""
from flask import Blueprint, jsonify, request

from services.widget_service import get_widget_config

widget_config_bp = Blueprint("widget_config", __name__, url_prefix="/api/v1/widget")


@widget_config_bp.get("/<client_id>/config")
def widget_config(client_id):
    config = get_widget_config(client_id)
    if config is None:
        return jsonify({"error": "Άγνωστος πελάτης"}), 404
    resp = jsonify(config)
    # Το config είναι δημόσιο (χρώματα/κείμενα) — ανοιχτό CORS για εύκολη φόρτωση.
    origin = request.headers.get("Origin", "")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    return resp, 200
