"""Ρυθμίσεις βάσης δεδομένων — διαβάζονται από environment variables."""
import os


def get_database_url() -> str:
    """Επιστρέφει το DATABASE_URL, διορθωμένο για SQLAlchemy 2.x.

    Το Render δίνει 'postgres://...' αλλά η SQLAlchemy θέλει 'postgresql://...'.
    """
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url
