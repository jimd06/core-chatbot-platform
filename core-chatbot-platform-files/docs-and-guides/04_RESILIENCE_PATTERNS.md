# 04 — Resilience Patterns

## Όταν «πέφτει» το OpenAI
- Timeout στην κλήση (π.χ. 30s) + 1 retry.
- Αν αποτύχει: φιλικό fallback μήνυμα («Αντιμετωπίζουμε τεχνικό πρόβλημα, δοκιμάστε ξανά ή καλέστε μας στο ...») — ΠΟΤΕ stack trace στον χρήστη.

## Όταν «πέφτει» η βάση
- Το /health ελέγχει DB connection → το Render το βλέπει.
- Connection pooling με `pool_pre_ping=True` (SQLAlchemy) — αποφεύγει «stale connections» μετά από idle.

## Render ιδιαιτερότητες
- Free/Starter services κάνουν sleep → πρώτο request αργεί. Λύση: paid plan ή uptime pinger στο /health.
- Deploy = restart: το SessionStorage του widget κρατά το ιστορικό στον browser, όχι στον server.

## Γενικός κανόνας
- Κάθε εξωτερική κλήση (OpenAI, DB, crawl) μέσα σε try/except με log + καθαρό μήνυμα.
