"""Καταγραφή κατανάλωσης OpenAI ανά πελάτη — η βάση της τιμολόγησης."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from config.database import Base


class UsageLog(Base):
    __tablename__ = "cp_usage_logs"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=False, index=True)
    kind = Column(String(32), nullable=False)   # "chat" | "embedding"
    model = Column(String(64), default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
