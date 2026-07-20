"""Build: ενώνει src/widget.js + src/widget.css → build/widget.js.

Τρέχει με:  python 04-widget/build.py
Το build/widget.js είναι το ΜΟΝΟ αρχείο που σερβίρεται στους πελάτες
(μέσω του route /widget.js του backend).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

js = (HERE / "src" / "widget.js").read_text(encoding="utf-8")
css = (HERE / "src" / "widget.css").read_text(encoding="utf-8")

# Απλή "συμπίεση" CSS: σβήνουμε σχόλια και περιττά κενά.
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
css = re.sub(r"\s+", " ", css).strip()

# json.dumps → ασφαλές escape του CSS ως JavaScript string.
built = js.replace('"__WIDGET_CSS__"', json.dumps(css))

out = HERE / "build" / "widget.js"
out.write_text(built, encoding="utf-8")
print(f"OK → {out} ({out.stat().st_size} bytes)")
