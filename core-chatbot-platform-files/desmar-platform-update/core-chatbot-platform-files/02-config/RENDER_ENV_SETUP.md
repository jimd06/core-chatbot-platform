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

## Email ειδοποιήσεις (προαιρετικά)
Χωρίς αυτά, η πλατφόρμα δουλεύει κανονικά — απλώς παραλείπονται οι
ειδοποιήσεις (νέο lead, escalation).

| Όνομα | Τιμή |
|---|---|
| `SMTP_USER` | το Gmail αποστολής (π.χ. `jim.ilioup@gmail.com`) |
| `SMTP_PASSWORD` | Gmail **App Password** 16 χαρακτήρων — ΜΟΝΟ εδώ, ΠΟΤΕ σε αρχείο ή repo |

Δημιουργία App Password: Google Account → Ασφάλεια → Επαλήθευση σε 2 βήματα
(πρέπει να είναι ενεργή) → https://myaccount.google.com/apppasswords →
νέο password με όνομα «Desmar Render» → αντιγραφή των 16 χαρακτήρων.
Προαιρετικά: `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT` (default `587`).

## Μετά το πρώτο deploy (μία φορά)
1. `POST https://<service>.onrender.com/api/v1/admin/setup`
   με header `X-API-Key: <API_KEY>` → φτιάχνει extension + πίνακες + demo πελάτη.
2. Έλεγχος: `GET /health` → 200.
3. Δοκιμή chat: άνοιξε `/test` στον browser.

## Ασφάλεια
- Το OPENAI_API_KEY ζει ΜΟΝΟ στο Render Environment. ΠΟΤΕ σε αρχείο του repo.
- Το ίδιο ισχύει για το SMTP_PASSWORD (Gmail App Password).
- Βάλε μηνιαίο spending cap στο platform.openai.com.
