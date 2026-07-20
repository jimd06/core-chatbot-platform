"""Route /demo + σερβίρισμα του widget.

- GET /widget.js            → το χτισμένο 04-widget/build/widget.js
                              (αυτό βάζουν οι πελάτες στο snippet τους)
- GET /demo?client_id=XXX   → live δοκιμή του widget για οποιοδήποτε client_id
"""
import os

from flask import Blueprint, Response, render_template_string, request, send_file

demo_bp = Blueprint("demo", __name__)

# 03-backend/routes/demo.py → ρίζα repo → 04-widget/build/widget.js
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_WIDGET_BUILD = os.path.join(_REPO_ROOT, "04-widget", "build", "widget.js")


@demo_bp.get("/widget.js")
def widget_js():
    if not os.path.exists(_WIDGET_BUILD):
        return Response("/* widget.js: το build λείπει — τρέξε 04-widget/build.py */",
                        mimetype="application/javascript"), 404
    resp = send_file(_WIDGET_BUILD, mimetype="application/javascript")
    # Μικρό cache: αλλαγές στο widget φαίνονται στους πελάτες μέσα σε 5 λεπτά.
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


DEMO_PAGE = """<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo — core-chatbot-platform</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:680px;margin:32px auto;
       padding:0 16px;color:#1f2430;background:#fafbfc}
  h1{font-size:22px}
  .bar{display:flex;gap:8px;margin:18px 0;flex-wrap:wrap}
  input{font-size:16px;padding:9px 12px;border:1px solid #cbd2dc;border-radius:8px}
  button{font-size:16px;padding:9px 16px;border:none;border-radius:8px;
         background:#2563eb;color:#fff;cursor:pointer}
  .hint{color:#6b7280;font-size:14px;line-height:1.6}
  code{background:#eef1f5;padding:2px 6px;border-radius:4px}
</style>
</head>
<body>
<h1>Demo widget</h1>
<p class="hint">Ενεργό client_id: <code>{{ client_id }}</code>.
Το widget εμφανίζεται κάτω δεξιά — ίδιος κώδικας, διαφορετικά χρώματα/γνώση ανά πελάτη.</p>
<div class="bar">
  <input id="cid" value="{{ client_id }}" placeholder="client_id">
  <button onclick="go()">Φόρτωσε client</button>
</div>
<p class="hint">Η σελίδα φορτώνει το widget ακριβώς όπως ο πελάτης:
<br><code>&lt;script src="/widget.js" data-client-id="{{ client_id }}" async&gt;&lt;/script&gt;</code></p>
<script>
function go(){
  const cid = document.getElementById('cid').value.trim();
  if(cid) window.location = '/demo?client_id=' + encodeURIComponent(cid);
}
document.getElementById('cid').addEventListener('keydown', e => { if(e.key==='Enter') go(); });
</script>
<script src="/widget.js" data-client-id="{{ client_id }}" async></script>
</body>
</html>"""


@demo_bp.get("/demo")
def demo():
    client_id = (request.args.get("client_id") or "demo").strip()[:64]
    return render_template_string(DEMO_PAGE, client_id=client_id)
