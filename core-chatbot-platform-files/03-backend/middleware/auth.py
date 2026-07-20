"""Προστασία των /admin endpoints με το API_KEY (header X-API-Key)."""
from functools import wraps

from flask import jsonify, request

from platform_config import Config


def require_admin_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not Config.API_KEY or key != Config.API_KEY:
            return jsonify({"error": "Μη έγκυρο ή ελλιπές X-API-Key"}), 401
        return fn(*args, **kwargs)
    return wrapper
