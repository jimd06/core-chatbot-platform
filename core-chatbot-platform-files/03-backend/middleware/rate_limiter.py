"""Απλό in-memory rate limiting ανά IP (αρκετό για ένα gunicorn service).

Αν αργότερα τρέξουν πολλά instances, αντικαθίσταται με Redis — όχι τώρα.
"""
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

_hits = defaultdict(deque)  # ip -> χρόνοι αιτημάτων (τελευταίο 60s)


def rate_limit(max_per_minute):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?")
            ip = ip.split(",")[0].strip()
            now = time.time()
            q = _hits[ip + ":" + fn.__name__]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= max_per_minute:
                return jsonify({"error": "Πολλά αιτήματα — δοκιμάστε σε λίγο."}), 429
            q.append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
