"""Admin endpoints (μόνο με X-API-Key):
- POST /api/v1/admin/setup      → pgvector extension + πίνακες cp_* + demo πελάτης
                                  + idempotent migrations (νέες στήλες)
- POST /api/v1/admin/client     → δημιουργία/ενημέρωση πελάτη (ίδιο JSON με το
                                  05-onboarding/seed_new_client.py) — για δουλειά
                                  μόνο από browser, χωρίς τοπικό περιβάλλον
- POST /api/v1/admin/knowledge  → φόρτωση γνώσης με embeddings για έναν client_id
- GET  /api/v1/admin/leads      → λίστα leads ενός πελάτη (έλεγχος χωρίς psql)
- POST /api/v1/admin/demo         → Demo-First: demo chatbot από site υποψήφιου
- GET  /api/v1/admin/demo/status  → πρόοδος/κατάσταση ενός demo
- POST /api/v1/admin/demo/cleanup → καθάρισμα ληγμένων demos (έτοιμο για Cron)
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


# ===========================================================================
# Demo-First (Chat 3): demo chatbot από το site υποψήφιου πελάτη
# ===========================================================================

def _load_make_demo():
    """Lazy import: το 05-onboarding μπαίνει στο sys.path από το app.py.
    Αν λείπει το αρχείο από το deploy (π.χ. μισό upload χωρίς Commit),
    σφάλμα ΜΟΝΟ στα demo endpoints — όχι σε όλη την πλατφόρμα."""
    import make_demo
    return make_demo


_MAKE_DEMO_MISSING = ("Λείπει το 05-onboarding/make_demo.py από το deploy — "
                      "έλεγξε ότι ανέβηκε ο φάκελος και πατήθηκε το Commit.")


@admin_bp.post("/demo")
@require_admin_key
def create_demo():
    """Δημιουργία demo με ΜΙΑ κλήση. Body:
    {site_url, business_name, industry, contact_email,
     answer_limit? (1-200, default 20), days? (1-30, default 7),
     client_id? (ΜΟΝΟ για επανεκκίνηση ingestion υπάρχοντος demo)}

    industry: iatreio | kommotirio | xenodocheio | gymnastirio | skafi | allo
    Guard: αν υπάρχει ήδη ΕΝΕΡΓΟ demo με ίδιο site_url → επιστρέφεται το
    υπάρχον (reused: true) — διπλό κλικ ΔΕΝ φτιάχνει δεύτερο client.
    """
    try:
        make_demo = _load_make_demo()
    except ImportError:
        return jsonify({"error": _MAKE_DEMO_MISSING}), 500

    data = request.get_json(silent=True) or {}

    # Πίσω από το Render proxy το host_url μπορεί να βγει http:// — για τα
    # links του email/demo θέλουμε https (εκτός από τοπικό τρέξιμο).
    base_url = request.host_url.rstrip("/")
    if base_url.startswith("http://") and "localhost" not in base_url \
            and "127.0.0.1" not in base_url:
        base_url = "https://" + base_url[len("http://"):]

    result = make_demo.create_demo(
        site_url=clean_str(data.get("site_url"), 512),
        business_name=clean_str(data.get("business_name"), 255),
        industry=clean_str(data.get("industry"), 32),
        contact_email=clean_str(data.get("contact_email"), 255),
        base_url=base_url,
        reuse_client_id=clean_str(data.get("client_id"), 64) or None,
        answer_limit=data.get("answer_limit"),
        days=data.get("days"),
    )
    return jsonify(result), (200 if result.get("ok") else 400)


@admin_bp.get("/demo/status")
@require_admin_key
def demo_status():
    """GET /api/v1/admin/demo/status?client_id=demo-xxxx-1a2b
    → status (pending/ingesting/ready/error/expired), σελίδες, chunks,
      απαντήσεις που απομένουν, λήξη."""
    try:
        make_demo = _load_make_demo()
    except ImportError:
        return jsonify({"error": _MAKE_DEMO_MISSING}), 500

    client_id = clean_str(request.args.get("client_id"), 64)
    if not client_id:
        return jsonify({"error": "Χρειάζεται client_id "
                                 "(π.χ. ?client_id=demo-x-1a2b)"}), 400
    state = make_demo.get_demo_state(client_id)
    if state is None:
        return jsonify({"error": f"Άγνωστος πελάτης '{client_id}'"}), 404
    return jsonify(state), 200


@admin_bp.post("/demo/cleanup")
@require_admin_key
def demo_cleanup():
    """Καθαρίζει ληγμένα demos: chunks + ingest hashes + συνομιλίες/μηνύματα,
    client → ανενεργός. ΚΡΑΤΑΕΙ client/settings (η σελίδα demo δείχνει
    «έληξε» + CTA) και ΟΛΑ τα usage_logs (ιστορικό κόστους demos ανά μήνα).

    Body (προαιρετικό): {"client_id": "demo-...", "force": true} → καθάρισμα
    ΣΥΓΚΕΚΡΙΜΕΝΟΥ demo ακόμα κι αν δεν έχει λήξει (για δοκιμές).
    Χωρίς body: όλα τα ληγμένα — έτοιμο για μελλοντικό Render Cron Job.
    """
    try:
        make_demo = _load_make_demo()
    except ImportError:
        return jsonify({"error": _MAKE_DEMO_MISSING}), 500

    data = request.get_json(silent=True) or {}
    cleaned = make_demo.cleanup_expired(
        only_client_id=clean_str(data.get("client_id"), 64) or None,
        force=bool(data.get("force")),
    )
    return jsonify({"ok": True, "cleaned": cleaned, "count": len(cleaned)}), 200
