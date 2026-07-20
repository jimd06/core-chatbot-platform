# Ρύθμιση Render — Web Service

## Βασικά
1. New → **Web Service** → σύνδεση με το repo `core-chatbot-platform` (branch: main).
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `cd 03-backend && gunicorn "app:create_app()" --bind 0.0.0.0:$PORT`
4. Το `runtime.txt` κλειδώνει Python 3.12.8 (το 3.14 ΔΕΝ δουλεύει με psycopg2-binary).

## Environment Variables (Settings → Environment)
| Όνομα | Τιμή |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Internal Database URL της dentalpoint-db |
| `OPENAI_API_KEY` | το κλειδί σου από platform.openai.com |
| `API_KEY` | δικός σου μυστικός κωδικός για τα /admin endpoints |

Προαιρετικά: `CHAT_MODEL`, `EMBEDDING_MODEL`, `CONFIDENCE_THRESHOLD`,
`RETRIEVAL_K`, `RATE_LIMIT_CHAT`, `RATE_LIMIT_LEAD`.

## Μετά το πρώτο deploy (μία φορά)
1. `POST https://<service>.onrender.com/api/v1/admin/setup`
   με header `X-API-Key: <API_KEY>` → φτιάχνει extension + πίνακες + demo πελάτη.
2. Έλεγχος: `GET /health` → 200.
3. Δοκιμή chat: άνοιξε `/test` στον browser.

## Ασφάλεια
- Το OPENAI_API_KEY ζει ΜΟΝΟ στο Render Environment. ΠΟΤΕ σε αρχείο του repo.
- Βάλε μηνιαίο spending cap στο platform.openai.com.
