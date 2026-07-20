"""Ομοιόμορφες JSON απαντήσεις σφαλμάτων — ποτέ HTML error pages στο API."""
import logging

from flask import jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Δεν βρέθηκε"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Μη επιτρεπτή μέθοδος"}), 405

    @app.errorhandler(Exception)
    def internal_error(e):
        logger.exception("Απρόσμενο σφάλμα")
        return jsonify({"error": "Εσωτερικό σφάλμα — δοκιμάστε ξανά."}), 500
