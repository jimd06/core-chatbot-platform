#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_content.py — Το «εργοστάσιο πελατών», βήμα 2.

Μετατρέπει κείμενα, PDF και URLs σε KnowledgeChunk εγγραφές με OpenAI
embeddings, χρησιμοποιώντας τα models του 01-data-layer (πίνακας
cp_knowledge_chunks). Ο ΜΟΝΟΣ πίνακας που δημιουργεί το script είναι ο
βοηθητικός cp_ingest_sources (hash ανά πηγή).

Χρήση (χειροκίνητα, για έναν πελάτη):
    python 05-onboarding/ingest_content.py --client komotirio_demo --url https://example.gr/services
    python 05-onboarding/ingest_content.py --client komotirio_demo --file 05-onboarding/sample_content/komotirio_info.txt
    python 05-onboarding/ingest_content.py --client komotirio_demo --pdf timokatalogos.pdf

Χρήση (αυτόματα, για ΟΛΟΥΣ τους πελάτες — Render Cron Job):
    python 05-onboarding/ingest_content.py --all
    (διαβάζει τα crawl_urls από το ClientSettings κάθε ενεργού πελάτη)

Λογική hash (μηδέν κόστος OpenAI για αμετάβλητο περιεχόμενο):
    - Κάθε πηγή (URL/αρχείο) → sha256 hash του κειμένου της στον cp_ingest_sources.
    - Ίδιο hash → SKIP (κανένα embedding, κανένα κόστος).
    - Διαφορετικό hash → σβήνονται τα παλιά chunks της πηγής και ξαναγίνονται embeddings.
    - Κάθε chunk κρατά και δικό του content_hash (πεδίο του KnowledgeChunk).

Απαιτεί environment variables: DATABASE_URL, OPENAI_API_KEY
"""

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone

# --- sys.path: ίδιο pattern με seed.py / app.py ------------------------------
ONBOARDING_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ONBOARDING_DIR)
DATA_LAYER = os.path.join(REPO_ROOT, "01-data-layer")
if DATA_LAYER not in sys.path:
    sys.path.insert(0, DATA_LAYER)
# ----------------------------------------------------------------------------

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from config.database import Base, db_session, get_engine
from models import Client, ClientSettings, KnowledgeChunk

# Ίδιο default με το 02-config/config.py — ίδιο μοντέλο σε ingestion & αναζήτηση.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
CHUNK_SIZE = 1000        # χαρακτήρες ανά chunk
CHUNK_OVERLAP = 200      # επικάλυψη μεταξύ διαδοχικών chunks
EMBED_BATCH_SIZE = 64    # πόσα chunks ανά κλήση στο OpenAI
MAX_SOURCE_URL_LEN = 512  # όσο και το String(512) του KnowledgeChunk.source_url


class IngestSource(Base):
    """Βοηθητικός πίνακας ΑΥΤΟΥ του script: hash κειμένου ανά (client, πηγή)."""
    __tablename__ = "cp_ingest_sources"

    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), nullable=False, index=True)
    source_url = Column(String(512), nullable=False)
    content_hash = Column(String(64), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("client_id", "source_url", name="uq_ingest_client_source"),)


# ---------------------------------------------------------------- εξαγωγή κειμένου

def text_from_url(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (chatbot-ingester)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def text_from_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def text_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- chunking

def chunk_text(text: str) -> list[str]:
    """Απλό chunking με μέγεθος CHUNK_SIZE και επικάλυψη CHUNK_OVERLAP.
    Προσπαθεί να «κόβει» σε αλλαγή παραγράφου ή πρότασης, όχι στη μέση λέξης."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            # Ψάξε καλό σημείο κοπής: παράγραφος > πρόταση > αλλαγή γραμμής > κενό
            for sep in ("\n\n", ". ", "\n", " "):
                cut = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


# ---------------------------------------------------------------- embeddings

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI()  # διαβάζει το OPENAI_API_KEY από το περιβάλλον
    embeddings: list[list[float]] = []
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i:i + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in resp.data)
    return embeddings


# ---------------------------------------------------------------- ingestion

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_source(client_id: str, source_url: str, text: str) -> str:
    """Επιστρέφει: 'skipped' | 'updated' | 'empty'."""
    text = text.strip()
    if not text:
        return "empty"

    source_url = source_url[:MAX_SOURCE_URL_LEN]
    source_hash = sha256(text)

    # Έλεγχος hash (δικό του session — τα embeddings γίνονται ΕΚΤΟΣ session,
    # για να μην κρατάμε ανοιχτή σύνδεση όσο μιλάμε με το OpenAI)
    with db_session() as db:
        existing = (db.query(IngestSource.content_hash)
                      .filter_by(client_id=client_id, source_url=source_url)
                      .first())
        if existing and existing[0] == source_hash:
            return "skipped"

    chunks = chunk_text(text)
    embeddings = embed_chunks(chunks)

    with db_session() as db:
        # Σβήσε τα παλιά chunks αυτής της πηγής και γράψε τα νέα
        (db.query(KnowledgeChunk)
           .filter_by(client_id=client_id, source_url=source_url)
           .delete())
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeChunk(
                client_id=client_id,
                content=chunk,
                chunk_metadata={"chunk_index": idx, "total_chunks": len(chunks)},
                source_url=source_url,
                content_hash=sha256(chunk),
                embedding=emb,
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

    return "updated"


def crawl_all_clients() -> None:
    """Cron mode: για κάθε ενεργό πελάτη, κατέβασε τα crawl_urls του."""
    with db_session() as db:
        rows = (db.query(ClientSettings.client_id, ClientSettings.crawl_urls)
                  .join(Client, Client.client_id == ClientSettings.client_id)
                  .filter(Client.is_active.is_(True))
                  .all())
        # Μόνο απλά δεδομένα βγαίνουν από το session (όχι ORM αντικείμενα)
        client_urls = [(client_id, list(crawl_urls or [])) for client_id, crawl_urls in rows]

    if not client_urls:
        print("Δεν βρέθηκαν ενεργοί πελάτες.")
        return

    for client_id, urls in client_urls:
        if not urls:
            print(f"[{client_id}] χωρίς crawl_urls — παράλειψη.")
            continue
        for url in urls:
            try:
                result = ingest_source(client_id, url, text_from_url(url))
                print(f"[{client_id}] {url} → {result}")
            except Exception as exc:
                print(f"[{client_id}] {url} → ΣΦΑΛΜΑ: {exc}")


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion περιεχομένου σε knowledge chunks.")
    parser.add_argument("--client", help="client_id του πελάτη")
    parser.add_argument("--url", action="append", default=[], help="URL προς ingestion (επαναλαμβανόμενο)")
    parser.add_argument("--file", action="append", default=[], help="Αρχείο κειμένου (.txt/.md)")
    parser.add_argument("--pdf", action="append", default=[], help="Αρχείο PDF")
    parser.add_argument("--all", action="store_true", help="Cron mode: όλοι οι ενεργοί πελάτες από crawl_urls")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ΣΦΑΛΜΑ: Δεν βρέθηκε το DATABASE_URL στο περιβάλλον.")
        sys.exit(1)
    if not os.environ.get("OPENAI_API_KEY"):
        print("ΣΦΑΛΜΑ: Δεν βρέθηκε το OPENAI_API_KEY στο περιβάλλον.")
        sys.exit(1)

    # Δημιουργεί ΜΟΝΟ τον cp_ingest_sources αν λείπει (οι υπόλοιποι πίνακες
    # ανήκουν στο 01-data-layer και πρέπει να υπάρχουν ήδη).
    IngestSource.__table__.create(bind=get_engine(), checkfirst=True)

    if args.all:
        crawl_all_clients()
        return

    if not args.client:
        parser.error("Χρειάζεται --client <client_id> (ή --all για cron mode).")
    if not (args.url or args.file or args.pdf):
        parser.error("Δώσε τουλάχιστον ένα --url, --file ή --pdf.")

    for url in args.url:
        print(f"[{args.client}] {url} → {ingest_source(args.client, url, text_from_url(url))}")
    for path in args.file:
        print(f"[{args.client}] {path} → {ingest_source(args.client, path, text_from_file(path))}")
    for path in args.pdf:
        print(f"[{args.client}] {path} → {ingest_source(args.client, path, text_from_pdf(path))}")

    print("✅ Ολοκληρώθηκε.")


if __name__ == "__main__":
    main()
