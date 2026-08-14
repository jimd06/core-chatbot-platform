"""Lead (ενδιαφερόμενος) που άφησε στοιχεία μέσω του widget ή της φόρμας του site."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base


class Lead(Base):
    __tablename__ = "cp_leads"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), default="")
    email = Column(String(255), default="")
    phone = Column(String(64), default="")
    message = Column(Text, default="")
    # Πρόσθετα πεδία ανά πηγή lead (π.χ. φόρμα site: industry, site_url,
    # utm_source, utm_medium, utm_campaign). JSONB — ίδιο pattern με το
    # feature_flags του client_settings. Η στήλη προστίθεται σε υπάρχουσα
    # βάση με το idempotent ALTER μέσα στο POST /api/v1/admin/setup.
    extra_data = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
