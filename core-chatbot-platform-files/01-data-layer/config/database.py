"""Σύνδεση SQLAlchemy με την PostgreSQL (dentalpoint-db στο Render)."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import get_database_url

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            pool_pre_ping=True,   # ζωντανεύει "κοιμισμένες" συνδέσεις του Render
            pool_size=5,
            max_overflow=5,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def db_session():
    """Context manager: άνοιγμα/commit/rollback/κλείσιμο session.

    ΠΡΟΣΟΧΗ: ό,τι επιστρέφεις έξω από το `with` πρέπει να είναι απλά δεδομένα
    (str, dict, λίστες) — ΟΧΙ ORM αντικείμενα, αλλιώς: 'Instance not bound
    to a Session'.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
