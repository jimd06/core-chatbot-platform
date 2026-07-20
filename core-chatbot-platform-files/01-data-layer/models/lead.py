"""Lead (ενδιαφερόμενος) που άφησε στοιχεία μέσω του widget."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from config.database import Base


class Lead(Base):
    __tablename__ = "cp_leads"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), default="")
    email = Column(String(255), default="")
    phone = Column(String(64), default="")
    message = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
