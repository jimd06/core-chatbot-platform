# 05 — GDPR Compliance

## Στο widget
- Consent πριν το πρώτο μήνυμα: σύντομο κείμενο + link σε πολιτική απορρήτου + κουμπί αποδοχής.
- Χωρίς αποδοχή → δεν αποθηκεύεται τίποτα, δεν φεύγει μήνυμα.

## Στο backend
- Endpoint διαγραφής: `DELETE /api/chat/visitor/<visitor_id>` — σβήνει conversations/messages/leads του visitor.
- Ελάχιστα δεδομένα: μόνο ό,τι χρειάζεται (μήνυμα, timestamp, visitor_id). Όχι IP στο μόνιμο log.

## Πολιτική διατήρησης
- Πρόταση: αυτόματη διαγραφή συζητήσεων μετά από 12 μήνες (μελλοντικό cron).

## Τι λες στον πελάτη σου (την επιχείρηση)
- Αυτός είναι ο Data Controller, εσύ ο Processor. Χρειάζεται αναφορά του chatbot στην πολιτική απορρήτου του site του.
- Τα δεδομένα μένουν σε EU region (Render Frankfurt) όπου γίνεται.
