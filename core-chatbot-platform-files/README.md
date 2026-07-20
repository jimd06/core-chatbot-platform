# core-chatbot-platform

Multi-tenant AI chatbot platform — ΕΝΑΣ κώδικας, ΜΙΑ βάση, ΕΝΑ deploy.

Stack: Flask + PostgreSQL/pgvector + OpenAI. Όλοι οι πελάτες τρέχουν στην ίδια
πλατφόρμα· ό,τι διαφέρει ανά πελάτη (ύφος, χρώματα, γνώση) ζει στη βάση με `client_id`.

## Δομή
- `01-data-layer/` — SQLAlchemy models (πίνακες με πρόθεμα `cp_`), σύνδεση βάσης, seed
- `02-config/` — ρυθμίσεις από environment variables, pre-flight έλεγχος
- `03-backend/` — Flask API: chat (RAG), leads, widget config, health, admin
- `04-widget/` — (Φάση 3)
- `05-onboarding/` — (Φάση 4)

## Render
- Build: `pip install -r requirements.txt`
- Start: `cd 03-backend && gunicorn "app:create_app()" --bind 0.0.0.0:$PORT`
- Python: 3.12.8 (runtime.txt)
- Env vars: βλ. `02-config/RENDER_ENV_SETUP.md`

## Πρώτη εκκίνηση (μία φορά)
1. Deploy στο Render με τα env vars.
2. `POST /api/v1/admin/setup` με header `X-API-Key: <API_KEY>` — φτιάχνει
   pgvector extension, πίνακες `cp_*` και demo πελάτη `demo`.
3. `POST /api/v1/admin/knowledge` — φορτώνει γνώση για έναν πελάτη.
4. Άνοιξε `/test` στον browser και δοκίμασε το chat.
