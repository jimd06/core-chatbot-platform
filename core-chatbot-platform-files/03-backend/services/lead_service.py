"""Αποθήκευση leads ανά πελάτη."""
from config.database import db_session
from models import Lead


def create_lead(client_id: str, name: str, email: str, phone: str, message: str) -> int:
    with db_session() as db:
        lead = Lead(client_id=client_id, name=name, email=email,
                    phone=phone, message=message)
        db.add(lead)
        db.flush()
        return lead.id
