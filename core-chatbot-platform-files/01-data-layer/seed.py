"""Δημιουργεί/ενημερώνει τον demo πελάτη 'demo' για δοκιμές.

Χρήση:  python seed.py   (ή μέσω POST /api/v1/admin/setup που τον καλεί)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.database import db_session
from models import Client, ClientSettings

DEMO_CLIENT_ID = "demo"


def run():
    with db_session() as db:
        client = db.query(Client).filter_by(client_id=DEMO_CLIENT_ID).first()
        if client is None:
            client = Client(client_id=DEMO_CLIENT_ID, name="Demo Πελάτης",
                            allowed_domain="", is_active=True)
            db.add(client)

        settings = db.query(ClientSettings).filter_by(client_id=DEMO_CLIENT_ID).first()
        if settings is None:
            settings = ClientSettings(client_id=DEMO_CLIENT_ID)
            db.add(settings)

        settings.system_prompt = (
            "Είσαι ο ψηφιακός βοηθός μιας ελληνικής επιχείρησης. "
            "Απαντάς σύντομα, ευγενικά και στα ελληνικά."
        )
        settings.welcome_message = "Γεια σας! Πώς μπορώ να βοηθήσω;"
        settings.primary_color = "#2563eb"
        settings.feature_flags = {"leads": True, "escalation": False}
        settings.crawl_urls = []
        settings.crawl_frequency = "manual"

    print(f"OK: πελάτης '{DEMO_CLIENT_ID}' και settings έτοιμα.")


if __name__ == "__main__":
    run()
