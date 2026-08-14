"""Απλές ειδοποιήσεις email μέσω SMTP (Gmail App Password).

Best-effort by design:
- Η αποστολή γίνεται σε background thread — ΠΟΤΕ δεν καθυστερεί και ΠΟΤΕ
  δεν ρίχνει το request (lead ή chat), ό,τι κι αν πάει στραβά στο SMTP.
- Αν λείπουν SMTP_USER/SMTP_PASSWORD ή δεν υπάρχει παραλήπτης, η ειδοποίηση
  απλώς παραλείπεται (με log) — καμία εξαίρεση.
- Το thread ΔΕΝ αγγίζει τη βάση: ό,τι χρειάζεται (παραλήπτης, κείμενο)
  ετοιμάζεται πριν, μέσα στο request.

ΔΕΝ είναι το πλήρες module emails της Φάσης 5 — μόνο ό,τι χρειάζεται τώρα:
ειδοποίηση νέου lead και escalation από το chat.
"""
import logging
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

from platform_config import Config

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(Config.SMTP_USER and Config.SMTP_PASSWORD)


def _send(to_email: str, subject: str, body: str) -> None:
    """Τρέχει μέσα στο background thread — μόνο SMTP, καμία πρόσβαση σε βάση."""
    try:
        msg = EmailMessage()
        msg["From"] = formataddr(("Desmar Platform", Config.SMTP_USER))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Ειδοποίηση email στάλθηκε στο %s: %s", to_email, subject)
    except Exception:
        logger.exception("Αποτυχία ειδοποίησης email (to=%s) — συνεχίζουμε κανονικά",
                         to_email)


def send_async(to_email: str, subject: str, body: str) -> bool:
    """Στέλνει ειδοποίηση χωρίς να μπλοκάρει. Επιστρέφει True αν προγραμματίστηκε."""
    if not smtp_configured():
        logger.info("SMTP μη ρυθμισμένο (SMTP_USER/SMTP_PASSWORD) — παράλειψη ειδοποίησης.")
        return False
    if not to_email:
        logger.info("Χωρίς notification_email στον πελάτη — παράλειψη ειδοποίησης.")
        return False
    threading.Thread(target=_send, args=(to_email, subject, body), daemon=True).start()
    return True
