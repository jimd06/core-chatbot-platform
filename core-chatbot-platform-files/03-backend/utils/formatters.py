"""Μικρές βοηθητικές μορφοποιήσεις."""


def truncate(text: str, max_chars: int) -> str:
    if not text or max_chars <= 0 or len(text) <= max_chars:
        return text or ""
    return text[: max_chars - 1].rstrip() + "…"
