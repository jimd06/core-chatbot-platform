#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_new_client.py — Το «εργοστάσιο πελατών», βήμα 1.

Παίρνει ένα JSON αρχείο με τις απαντήσεις του ερωτηματολογίου ενός πελάτη
και δημιουργεί (ή ενημερώνει) Client + ClientSettings, χρησιμοποιώντας τα
models του 01-data-layer (πίνακες cp_clients / cp_client_settings).

Χρήση (από τον φάκελο 05-onboarding ή από τη ρίζα του repo):
    python 05-onboarding/seed_new_client.py 05-onboarding/demo_client_komotirio.json

Απαιτεί environment variable: DATABASE_URL

Μορφή JSON: δες demo_client_komotirio.json. Σημείωση:
    - forbidden_topics: λίστα, π.χ. ["πολιτική", "θρησκεία"]
      (αν δοθεί string, χωρίζεται αυτόματα στα κόμματα)
    - escalation_rules: dict, π.χ. {"keywords": ["ραντεβού"], "note": "..."}
      (αν δοθεί string, γίνεται {"note": "..."})
"""

import json
import os
import sys

# --- sys.path: ίδιο pattern με seed.py / app.py ------------------------------
ONBOARDING_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ONBOARDING_DIR)
DATA_LAYER = os.path.join(REPO_ROOT, "01-data-layer")
if DATA_LAYER not in sys.path:
    sys.path.insert(0, DATA_LAYER)
# ----------------------------------------------------------------------------

from config.database import db_session
from models import Client, ClientSettings

REQUIRED_FIELDS = ["client_id", "name"]


def as_list(value) -> list:
    """forbidden_topics: δέχεται λίστα ή string με κόμματα."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [part.strip() for part in str(value).split(",") if part.strip()]


def as_dict(value) -> dict:
    """escalation_rules: δέχεται dict ή string (→ {"note": ...})."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    return {"note": str(value)}


def build_system_prompt(data: dict, forbidden: list) -> str:
    """Συνθέτει το system_prompt από τις απαντήσεις του ερωτηματολογίου,
    εκτός αν δίνεται έτοιμο system_prompt στο JSON."""
    if data.get("system_prompt"):
        return data["system_prompt"]

    parts = [
        f"Είσαι ο ψηφιακός βοηθός της επιχείρησης «{data['name']}».",
    ]
    if data.get("persona"):
        parts.append(f"Προσωπικότητα/ύφος: {data['persona']}")
    if data.get("business_description"):
        parts.append(f"Η επιχείρηση: {data['business_description']}")
    if data.get("out_of_scope"):
        parts.append(
            "Εκτός αρμοδιότητας: " + data["out_of_scope"] +
            " Αν σε ρωτήσουν κάτι τέτοιο, απάντησε ευγενικά ότι δεν μπορείς να βοηθήσεις σε αυτό."
        )
    if forbidden:
        parts.append("ΑΠΑΓΟΡΕΥΜΕΝΑ θέματα (μην απαντάς ποτέ): " + ", ".join(forbidden))
    parts.append(
        "Απαντάς ΜΟΝΟ με βάση τις πληροφορίες που σου δίνονται. "
        "Αν δεν γνωρίζεις την απάντηση, το λες ευγενικά και προτείνεις επικοινωνία με την επιχείρηση."
    )
    return "\n".join(parts)


def main() -> None:
    if len(sys.argv) != 2:
        print("Χρήση: python seed_new_client.py <questionnaire.json>")
        sys.exit(1)

    if not os.environ.get("DATABASE_URL"):
        print("ΣΦΑΛΜΑ: Δεν βρέθηκε το DATABASE_URL στο περιβάλλον.")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    for field in REQUIRED_FIELDS:
        if not data.get(field):
            print(f"ΣΦΑΛΜΑ: Λείπει το υποχρεωτικό πεδίο «{field}» από το JSON.")
            sys.exit(1)

    forbidden = as_list(data.get("forbidden_topics"))
    escalation = as_dict(data.get("escalation_rules"))
    system_prompt = build_system_prompt(data, forbidden)

    with db_session() as db:
        client = db.query(Client).filter_by(client_id=data["client_id"]).first()
        if client is None:
            client = Client(client_id=data["client_id"], name=data["name"])
            db.add(client)
        client.name = data["name"]
        client.allowed_domain = data.get("allowed_domain", "")
        client.is_active = True

        settings = db.query(ClientSettings).filter_by(client_id=data["client_id"]).first()
        if settings is None:
            settings = ClientSettings(client_id=data["client_id"])
            db.add(settings)

        settings.system_prompt = system_prompt
        settings.welcome_message = data.get(
            "welcome_message", "Γεια σας! Πώς μπορώ να βοηθήσω;"
        )
        if data.get("out_of_scope_message"):
            settings.out_of_scope_message = data["out_of_scope_message"]
        settings.forbidden_topics = forbidden
        settings.escalation_rules = escalation
        settings.notification_email = data.get("notification_email", "")
        settings.primary_color = data.get("primary_color", "#2563eb")
        settings.logo_url = data.get("logo_url") or ""
        settings.feature_flags = data.get("feature_flags", {})
        settings.crawl_urls = data.get("crawl_urls", [])
        settings.crawl_frequency = data.get("crawl_frequency", "manual")

    print(f"✅ Ο πελάτης «{data['name']}» ({data['client_id']}) δημιουργήθηκε/ενημερώθηκε.")
    print("Επόμενο βήμα: python 05-onboarding/ingest_content.py --client", data["client_id"])


if __name__ == "__main__":
    main()
