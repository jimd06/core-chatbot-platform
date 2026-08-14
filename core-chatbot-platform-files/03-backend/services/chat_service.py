"""Ο εγκέφαλος: ερώτηση → embedding → pgvector search → guardrails → OpenAI.

Κανόνας: κάθε db_session ανοίγει σύντομα και επιστρέφει ΑΠΛΑ δεδομένα
(dict/str) — ποτέ ORM αντικείμενα έξω από το session ('Instance not bound
to a Session'). Οι κλήσεις OpenAI γίνονται ΕΚΤΟΣ session.

Escalation (ελάχιστη έκδοση — το πλήρες module είναι Φάση 5): αν το μήνυμα
του επισκέπτη περιέχει ελληνικό τηλέφωνο ή escalation keyword από τα
escalation_rules του πελάτη, φεύγει best-effort email ειδοποίηση στο
notification_email του (services/notify_service.py, background thread).
"""
import logging
import re

from openai import OpenAI

from config.database import db_session
from models import Client, ClientSettings, Conversation, KnowledgeChunk, Message, UsageLog
from platform_config import Config
from services.notify_service import send_async
from utils.formatters import truncate

logger = logging.getLogger(__name__)

_openai_client = None

# Ελληνικό τηλέφωνο μέσα σε κείμενο: κινητό 69ΧΧΧΧΧΧΧΧ ή σταθερό 2ΧΧΧΧΧΧΧΧΧ
# (10 ψηφία συνολικά), με προαιρετικό +30 και προαιρετικά κενά/παύλες/τελείες
# οπουδήποτε ανάμεσα στα ψηφία (π.χ. «69 4123 4567», «210 1234567»).
PHONE_RE = re.compile(r"(?<!\d)(?:\+?30[\s\-.]?)?(?:69|2\d)(?:[\s\-.]?\d){8}(?!\d)")


def _openai():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _openai_client


def load_client(client_id: str):
    """Επιστρέφει βασικά στοιχεία πελάτη (dict) ή None. Για CORS έλεγχο στα routes."""
    with db_session() as db:
        client = db.query(Client).filter_by(client_id=client_id, is_active=True).first()
        if client is None:
            return None
        return {"client_id": client.client_id, "allowed_domain": client.allowed_domain or ""}


def _load_context(client_id: str, conversation_id, visitor_id: str):
    """Session 1: settings + συνομιλία + ιστορικό → απλά δεδομένα."""
    with db_session() as db:
        settings = db.query(ClientSettings).filter_by(client_id=client_id).first()
        flags = dict(settings.feature_flags or {}) if settings else {}
        escalation = dict(settings.escalation_rules or {}) if settings else {}
        s = {
            "system_prompt": settings.system_prompt if settings else "",
            "out_of_scope": (settings.out_of_scope_message if settings else "") or
                            "Δεν έχω αυτή την πληροφορία.",
            "forbidden": list(settings.forbidden_topics or []) if settings else [],
            # Για το ελάχιστο escalation (βλ. _maybe_escalate):
            "notification_email": (settings.notification_email or "") if settings else "",
            "escalation_enabled": bool(flags.get("escalation")),
            "escalation_keywords": [str(k).lower() for k in (escalation.get("keywords") or [])],
        }

        conv = None
        if conversation_id:
            conv = db.query(Conversation).filter_by(
                id=str(conversation_id), client_id=client_id).first()
        if conv is None:
            conv = Conversation(client_id=client_id, visitor_id=visitor_id or "anonymous")
            db.add(conv)
            db.flush()
        conv_id = str(conv.id)

        history = [
            {"role": m.role, "content": truncate(m.content, 400)}
            for m in db.query(Message)
                      .filter_by(conversation_id=conv_id)
                      .order_by(Message.id.desc())
                      .limit(Config.HISTORY_MAX_MESSAGES)
                      .all()
        ][::-1]  # παλιότερο → νεότερο

        return s, conv_id, history


def _maybe_escalate(client_id: str, settings: dict, message: str, conv_id: str) -> None:
    """Αν ο επισκέπτης ζητά άνθρωπο ή αφήνει τηλέφωνο → email ειδοποίηση.

    Best-effort: η αποστολή γίνεται σε background thread και ποτέ δεν
    επηρεάζει την απάντηση του chat. Απαιτεί feature_flags.escalation=true
    και notification_email στα settings του πελάτη.
    """
    if not (settings["escalation_enabled"] and settings["notification_email"]):
        return
    lowered = message.lower()
    phone_match = PHONE_RE.search(message)
    keyword = next((k for k in settings["escalation_keywords"] if k and k in lowered), None)
    if not (phone_match or keyword):
        return
    reason = ("ο επισκέπτης άφησε τηλέφωνο" if phone_match
              else f"keyword: «{keyword}»")
    body = (
        f"Πελάτης πλατφόρμας: {client_id}\n"
        f"Συνομιλία: {conv_id}\n"
        f"Λόγος: {reason}\n\n"
        f"Μήνυμα επισκέπτη:\n{truncate(message, 1000)}"
    )
    send_async(settings["notification_email"],
               f"Escalation — {client_id}: ο επισκέπτης ζητά επικοινωνία",
               body)


def _embed(text: str, client_id: str):
    """Embedding της ερώτησης + καταγραφή κατανάλωσης."""
    resp = _openai().embeddings.create(model=Config.EMBEDDING_MODEL, input=text)
    vector = resp.data[0].embedding
    tokens = resp.usage.total_tokens if resp.usage else 0
    with db_session() as db:
        db.add(UsageLog(client_id=client_id, kind="embedding",
                        model=Config.EMBEDDING_MODEL, total_tokens=tokens))
    return vector


def _search_chunks(client_id: str, query_vector):
    """Session 2: pgvector cosine search ανά client_id → [(content, similarity)]."""
    with db_session() as db:
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
        rows = (db.query(KnowledgeChunk.content, distance.label("distance"))
                  .filter(KnowledgeChunk.client_id == client_id)
                  .filter(KnowledgeChunk.embedding.isnot(None))
                  .order_by(distance)
                  .limit(Config.RETRIEVAL_K)
                  .all())
        return [(content, max(0.0, 1.0 - float(dist))) for content, dist in rows]


def _confidence(chunks):
    """Πρακτική από sitechat: μέσος όρος similarity + bonus πολλαπλών πηγών, cap 0.95."""
    if not chunks:
        return 0.0
    avg = sum(sim for _, sim in chunks) / len(chunks)
    bonus = min(0.2, 0.05 * len(chunks))
    return min(0.95, avg + bonus)


def _build_system_prompt(settings, chunks):
    parts = [settings["system_prompt"] or
             "Είσαι εξυπηρετικός ψηφιακός βοηθός. Απαντάς σύντομα και στα ελληνικά."]
    if settings["forbidden"]:
        parts.append(
            "Απαγορευμένα θέματα: " + ", ".join(settings["forbidden"]) +
            ". Αν ρωτηθείς για αυτά, αρνήσου ευγενικά και επανέφερε τη συζήτηση "
            "στις υπηρεσίες της επιχείρησης."
        )
    parts.append(
        "Απαντάς ΜΟΝΟ με βάση τις παρακάτω πληροφορίες της επιχείρησης. "
        "Αν η απάντηση δεν υπάρχει εκεί, πες ευγενικά ότι δεν έχεις την πληροφορία. "
        "ΠΟΤΕ μη λες φράσεις όπως «βάσει των πληροφοριών» ή «σύμφωνα με το κείμενο» — "
        "απάντα φυσικά, σαν να τα ξέρεις."
    )
    context = "\n\n---\n\n".join(
        truncate(content, Config.CONTEXT_CHUNK_MAX_CHARS) for content, _ in chunks
    )
    parts.append("[Πληροφορίες επιχείρησης]\n" + (context or "Καμία διαθέσιμη πληροφορία."))
    return "\n\n".join(parts)


def _save_turn(conv_id, user_msg, reply, confidence, is_unanswered):
    """Session 3: αποθήκευση των δύο μηνυμάτων."""
    with db_session() as db:
        db.add(Message(conversation_id=conv_id, role="user", content=user_msg))
        db.add(Message(conversation_id=conv_id, role="assistant", content=reply,
                       confidence=confidence, is_unanswered=is_unanswered))


def answer(client_id: str, message: str, conversation_id=None, visitor_id="anonymous"):
    """Πλήρης κύκλος απάντησης. Επιστρέφει dict έτοιμο για JSON."""
    settings, conv_id, history = _load_context(client_id, conversation_id, visitor_id)

    # Escalation έλεγχος πριν από οτιδήποτε άλλο — καλύπτει ΚΑΙ την περίπτωση
    # χαμηλού confidence (κάποιος αφήνει τηλέφωνο ακριβώς όταν το bot κολλάει).
    _maybe_escalate(client_id, settings, message, conv_id)

    query_vector = _embed(message, client_id)
    chunks = _search_chunks(client_id, query_vector)
    confidence = round(_confidence(chunks), 2)

    # Guardrail: χαμηλό confidence → σταθερή out-of-scope απάντηση, χωρίς κλήση LLM
    # (μηδέν κόστος, μηδέν κίνδυνος να "εφευρεθεί" απάντηση).
    if confidence < Config.CONFIDENCE_THRESHOLD:
        reply = settings["out_of_scope"]
        _save_turn(conv_id, message, reply, confidence, True)
        return {"reply": reply, "conversation_id": conv_id,
                "confidence": confidence, "is_unanswered": True}

    messages = [{"role": "system", "content": _build_system_prompt(settings, chunks)}]
    messages += history
    messages.append({"role": "user", "content": message})

    resp = _openai().chat.completions.create(
        model=Config.CHAT_MODEL, messages=messages,
        temperature=0.4, max_tokens=500,
    )
    reply = (resp.choices[0].message.content or "").strip()

    usage = resp.usage
    with db_session() as db:
        db.add(UsageLog(client_id=client_id, kind="chat", model=Config.CHAT_MODEL,
                        prompt_tokens=usage.prompt_tokens if usage else 0,
                        completion_tokens=usage.completion_tokens if usage else 0,
                        total_tokens=usage.total_tokens if usage else 0))

    _save_turn(conv_id, message, reply, confidence, False)
    return {"reply": reply, "conversation_id": conv_id,
            "confidence": confidence, "is_unanswered": False}


def delete_visitor_data(client_id: str, visitor_id: str) -> int:
    """GDPR: διαγράφει όλες τις συνομιλίες + μηνύματα ενός επισκέπτη."""
    with db_session() as db:
        conv_ids = [c.id for c in db.query(Conversation.id)
                    .filter_by(client_id=client_id, visitor_id=visitor_id).all()]
        if not conv_ids:
            return 0
        db.query(Message).filter(Message.conversation_id.in_(conv_ids)) \
            .delete(synchronize_session=False)
        deleted = db.query(Conversation).filter(Conversation.id.in_(conv_ids)) \
            .delete(synchronize_session=False)
        return deleted
