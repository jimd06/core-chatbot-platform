"""Chat endpoint με CORS ανά πελάτη (allowed_domain + wildcard) και GDPR delete."""
from flask import Blueprint, jsonify, request

from middleware.rate_limiter import rate_limit
from platform_config import Config
from services.chat_service import answer, delete_visitor_data, load_client
from utils.validators import clean_str, origin_allowed

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1/chat")


def _with_cors(response, origin):
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, DELETE, OPTIONS"
    return response


def _check_client_and_origin(client_id):
    """Επιστρέφει (client_dict, origin, error_response)."""
    origin = request.headers.get("Origin", "")
    client = load_client(client_id)
    if client is None:
        return None, origin, (jsonify({"error": "Άγνωστος πελάτης"}), 404)
    if not origin_allowed(origin, client["allowed_domain"]):
        return None, origin, (jsonify({"error": "Μη επιτρεπτό domain"}), 403)
    return client, origin, None


@chat_bp.route("/<client_id>", methods=["OPTIONS"])
@chat_bp.route("/<client_id>/visitor/<visitor_id>", methods=["OPTIONS"])
def preflight(client_id, visitor_id=None):
    client, origin, error = _check_client_and_origin(client_id)
    if error:
        return error
    return _with_cors(jsonify({}), origin), 204


@chat_bp.post("/<client_id>")
@rate_limit(Config.RATE_LIMIT_CHAT)
def chat(client_id):
    client, origin, error = _check_client_and_origin(client_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    message = clean_str(data.get("message"), max_len=2000)
    if not message:
        return _with_cors(jsonify({"error": "Κενό μήνυμα"}), origin), 400

    result = answer(
        client_id=client_id,
        message=message,
        conversation_id=clean_str(data.get("conversation_id"), 64) or None,
        visitor_id=clean_str(data.get("visitor_id"), 64) or "anonymous",
    )
    return _with_cors(jsonify(result), origin), 200


@chat_bp.delete("/<client_id>/visitor/<visitor_id>")
@rate_limit(Config.RATE_LIMIT_LEAD)
def gdpr_delete(client_id, visitor_id):
    """GDPR: ο επισκέπτης διαγράφει όλα τα δεδομένα συνομιλιών του."""
    client, origin, error = _check_client_and_origin(client_id)
    if error:
        return error
    deleted = delete_visitor_data(client_id, clean_str(visitor_id, 64))
    return _with_cors(jsonify({"deleted_conversations": deleted}), origin), 200
