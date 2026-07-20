"""Admin endpoints (μόνο με X-API-Key):
- POST /api/v1/admin/setup      → pgvector extension + πίνακες cp_* + demo πελάτης
- POST /api/v1/admin/knowledge  → φόρτωση γνώσης με embeddings για έναν client_id
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from config.database import Base, db_session, get_engine
from middleware.auth import require_admin_key
from models import Client, ClientSettings, KnowledgeChunk, UsageLog
from platform_config import Config
from utils.validators import clean_str

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


@admin_bp.post("/setup")
@require_admin_key
def setup():
    import models  # noqa: F401 — φορτώνει όλα τα models για το create_all

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)

    with db_session() as db:
        client = db.query(Client).filter_by(client_id="demo").first()
        if client is None:
            db.add(Client(client_id="demo", name="Demo Πελάτης",
                          allowed_domain="", is_active=True))
        settings = db.query(ClientSettings).filter_by(client_id="demo").first()
        if settings is None:
            db.add(ClientSettings(
                client_id="demo",
                system_prompt=("Είσαι ο ψηφιακός βοηθός μιας ελληνικής επιχείρησης. "
                               "Απαντάς σύντομα, ευγενικά και στα ελληνικά."),
                feature_flags={"leads": True, "escalation": False},
            ))

    return jsonify({"ok": True,
                    "message": "Extension, πίνακες cp_* και demo πελάτης έτοιμα."}), 200


@admin_bp.post("/knowledge")
@require_admin_key
def add_knowledge():
    """Body: {"client_id": "...", "clear": true|false,
              "chunks": [{"content": "...", "source_url": "..."}]}"""
    from openai import OpenAI

    data = request.get_json(silent=True) or {}
    client_id = clean_str(data.get("client_id"), 64)
    chunks = data.get("chunks") or []
    if not client_id or not isinstance(chunks, list) or not chunks:
        return jsonify({"error": "Χρειάζονται client_id και chunks (λίστα)"}), 400

    with db_session() as db:
        if db.query(Client).filter_by(client_id=client_id).first() is None:
            return jsonify({"error": f"Άγνωστος πελάτης '{client_id}'"}), 404

    texts = [clean_str(c.get("content"), 8000) for c in chunks if isinstance(c, dict)]
    texts = [t for t in texts if t]
    if not texts:
        return jsonify({"error": "Κανένα έγκυρο content στα chunks"}), 400

    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    resp = client.embeddings.create(model=Config.EMBEDDING_MODEL, input=texts)
    embeddings = [item.embedding for item in resp.data]
    tokens = resp.usage.total_tokens if resp.usage else 0

    with db_session() as db:
        if data.get("clear"):
            db.query(KnowledgeChunk).filter_by(client_id=client_id) \
                .delete(synchronize_session=False)
        for chunk, embedding in zip([c for c in chunks if isinstance(c, dict)
                                     and clean_str(c.get("content"), 8000)], embeddings):
            db.add(KnowledgeChunk(
                client_id=client_id,
                content=clean_str(chunk.get("content"), 8000),
                source_url=clean_str(chunk.get("source_url"), 512),
                embedding=embedding,
            ))
        db.add(UsageLog(client_id=client_id, kind="embedding",
                        model=Config.EMBEDDING_MODEL, total_tokens=tokens))

    return jsonify({"ok": True, "added": len(embeddings)}), 200
