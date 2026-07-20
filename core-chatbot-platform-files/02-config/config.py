"""Κεντρικές ρυθμίσεις πλατφόρμας — όλα από environment variables.

Φορτώνεται από το 03-backend/app.py με importlib ως module 'platform_config'
(για να ΜΗ συγκρούεται με το package 01-data-layer/config/).
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    API_KEY = os.environ.get("API_KEY", "")  # για τα /admin endpoints

    CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

    # Κάτω από αυτό το similarity η απάντηση μαρκάρεται is_unanswered=True
    CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.35"))

    # RAG
    RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "4"))
    CONTEXT_CHUNK_MAX_CHARS = int(os.environ.get("CONTEXT_CHUNK_MAX_CHARS", "900"))
    HISTORY_MAX_MESSAGES = int(os.environ.get("HISTORY_MAX_MESSAGES", "6"))

    # Rate limiting (αιτήματα ανά λεπτό ανά IP)
    RATE_LIMIT_CHAT = int(os.environ.get("RATE_LIMIT_CHAT", "20"))
    RATE_LIMIT_LEAD = int(os.environ.get("RATE_LIMIT_LEAD", "5"))

    @classmethod
    def missing_required(cls):
        """Λίστα με τα υποχρεωτικά env vars που λείπουν."""
        required = ["DATABASE_URL", "OPENAI_API_KEY", "API_KEY"]
        return [name for name in required if not getattr(cls, name)]
