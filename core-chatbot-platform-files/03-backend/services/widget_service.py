"""Configuration εμφάνισης του widget ανά πελάτη."""
from config.database import db_session
from models import Client, ClientSettings


def get_widget_config(client_id: str):
    """Επιστρέφει dict με τα δημόσια στοιχεία εμφάνισης, ή None αν δεν υπάρχει."""
    with db_session() as db:
        client = db.query(Client).filter_by(client_id=client_id, is_active=True).first()
        if client is None:
            return None
        s = db.query(ClientSettings).filter_by(client_id=client_id).first()
        return {
            "client_id": client_id,
            "name": client.name,
            "primary_color": (s.primary_color if s else "") or "#2563eb",
            "logo_url": (s.logo_url if s else "") or "",
            "welcome_message": (s.welcome_message if s else "") or "Γεια σας!",
            "feature_flags": dict(s.feature_flags or {}) if s else {},
        }
