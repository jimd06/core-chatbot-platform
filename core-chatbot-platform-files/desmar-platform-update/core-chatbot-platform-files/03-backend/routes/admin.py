"""Admin endpoints (μόνο με X-API-Key):
- POST /api/v1/admin/setup      → pgvector extension + πίνακες cp_* + demo πελάτης
                                  + idempotent migrations (νέες στήλες)
- POST /api/v1/admin/client     → δημιουργία/ενημέρωση πελάτη (ίδιο JSON με το
                                  05-onboarding/seed_new_client.py) — για δουλειά
                                  μόνο από browser, χωρίς τοπικό περιβάλλον
- POST /api/v1/admin/knowledge  → φόρτωση γνώσης με embeddings για έναν client_id
- GET  /api/v1/admin/leads      → λίστα leads ενός πελάτη (έλεγχος χωρίς psql)
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from config.database import Base, db_session, get_engine
from middleware.auth import require_admin_key
from models import Client, ClientSettings, KnowledgeChunk, Lead, UsageLog
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

    # Idempotent migrations: το create_all ΔΕΝ προσθέτει στήλες σε πίνακες
    # που υπάρχουν ήδη — τις προσθέτουμε εδώ, ακίνδυνα και όσες φορές τρέξει.
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE cp_leads ADD COLUMN IF NOT EXISTS extra_data JSONB"))
        conn.commit()

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
                    "message": "Extension, πίνακες cp_*, στήλη extra_data και "
                               "demo πελάτης έτοιμα."}), 200


# --- POST /client: ίδια λογική/ίδιο JSON με το seed_new_client.py ------------

def _as_list(value) -> list:
    """forbidden_topics: δέχεται λίστα ή string με κόμματα."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _as_dict(value) -> dict:
    """escalation_rules: δέχεται dict ή string (→ {"note": ...})."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    return {"note": str(value)}


def _build_system_prompt(data: dict, name: str, forbidden: list) -> str:
    """Ίδια σύνθεση με το seed_new_client.py — εκτός αν δίνεται έτοιμο system_prompt."""
    if data.get("system_prompt"):
        return data["system_prompt"]

    parts = [
        f"Είσαι ο ψηφιακός βοηθός της επιχείρησης «{name}».",
    ]
    if data.get("persona"):
        parts.append(f"Προσωπικότητα/ύφος: {data['persona']}")
    if data.get("business_description"):
        parts.append(f"Η επιχείρηση: {data['business_description']}")
    if data.get("out_of_scope"):
        parts.append(
            "Εκτός αρμοδιότητας: " + data["out_of_scope"] +
            " Αν σε ρωτήσουν κάτι τέτοιο, απάντησε ευγενικά ότι δεν μπορείς να βοηθήσεις σε αυτό."
        )
    if forbidden:
        parts.append("ΑΠΑΓΟΡΕΥΜΕΝΑ θέματα (μην απαντάς ποτέ): " + ", ".join(forbidden))
    parts.append(
        "Απαντάς ΜΟΝΟ με βάση τις πληροφορίες που σου δίνονται. "
        "Αν δεν γνωρίζεις την απάντηση, το λες ευγενικά και προτείνεις επικοινωνία με την επιχείρηση."
    )
    return "\n".join(parts)


@admin_bp.post("/client")
@require_admin_key
def upsert_client():
    """Δημιουργία/ενημέρωση Client + ClientSettings από το JSON ερωτηματολογίου.

    Body: ίδια μορφή με το 05-onboarding/seed_new_client.py (βλ.
    client_desmar.json). Άγνωστα πεδία (π.χ. "_future_...", "_σημείωση")
    αγνοούνται — έτσι το JSON μπορεί να κουβαλά και «σχολιασμένες» τιμές.
    """
    data = request.get_json(silent=True) or {}
    client_id = clean_str(data.get("client_id"), 64)
    name = clean_str(data.get("name"), 255)
    if not client_id or not name:
        return jsonify({"error": "Χρειάζονται client_id και name"}), 400

    forbidden = _as_list(data.get("forbidden_topics"))
    escalation = _as_dict(data.get("escalation_rules"))
    system_prompt = _build_system_prompt(data, name, forbidden)

    feature_flags = data.get("feature_flags")
    crawl_urls = data.get("crawl_urls")

    with db_session() as db:
        client = db.query(Client).filter_by(client_id=client_id).first()
        created = client is None
        if created:
            client = Client(client_id=client_id, name=name)
            db.add(client)
        client.name = name
        client.allowed_domain = clean_str(data.get("allowed_domain"), 255)
        client.is_active = True

        settings = db.query(ClientSettings).filter_by(client_id=client_id).first()
        if settings is None:
            settings = ClientSettings(client_id=client_id)
            db.add(settings)

        settings.system_prompt = system_prompt
        settings.welcome_message = (data.get("welcome_message") or
                                    "Γεια σας! Πώς μπορώ να βοηθήσω;")
        if data.get("out_of_scope_message"):
            settings.out_of_scope_message = data["out_of_scope_message"]
        settings.forbidden_topics = forbidden
        settings.escalation_rules = escalation
        settings.notification_email = clean_str(data.get("notification_email"), 255)
        settings.primary_color = clean_str(data.get("primary_color"), 16) or "#2563eb"
        settings.logo_url = clean_str(data.get("logo_url"), 512)
        settings.feature_flags = feature_flags if isinstance(feature_flags, dict) else {}
        settings.crawl_urls = crawl_urls if isinstance(crawl_urls, list) else []
        settings.crawl_frequency = clean_str(data.get("crawl_frequency"), 32) or "manual"

    return jsonify({"ok": True, "client_id": client_id,
                    "created": created}), (201 if created else 200)


@admin_bp.get("/leads")
@require_admin_key
def list_leads():
    """Λίστα leads ενός πελάτη, νεότερα πρώτα — έλεγχος leads/utm χωρίς psql.

    GET /api/v1/admin/leads?client_id=desmar&limit=50   (limit: 1–200)
    """
    client_id = clean_str(request.args.get("client_id"), 64)
    if not client_id:
        return jsonify({"error": "Χρειάζεται client_id (π.χ. ?client_id=desmar)"}), 400
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    except (TypeError, ValueError):
        limit = 50

    with db_session() as db:
        rows = (db.query(Lead).filter_by(client_id=client_id)
                  .order_by(Lead.id.desc()).limit(limit).all())
        leads = [{
            "id": lead.id,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "message": lead.message,
            "extra_data": lead.extra_data or {},
        } for lead in rows]

    return jsonify({"client_id": client_id, "count": len(leads), "leads": leads}), 200


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
