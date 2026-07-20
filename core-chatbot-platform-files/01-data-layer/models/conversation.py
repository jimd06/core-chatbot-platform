"""Συνομιλία επισκέπτη με το chatbot ενός πελάτη."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String

from config.database import Base


class Conversation(Base):
    __tablename__ = "cp_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(64), nullable=False, index=True)
    # visitor_id: ανώνυμο id που κρατάει το widget — χρειάζεται για το GDPR delete
    visitor_id = Column(String(64), nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
