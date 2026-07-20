"""Validators — email, καθαρισμός strings, CORS έλεγχος ανά πελάτη."""
import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(value: str) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value))


def clean_str(value, max_len=2000) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def origin_allowed(origin: str, allowed_domain: str) -> bool:
    """Ελέγχει αν το Origin του browser ταιριάζει στο allowed_domain του πελάτη.

    - allowed_domain κενό  → επιτρέπονται όλα (δοκιμές/onboarding)
    - "example.gr"         → example.gr και www.example.gr
    - "*.example.gr"       → οποιοδήποτε subdomain + το example.gr
    - Χωρίς Origin header (curl) → επιτρέπεται
    - Origin ίδιο με το host της πλατφόρμας (η σελίδα /demo) → επιτρέπεται,
      ώστε το /demo να δουλεύει και για πελάτες που έχουν ήδη allowed_domain.
    """
    if not allowed_domain:
        return True
    if not origin:
        return True
    host = urlparse(origin).hostname or ""
    if not host:
        return False
    if host in ("localhost", "127.0.0.1"):
        return True  # τοπικές δοκιμές του πελάτη πριν το live

    # Same-origin: το αίτημα έρχεται από τη δική μας σελίδα /demo.
    try:
        from flask import has_request_context, request
        if has_request_context():
            our_host = (request.host or "").split(":")[0].lower()
            if our_host and host.lower() == our_host:
                return True
    except ImportError:
        pass

    allowed = allowed_domain.strip().lower()
    host = host.lower()
    if allowed.startswith("*."):
        base = allowed[2:]
        return host == base or host.endswith("." + base)
    return host == allowed or host == "www." + allowed
