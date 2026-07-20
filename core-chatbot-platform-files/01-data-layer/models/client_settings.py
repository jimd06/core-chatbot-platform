"""Ό,τι διαφέρει ανά πελάτη — ύφος, εμφάνιση, guardrails, escalation, crawling."""
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base


class ClientSettings(Base):
    __tablename__ = "cp_client_settings"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), ForeignKey("cp_clients.client_id"),
                       unique=True, nullable=False, index=True)

    # Πώς μιλάει το bot
    system_prompt = Column(Text, default="")
    welcome_message = Column(Text, default="Γεια σας! Πώς μπορώ να βοηθήσω;")
    out_of_scope_message = Column(
        Text,
        default="Δεν έχω αυτή την πληροφορία. Θέλετε να αφήσετε τα στοιχεία σας για να επικοινωνήσουμε μαζί σας;",
    )

    # Guardrails
    forbidden_topics = Column(JSONB, default=list)      # π.χ. ["ιατρικές διαγνώσεις"]

    # Escalation (Φάση 5 — τα πεδία υπάρχουν από τώρα)
    escalation_rules = Column(JSONB, default=dict)
    notification_email = Column(String(255), default="")

    # Εμφάνιση widget
    primary_color = Column(String(16), default="#2563eb")
    logo_url = Column(String(512), default="")

    # Feature flags — π.χ. {"leads": true, "escalation": false}
    feature_flags = Column(JSONB, default=dict)

    # Αυτόματη ενημέρωση γνώσης από το site του πελάτη (Φάση 4)
    crawl_urls = Column(JSONB, default=list)            # λίστα URLs
    crawl_frequency = Column(String(32), default="manual")  # manual | daily | weekly
