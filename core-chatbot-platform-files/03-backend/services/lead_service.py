"""Αποθήκευση leads ανά πελάτη + άντληση email ειδοποίησης από τα settings."""
from config.database import db_session
from models import ClientSettings, Lead


def create_lead(client_id: str, name: str, email: str, phone: str,
                message: str, extra_data: dict | None = None) -> int:
    with db_session() as db:
        lead = Lead(client_id=client_id, name=name, email=email,
                    phone=phone, message=message, extra_data=extra_data or {})
        db.add(lead)
        db.flush()
        return lead.id


def get_notification_email(client_id: str) -> str:
    """Ο παραλήπτης ειδοποιήσεων του πελάτη (κενό string = δεν έχει οριστεί).

    Καλείται μέσα στο request, ΠΡΙΝ από το background thread του notify_service —
    το thread δεν αγγίζει ποτέ τη βάση.
    """
    with db_session() as db:
        settings = db.query(ClientSettings).filter_by(client_id=client_id).first()
        return (settings.notification_email or "") if settings else ""
