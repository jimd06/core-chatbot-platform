"""Μήνυμα μέσα σε συνομιλία (user ή assistant)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from config.database import Base


class Message(Base):
    __tablename__ = "cp_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(36), ForeignKey("cp_conversations.id"),
                             nullable=False, index=True)
    role = Column(String(16), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    # Μόνο για assistant μηνύματα:
    confidence = Column(Float, nullable=True)
    is_unanswered = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
