"""Flask application factory — ο πυρήνας της πλατφόρμας.

Render Start Command:
    cd 03-backend && gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
"""
import importlib.util
import os
import sys

# --- Ρύθμιση sys.path -------------------------------------------------------
# 1) 01-data-layer στο path → δουλεύουν τα `from models import ...`
#    και `from config.database import ...` (το config/ package της βάσης).
# 2) Το 02-config/config.py φορτώνεται με importlib ως 'platform_config'
#    για να ΜΗ συγκρουστεί με το παραπάνω config/ package.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_LAYER = os.path.join(REPO_ROOT, "01-data-layer")
BACKEND = os.path.dirname(os.path.abspath(__file__))

for path in (DATA_LAYER, BACKEND):
    if path not in sys.path:
        sys.path.insert(0, path)

if "platform_config" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "platform_config", os.path.join(REPO_ROOT, "02-config", "config.py")
    )
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    sys.modules["platform_config"] = _module
# ----------------------------------------------------------------------------

from flask import Flask

from middleware.error_handler import register_error_handlers
from routes.admin import admin_bp
from routes.chat import chat_bp
from routes.demo import demo_bp
from routes.health import health_bp
from routes.lead import lead_bp
from routes.widget_config import widget_config_bp


def create_app():
    app = Flask(__name__)

    register_error_handlers(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(lead_bp)
    app.register_blueprint(widget_config_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(demo_bp)  # Φάση 3: /demo + /widget.js

    return app


if __name__ == "__main__":
    create_app().run(port=5000, debug=True)
