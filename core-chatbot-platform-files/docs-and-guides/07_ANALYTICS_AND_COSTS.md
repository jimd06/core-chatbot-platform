# 07 — Analytics & Costs

## usage_log — τι μετράμε ανά client_id
- Μηνύματα, tokens (prompt + completion), embeddings, ημερομηνία.
- Από αυτό βγαίνει το μηνιαίο κόστος ΑΝΑ πελάτη → τεκμηρίωση τιμολόγησης.

## Τάξη μεγέθους κόστους (2026, gpt-4o-mini + text-embedding-3-small)
- Μια συνομιλία 10 μηνυμάτων: κλάσματα του λεπτού (<0,01€).
- Ingestion ενός μέσου site: λίγα λεπτά του ευρώ, ΜΙΑ φορά (μετά μόνο ό,τι άλλαξε — hash).
- Το πραγματικό κόστος κλιμάκωσης είναι τα chat completions, όχι το hosting.

## Έλεγχος κόστους
- `max_tokens` + όριο ιστορικού + όριο μήκους μηνύματος (βλ. 02).
- Budget alert στο OpenAI dashboard (π.χ. 20€/μήνα αρχικά).
- Μηνιαίο query: σύνολο tokens ανά client_id από usage_log.

## KPIs για τον πελάτη (μελλοντικό panel, Module 07)
- Συνομιλίες/μήνα, leads/μήνα, % αναπάντητων (is_unanswered) → τι λείπει από τη γνώση.
