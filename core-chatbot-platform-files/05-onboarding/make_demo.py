#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo.py — Demo-First: demo chatbot από το site υποψήφιου πελάτη με ΜΙΑ κλήση.

Ροή (καλείται από το POST /api/v1/admin/demo στο routes/admin.py):
1. create_demo(): φτιάχνει demo client (cp_clients + cp_client_settings) με
   template ανά κλάδο και ξεκινά ingestion του site σε background thread
   (το gunicorn έχει όριο 30" ανά request — sync δεν χωράει).
2. _run_ingestion(): αρχική σελίδα + same-domain σύνδεσμοι (βάθος 1, έως
   DEMO_MAX_PAGES) → κείμενο → chunks → embeddings → cp_knowledge_chunks.
   Η πρόοδος γράφεται στο feature_flags για να τη βλέπει το /admin/demo/status.
3. get_demo_state(): κατάσταση demo (status, σελίδες, chunks, απαντήσεις, λήξη).
4. cleanup_expired(): καθαρίζει ληγμένα demos — chunks + hashes + συνομιλίες.
   ΚΡΑΤΑΕΙ client/settings (η σελίδα /demo δείχνει «έληξε» + CTA) και ΟΛΑ τα
   usage_logs (ιστορικό κόστους demos ανά μήνα).

Όλη η κατάσταση του demo ζει στο feature_flags (JSONB) του ClientSettings —
κανένα νέο πεδίο, κανένα migration, ΔΕΝ χρειάζεται /admin/setup.
"""
import logging
import os
import re
import secrets
import sys
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

# --- sys.path: 01-data-layer (models/config) + 05-onboarding (sibling imports)
ONBOARDING_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ONBOARDING_DIR)
DATA_LAYER = os.path.join(REPO_ROOT, "01-data-layer")
for _path in (DATA_LAYER, ONBOARDING_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from config.database import db_session, get_engine
from models import Client, ClientSettings, Conversation, KnowledgeChunk, Message, UsageLog

from demo_templates import (
    DEMO_ANSWER_LIMIT, DEMO_DAYS, DEMO_MAX_CHUNKS_PER_PAGE, DEMO_MAX_PAGES,
    DEMO_OUT_OF_SCOPE, DEMO_PAGE_TIMEOUT, DEMO_TOTAL_BUDGET, INDUSTRY_TEMPLATES,
    demo_expired, email_for_prospect, industry_template,
)
from ingest_content import (
    EMBEDDING_MODEL, IngestSource, chunk_text, sha256, text_from_url,
)

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (chatbot-ingester)"

# Αρχεία που δεν είναι σελίδες περιεχομένου — δεν τα ακολουθούμε στο crawl.
_SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".css", ".js", ".xml", ".json", ".rss",
)


# ===========================================================================
# Δημόσιο API — create_demo / get_demo_state / cleanup_expired
# ===========================================================================

def create_demo(site_url: str, business_name: str, industry: str,
                contact_email: str, base_url: str, reuse_client_id: str = None,
                answer_limit=None, days=None) -> dict:
    """Δημιουργεί demo chatbot για υποψήφιο πελάτη. Επιστρέφει ΠΑΝΤΑ dict.

    - base_url: η βάση της πλατφόρμας (π.χ. https://core-chatbot-platform.onrender.com)
      — από αυτήν βγαίνουν το demo_url ΚΑΙ το allowed_domain του demo client,
      ώστε το widget να δουλεύει ΜΟΝΟ στη σελίδα /demo (το snippet δεν «κλέβεται»).
    - reuse_client_id: επανεκκίνηση ingestion ΥΠΑΡΧΟΝΤΟΣ demo (retry μετά από
      restart του Render ή σφάλμα) — δεν φτιάχνει νέο client.
    - Guard διπλού κλικ: αν υπάρχει ήδη ΕΝΕΡΓΟ, μη ληγμένο demo με το ίδιο
      site_url, επιστρέφεται το υπάρχον (reused: true) αντί για δεύτερο client.
    """
    _ensure_ingest_table()

    if reuse_client_id:
        return _rerun_demo(reuse_client_id, base_url)

    norm_url = _normalize_site_url(site_url)
    business_name = (business_name or "").strip()
    if not norm_url:
        return {"ok": False,
                "error": "Χρειάζεται έγκυρο site_url (π.χ. https://example.gr)."}
    if not business_name:
        return {"ok": False, "error": "Χρειάζεται business_name."}

    contact_email = (contact_email or "").strip()
    if contact_email and ("@" not in contact_email or " " in contact_email):
        contact_email = ""

    industry_key = (industry or "").strip().lower()
    if industry_key not in INDUSTRY_TEMPLATES:
        industry_key = "allo"
    tpl = industry_template(industry_key)

    limit = _clamp_int(answer_limit, DEMO_ANSWER_LIMIT, 1, 200)
    duration = _clamp_int(days, DEMO_DAYS, 1, 30)

    # --- Guard διπλού κλικ / επανάληψης κλήσης για το ίδιο site ---------------
    existing = _find_active_demo_by_site(norm_url)
    if existing:
        note = "Υπάρχει ήδη ενεργό demo για αυτό το site — επιστράφηκε το υπάρχον."
        state = get_demo_state(existing) or {}
        if state.get("status") == "error":
            _start_ingestion(existing, norm_url)
            note += " Το ingestion ξεκίνησε ξανά (το προηγούμενο είχε σφάλμα)."
        return _demo_response(existing, base_url, created=False, reused=True,
                              note=note)

    client_id = _unique_client_id(business_name)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat()
    platform_host = urlparse(base_url).hostname or ""

    with db_session() as db:
        db.add(Client(client_id=client_id, name=business_name,
                      allowed_domain=platform_host, is_active=True))
        db.add(ClientSettings(
            client_id=client_id,
            system_prompt=tpl["system_prompt"].format(business_name=business_name),
            welcome_message=tpl["welcome_message"].format(business_name=business_name),
            out_of_scope_message=DEMO_OUT_OF_SCOPE,
            forbidden_topics=list(tpl.get("forbidden_topics") or []),
            escalation_rules={},
            # Αποθηκεύεται για μελλοντική επαφή — ΔΕΝ εμφανίζεται πουθενά και
            # δεν στέλνεται τίποτα (escalation: false, SMTP ούτως ή άλλως κλειστό).
            notification_email=contact_email,
            primary_color=tpl["primary_color"],
            logo_url="",
            feature_flags={
                "leads": False,
                "escalation": False,
                "is_demo": True,
                "demo_status": "pending",       # pending → ingesting → ready/error
                "demo_expires_at": expires_at,
                "demo_answer_limit": limit,
                "demo_business_name": business_name,
                "demo_site_url": norm_url,
                "demo_industry": industry_key,
                "demo_pages_ok": 0,
                "demo_pages_total": 0,
                "demo_error": "",
            },
            crawl_urls=[],              # ο μελλοντικός cron ΔΕΝ ξανακατεβάζει demos
            crawl_frequency="manual",
        ))

    _start_ingestion(client_id, norm_url)
    return _demo_response(client_id, base_url, created=True, reused=False,
                          note="Το ingestion του site τρέχει στο background.")


def get_demo_state(client_id: str):
    """Κατάσταση demo για το /admin/demo/status και τη σελίδα /demo/<id>.

    Επιστρέφει None για άγνωστο client. Για ΜΗ-demo clients επιστρέφει μικρό
    dict με is_demo: False (η σελίδα /demo τους δείχνει όπως πριν).
    """
    client_id = (client_id or "").strip()
    if not client_id:
        return None
    with db_session() as db:
        client = db.query(Client).filter_by(client_id=client_id).first()
        if client is None:
            return None
        settings = db.query(ClientSettings).filter_by(client_id=client_id).first()
        flags = dict(settings.feature_flags or {}) if settings else {}

        state = {
            "client_id": client_id,
            "name": client.name,
            "is_active": bool(client.is_active),
            "is_demo": bool(flags.get("is_demo")),
        }
        if not state["is_demo"]:
            return state

        answers_used = db.query(UsageLog).filter_by(
            client_id=client_id, kind="chat").count()
        chunks = db.query(KnowledgeChunk).filter_by(client_id=client_id).count()
        limit = _clamp_int(flags.get("demo_answer_limit"), DEMO_ANSWER_LIMIT, 1, 200)
        expires_at = str(flags.get("demo_expires_at") or "")

        state.update({
            "business_name": str(flags.get("demo_business_name") or client.name),
            "industry": str(flags.get("demo_industry") or "allo"),
            "site_url": str(flags.get("demo_site_url") or ""),
            "status": str(flags.get("demo_status") or ""),
            "error": str(flags.get("demo_error") or ""),
            "pages_ok": _clamp_int(flags.get("demo_pages_ok"), 0, 0, 10_000),
            "pages_total": _clamp_int(flags.get("demo_pages_total"), 0, 0, 10_000),
            "chunks": chunks,
            "answers_used": answers_used,
            "answer_limit": limit,
            "answers_left": max(0, limit - answers_used),
            "expires_at": expires_at,
            "expired": demo_expired(expires_at),
            "primary_color": (settings.primary_color if settings else "") or "#0B6E4F",
        })
        return state


def cleanup_expired(only_client_id: str = None, force: bool = False) -> list:
    """Καθαρίζει ληγμένα demos. Επιστρέφει λίστα με τα client_ids που καθάρισε.

    Τι σβήνει: knowledge chunks, ingest hashes, συνομιλίες + μηνύματα.
    Τι ΚΡΑΤΑΕΙ: τις εγγραφές client/client_settings (ώστε το /demo/<id> να
    δείχνει «έληξε» + CTA) και ΟΛΑ τα usage_logs — το ιστορικό κόστους των
    demos ανά μήνα μένει άθικτο για το tracking κόστους ανά κανάλι.

    only_client_id + force=True → καθάρισμα ΣΥΓΚΕΚΡΙΜΕΝΟΥ demo ακόμα κι αν
    δεν έχει λήξει (χρήσιμο για δοκιμές). Το force ΧΩΡΙΣ client_id αγνοείται
    (ασφάλεια: να μη σβηστούν κατά λάθος όλα τα ενεργά demos).
    Χωρίς ορίσματα: όλα τα ληγμένα — έτοιμο για μελλοντικό Render Cron Job.
    """
    with db_session() as db:
        rows = db.query(ClientSettings.client_id, ClientSettings.feature_flags).all()

    candidates = []
    for cid, flags in rows:
        f = dict(flags or {})
        if not f.get("is_demo") or f.get("demo_status") == "expired":
            continue
        if only_client_id and cid != only_client_id:
            continue
        is_expired = demo_expired(str(f.get("demo_expires_at") or ""))
        if is_expired or (force and only_client_id):
            candidates.append(cid)

    cleaned = []
    for cid in candidates:
        with db_session() as db:
            db.query(KnowledgeChunk).filter_by(client_id=cid).delete(
                synchronize_session=False)
            db.query(IngestSource).filter_by(client_id=cid).delete(
                synchronize_session=False)
            # Ίδιο pattern με το GDPR delete του chat_service:
            conv_ids = [c.id for c in
                        db.query(Conversation.id).filter_by(client_id=cid).all()]
            if conv_ids:
                db.query(Message).filter(
                    Message.conversation_id.in_(conv_ids)).delete(
                    synchronize_session=False)
                db.query(Conversation).filter(
                    Conversation.id.in_(conv_ids)).delete(
                    synchronize_session=False)
            client = db.query(Client).filter_by(client_id=cid).first()
            if client is not None:
                client.is_active = False
            settings = db.query(ClientSettings).filter_by(client_id=cid).first()
            if settings is not None:
                flags = dict(settings.feature_flags or {})
                flags["demo_status"] = "expired"
                settings.feature_flags = flags
        cleaned.append(cid)
        logger.info("Demo %s: καθαρίστηκε (chunks, hashes, συνομιλίες).", cid)
    return cleaned


# ===========================================================================
# Εσωτερικά — απάντηση API, επανεκκίνηση, guard, client_id
# ===========================================================================

def _demo_response(client_id: str, base_url: str, created: bool,
                   reused: bool, note: str = "") -> dict:
    """Κοινό σχήμα απάντησης για νέο demo, guard hit και επανεκκίνηση."""
    state = get_demo_state(client_id) or {}
    business_name = state.get("business_name") or client_id
    expires_at = state.get("expires_at") or ""
    demo_url = f"{base_url.rstrip('/')}/demo/{client_id}"
    subject, body = email_for_prospect(business_name, demo_url, expires_at)
    return {
        "ok": True,
        "created": created,
        "reused": reused,
        "client_id": client_id,
        "demo_url": demo_url,
        "expires_at": expires_at,
        "status": state.get("status") or "",
        "answers_left": state.get("answers_left"),
        "email_subject": subject,
        "email_body": body,
        "note": note,
        "next": (f"GET /api/v1/admin/demo/status?client_id={client_id} "
                 "μέχρι status: ready — μετά στείλε το email στον υποψήφιο."),
    }


def _rerun_demo(client_id: str, base_url: str) -> dict:
    """Επανεκκίνηση ingestion υπάρχοντος (ζωντανού) demo — όχι νέος client."""
    state = get_demo_state(client_id)
    if state is None or not state.get("is_demo"):
        return {"ok": False, "error": f"Το '{client_id}' δεν είναι demo client."}
    if state.get("expired") or not state.get("is_active") \
            or state.get("status") == "expired":
        return {"ok": False,
                "error": f"Το demo '{client_id}' έχει λήξει — δημιούργησε νέο."}
    site_url = state.get("site_url") or ""
    if not site_url:
        return {"ok": False,
                "error": f"Το demo '{client_id}' δεν έχει αποθηκευμένο site_url."}
    _start_ingestion(client_id, site_url)
    return _demo_response(client_id, base_url, created=False, reused=True,
                          note="Το ingestion ξεκίνησε ξανά για το υπάρχον demo.")


def _find_active_demo_by_site(norm_url: str):
    """client_id ενεργού, μη ληγμένου demo με το ίδιο site — αλλιώς None."""
    with db_session() as db:
        rows = (db.query(ClientSettings.client_id, ClientSettings.feature_flags)
                .join(Client, Client.client_id == ClientSettings.client_id)
                .filter(Client.is_active.is_(True))
                .all())
    for cid, flags in rows:
        f = dict(flags or {})
        if (f.get("is_demo")
                and f.get("demo_status") != "expired"
                and str(f.get("demo_site_url") or "") == norm_url
                and not demo_expired(str(f.get("demo_expires_at") or ""))):
            return cid
    return None


_GREEK_MAP = {
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "φ": "f", "χ": "ch", "ψ": "ps", "ω": "o",
}


def _slugify(name: str) -> str:
    """«Κομμωτήριο Ορφέας» → 'kommotirio-orfeas' (λατινικά, πεζά, παύλες)."""
    text = unicodedata.normalize("NFD", (name or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    out = []
    for ch in text:
        if ch in _GREEK_MAP:
            out.append(_GREEK_MAP[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return slug[:24].rstrip("-")


def _unique_client_id(business_name: str) -> str:
    """demo-<slug>-<4hex>, με έλεγχο μοναδικότητας στη βάση."""
    slug = _slugify(business_name) or "demo"
    for _ in range(5):
        candidate = f"demo-{slug}-{secrets.token_hex(2)}"
        with db_session() as db:
            exists = db.query(Client.id).filter_by(client_id=candidate).first()
        if not exists:
            return candidate
    return f"demo-{slug}-{secrets.token_hex(4)}"


def _clamp_int(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _normalize_site_url(url: str) -> str:
    """https:// αν λείπει, πεζό host, χωρίς trailing slash — για guard + crawl."""
    url = (url or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = _host_with_port(parsed)
    if not host or "." not in (parsed.hostname or ""):
        return ""
    path = (parsed.path or "").rstrip("/")
    return f"{parsed.scheme}://{host}{path}"


def _host_with_port(parsed) -> str:
    """πεζό hostname + ρητό port αν υπάρχει (το .hostname το πετάει)."""
    host = (parsed.hostname or "").lower()
    if host and parsed.port:
        host = f"{host}:{parsed.port}"
    return host


# ===========================================================================
# Ingestion σε background thread
# ===========================================================================

_ingest_table_ready = False


def _ensure_ingest_table() -> None:
    """Ο πίνακας cp_ingest_sources (hash ανά πηγή) μπορεί να μην υπάρχει ακόμα
    στη βάση — δημιουργείται εδώ ακίνδυνα (checkfirst=True)."""
    global _ingest_table_ready
    if _ingest_table_ready:
        return
    IngestSource.__table__.create(bind=get_engine(), checkfirst=True)
    _ingest_table_ready = True


def _start_ingestion(client_id: str, site_url: str) -> None:
    _set_flags(client_id, demo_status="pending", demo_error="",
               demo_pages_ok=0, demo_pages_total=0)
    threading.Thread(target=_run_ingestion, args=(client_id, site_url),
                     daemon=True, name=f"demo-ingest-{client_id}").start()


def _run_ingestion(client_id: str, site_url: str) -> None:
    """Τρέχει σε background thread — ΠΟΤΕ δεν αφήνει exception προς τα έξω.
    Η πρόοδος και τα σφάλματα γράφονται στο feature_flags (demo_status κ.λπ.)."""
    try:
        _set_flags(client_id, demo_status="ingesting", demo_error="")
        pages = _discover_pages(site_url)
        _set_flags(client_id, demo_pages_total=len(pages))

        deadline = time.monotonic() + DEMO_TOTAL_BUDGET
        pages_ok = 0
        for url in pages:
            if time.monotonic() > deadline:
                logger.warning("[%s] Τέλος χρόνου ingestion — σταματάμε στις "
                               "%d σελίδες.", client_id, pages_ok)
                break
            try:
                text = text_from_url(url, timeout=DEMO_PAGE_TIMEOUT)
                result = _ingest_page(client_id, url, text)
                if result in ("updated", "skipped"):
                    pages_ok += 1
                    _set_flags(client_id, demo_pages_ok=pages_ok)
            except Exception as exc:
                logger.warning("[%s] Σφάλμα σελίδας %s: %s", client_id, url, exc)

        with db_session() as db:
            chunks = db.query(KnowledgeChunk).filter_by(client_id=client_id).count()
        if chunks == 0:
            _set_flags(client_id, demo_status="error",
                       demo_error="Δεν εξήχθη αξιοποιήσιμο περιεχόμενο από το site.")
        else:
            _set_flags(client_id, demo_status="ready")
            logger.info("[%s] Demo έτοιμο: %d σελίδες, %d chunks.",
                        client_id, pages_ok, chunks)
    except Exception as exc:  # δίχτυ ασφαλείας — το σφάλμα φαίνεται στο status
        logger.exception("[%s] Το demo ingestion απέτυχε.", client_id)
        _set_flags(client_id, demo_status="error", demo_error=str(exc)[:300])


def _set_flags(client_id: str, **updates) -> None:
    """Ενημερώνει κλειδιά στο feature_flags. ΠΑΝΤΑ με ΝΕΟ dict — η SQLAlchemy
    δεν ανιχνεύει in-place αλλαγές σε JSONB."""
    with db_session() as db:
        settings = db.query(ClientSettings).filter_by(client_id=client_id).first()
        if settings is None:
            return
        flags = dict(settings.feature_flags or {})
        flags.update(updates)
        settings.feature_flags = flags


def _canon_url(url: str) -> str:
    """Κανονικοποίηση URL για dedup: χωρίς query/fragment/trailing slash."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    path = (parsed.path or "").rstrip("/")
    return f"{parsed.scheme}://{_host_with_port(parsed)}{path}"


def _bare_host(host: str) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def _discover_pages(start_url: str) -> list:
    """Αρχική σελίδα + same-domain σύνδεσμοι από αυτήν (βάθος 1).
    Επιστρέφει έως DEMO_MAX_PAGES κανονικοποιημένα URLs — η αρχική πρώτη."""
    import requests
    from bs4 import BeautifulSoup

    start = _canon_url(start_url) or start_url
    pages = [start]
    try:
        resp = requests.get(start, timeout=DEMO_PAGE_TIMEOUT,
                            headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        base_host = _bare_host(urlparse(start).hostname or "")
        seen = {start}
        for anchor in soup.find_all("a", href=True):
            candidate = _canon_url(urljoin(start, anchor["href"].strip()))
            if not candidate or candidate in seen:
                continue
            if _bare_host(urlparse(candidate).hostname or "") != base_host:
                continue
            if urlparse(candidate).path.lower().endswith(_SKIP_EXTENSIONS):
                continue
            seen.add(candidate)
            pages.append(candidate)
            if len(pages) >= DEMO_MAX_PAGES:
                break
    except Exception as exc:
        logger.warning("Αποτυχία ανίχνευσης συνδέσμων από %s: %s — συνεχίζουμε "
                       "μόνο με την αρχική σελίδα.", start, exc)
    return pages


def _ingest_page(client_id: str, source_url: str, text: str) -> str:
    """'updated' | 'skipped' | 'empty' — ίδια λογική με το ingest_source του
    ingest_content.py, συν: καταγραφή UsageLog (κόστος embeddings ανά demo)
    και φρένο DEMO_MAX_CHUNKS_PER_PAGE σε υπερβολικά μεγάλες σελίδες."""
    text = (text or "").strip()
    if len(text) < 80:  # πολύ λίγο κείμενο → δεν αξίζει chunk
        return "empty"
    source_url = source_url[:512]
    source_hash = sha256(text)

    with db_session() as db:
        existing = (db.query(IngestSource.content_hash)
                    .filter_by(client_id=client_id, source_url=source_url)
                    .first())
        if existing and existing[0] == source_hash:
            return "skipped"

    chunks = chunk_text(text)[:DEMO_MAX_CHUNKS_PER_PAGE]
    if not chunks:
        return "empty"
    embeddings, total_tokens = _embed_with_usage(chunks)

    with db_session() as db:
        db.query(KnowledgeChunk).filter_by(
            client_id=client_id, source_url=source_url).delete(
            synchronize_session=False)
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeChunk(
                client_id=client_id,
                content=chunk,
                chunk_metadata={"chunk_index": idx, "total_chunks": len(chunks),
                                "demo": True},
                source_url=source_url,
                content_hash=sha256(chunk),
                embedding=embedding,
            ))
        record = (db.query(IngestSource)
                  .filter_by(client_id=client_id, source_url=source_url)
                  .first())
        if record is None:
            record = IngestSource(client_id=client_id, source_url=source_url,
                                  content_hash=source_hash)
            db.add(record)
        record.content_hash = source_hash
        record.updated_at = datetime.now(timezone.utc)
        db.add(UsageLog(client_id=client_id, kind="embedding",
                        model=EMBEDDING_MODEL, total_tokens=total_tokens))
    return "updated"


def _embed_with_usage(chunks: list):
    """Embeddings σε batches + συνολικά tokens (για το UsageLog του demo)."""
    from openai import OpenAI  # lazy — το κλειδί έρχεται από το OPENAI_API_KEY

    client = OpenAI()
    embeddings, total_tokens = [], 0
    for i in range(0, len(chunks), 64):
        batch = chunks[i:i + 64]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)
        if response.usage:
            total_tokens += response.usage.total_tokens
    return embeddings, total_tokens
