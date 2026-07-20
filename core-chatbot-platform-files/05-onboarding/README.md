# 05-onboarding — Το εργοστάσιο πελατών

Δύο scripts: `seed_new_client.py` (ερωτηματολόγιο → βάση) και `ingest_content.py` (περιεχόμενο → knowledge chunks με embeddings). Χρησιμοποιούν τα models του 01-data-layer (πίνακες `cp_clients`, `cp_client_settings`, `cp_knowledge_chunks`). Μόνος νέος πίνακας: ο βοηθητικός `cp_ingest_sources` (hashes) — δημιουργείται αυτόματα.

## Α. Προετοιμασία (μία φορά)

1. Αντέγραψε τον φάκελο `05-onboarding/` στη ρίζα του repo `core-chatbot-platform`.
2. Πρόσθεσε στο `requirements.txt` της ρίζας τις 3 γραμμές: `requests`, `beautifulsoup4`, `pypdf` (έτοιμο αρχείο: δες requirements.txt στο ZIP).
3. Από τη ρίζα του repo: `pip install -r requirements.txt`
4. Όρισε τα environment variables (τα ίδια με το Render):
   - Windows: `set DATABASE_URL=postgres://...` και `set OPENAI_API_KEY=sk-...`
   - Render Shell/Linux: `export DATABASE_URL=...` κ.λπ.

## Β. Νέος πελάτης (η τυποποιημένη ροή)

1. Συμπλήρωσε ένα JSON με τις απαντήσεις του ερωτηματολογίου (πρότυπο: `demo_client_komotirio.json`). Προσοχή: `forbidden_topics` = λίστα, `escalation_rules` = αντικείμενο.
2. `python 05-onboarding/seed_new_client.py <πελάτης>.json`
3. Πέρασε τη γνώση του:
   - `python 05-onboarding/ingest_content.py --client <client_id> --file <αρχείο.txt>`
   - `python 05-onboarding/ingest_content.py --client <client_id> --pdf <αρχείο.pdf>`
   - `python 05-onboarding/ingest_content.py --client <client_id> --url https://...`
4. Δοκίμασε στο `/demo?client_id=<client_id>` στο Render URL.
5. Δώσε στον πελάτη το snippet με το `client_id` του. Τέλος.

## Γ. Demo πελάτης (κομμωτήριο) — απόδειξη ότι δουλεύει

1. `python 05-onboarding/seed_new_client.py 05-onboarding/demo_client_komotirio.json`
2. `python 05-onboarding/ingest_content.py --client komotirio_demo --file 05-onboarding/sample_content/komotirio_info.txt`
3. Άνοιξε `/demo?client_id=komotirio_demo` και ρώτα π.χ. «πόσο κοστίζει το balayage;».
4. Ξανατρέξε το βήμα 2 → πρέπει να δεις `skipped` (μηδέν κόστος OpenAI).

## Δ. Render Cron Job (αυτόματη ανανέωση γνώσης)

1. Render → New → **Cron Job**, ίδιο repo, Python 3.12.
2. Schedule: `0 4 * * 1` (κάθε Δευτέρα 04:00 UTC — άλλαξέ το αν θες).
3. Command: `pip install -r requirements.txt && python 05-onboarding/ingest_content.py --all`
4. Environment: πρόσθεσε `DATABASE_URL` και `OPENAI_API_KEY`.
5. Το `--all` διαβάζει τα `crawl_urls` από το `cp_client_settings` κάθε ενεργού πελάτη. Βάλε λοιπόν τα URLs του πελάτη στο πεδίο `crawl_urls` του JSON του (και `crawl_frequency`: `weekly`).

## Πώς λειτουργεί το hash (μηδέν περιττό κόστος OpenAI)

- Κάθε πηγή (URL ή αρχείο) παίρνει sha256 hash του κειμένου της (πίνακας `cp_ingest_sources`).
- Ίδιο hash → `skipped`: κανένα embedding, κανένα κόστος.
- Αλλαγμένο hash → σβήνονται τα παλιά chunks της πηγής και ξαναγίνονται embeddings μόνο για αυτήν.
- Επιπλέον, κάθε chunk κρατά δικό του `content_hash` (πεδίο του `cp_knowledge_chunks`).

## Σημείωση συμβατότητας

Ίδιο embedding μοντέλο με το backend (`EMBEDDING_MODEL`, default `text-embedding-3-small`) — αν αλλάξει το env var στο Render, πρέπει να αλλάξει και στο Cron Job, και να ξαναγίνει ingestion όλης της γνώσης.
