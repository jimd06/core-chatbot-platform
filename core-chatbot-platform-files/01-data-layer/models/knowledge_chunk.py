"""Κομμάτι γνώσης με embedding — η "μνήμη" του RAG ανά πελάτη.

ΠΡΟΣΟΧΗ: το attribute λέγεται chunk_metadata (ΟΧΙ metadata) —
το 'metadata' είναι δεσμευμένο όνομα στη SQLAlchemy.
"""
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base

EMBEDDING_DIM = 1536  # text-embedding-3-small


class KnowledgeChunk(Base):
    __tablename__ = "cp_knowledge_chunks"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_metadata = Column(JSONB, default=dict)
    source_url = Column(String(512), default="")
    # hash του περιεχομένου — για να ΜΗΝ ξαναφτιάχνουμε embeddings
    # σε αμετάβλητο περιεχόμενο (Φάση 4, cron re-crawl)
    content_hash = Column(String(64), default="", index=True)
    embedding = Column(Vector(EMBEDDING_DIM))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
