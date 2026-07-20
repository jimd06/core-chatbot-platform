"""Πελάτης της πλατφόρμας (μία επιχείρηση = μία εγγραφή)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from config.database import Base


class Client(Base):
    __tablename__ = "cp_clients"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), unique=True, nullable=False, index=True)  # π.χ. "palatino"
    name = Column(String(255), nullable=False)
    # Domain όπου επιτρέπεται το widget. Δέχεται wildcard: "*.example.gr".
    # Κενό = επιτρέπονται όλα (μόνο για δοκιμές).
    allowed_domain = Column(String(255), default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
