"""Route /demo + σερβίρισμα του widget.

- GET /widget.js            → το χτισμένο 04-widget/build/widget.js
                              (αυτό βάζουν οι πελάτες στο snippet τους)
- GET /demo?client_id=XXX   → live δοκιμή του widget για οποιοδήποτε client_id
- GET /demo/<client_id>     → ίδιο με το παραπάνω· για DEMO clients (Chat 3)
                              δείχνει τη σελίδα υποψήφιου πελάτη: banner,
                              προτεινόμενες ερωτήσεις, όριο/λήξη και CTA.
"""
import os
import re

from flask import Blueprint, Response, render_template_string, request, send_file

demo_bp = Blueprint("demo", __name__)

# 03-backend/routes/demo.py → ρίζα repo → 04-widget/build/widget.js
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_WIDGET_BUILD = os.path.join(_REPO_ROOT, "04-widget", "build", "widget.js")

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


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


# ===========================================================================
# Demo-First (Chat 3): σελίδα υποψήφιου πελάτη + σελίδα λήξης
# ===========================================================================

DEMO_CLIENT_PAGE = """<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo — {{ business_name }}</title>
<style>
  :root { --accent: {{ primary_color }}; }
  body{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;
       padding:24px 16px 140px;color:#1f2430;background:#fafbfc}
  .banner{background:var(--accent);color:#fff;border-radius:10px;
          padding:12px 16px;font-size:14px;line-height:1.5;margin:0 0 22px}
  h1{font-size:24px;margin:0 0 6px}
  .hint{color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 18px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
  .chip{border:1.5px solid var(--accent);color:var(--accent);background:#fff;
        border-radius:999px;padding:9px 15px;font-size:14px;cursor:pointer;
        font-family:inherit}
  .chip:hover{background:var(--accent);color:#fff}
  .meta{color:#6b7280;font-size:13px;line-height:1.6;margin:0 0 26px}
  .cta{border:1.5px solid var(--accent);border-radius:12px;background:#fff;
       padding:16px 18px}
  .cta strong{color:var(--accent);font-size:16px}
  .cta p{margin:8px 0 0;font-size:14px;line-height:1.6;color:#3a3f4c}
  .cta a{color:var(--accent);font-weight:600;text-decoration:none}
</style>
</head>
<body>
<div class="banner">{{ banner }}</div>
<h1>Δοκιμάστε τον ψηφιακό βοηθό σας</h1>
<p class="hint">Πατήστε μια ερώτηση — ή ανοίξτε τη συνομιλία κάτω δεξιά και
ρωτήστε ό,τι θα ρωτούσε ένας πελάτης σας.</p>
{% if questions %}<div class="chips">
  {% for q in questions %}<button class="chip" type="button" data-q="{{ q }}">{{ q }}</button>
  {% endfor %}
</div>{% endif %}
<p class="meta">Δοκιμαστική έκδοση · απομένουν {{ answers_left }} από
{{ answer_limit }} απαντήσεις{% if expires_str %} · ενεργό έως {{ expires_str }}{% endif %}{% if not ready %}
· το chatbot εκπαιδεύεται ακόμα στο site σας ({{ pages_ok }}/{{ pages_total }} σελίδες
— δοκιμάστε ξανά σε λίγο){% endif %}</p>
<div class="cta">
  <strong>{{ cta_title }}</strong>
  <p>Το πλήρες chatbot μπαίνει στο site σας με μία γραμμή κώδικα και απαντά
  24/7, χωρίς όρια μηνυμάτων — από 69 €/μήνα.</p>
  <p><a href="mailto:{{ contact_email }}">{{ contact_email }}</a> ·
     <a href="tel:{{ contact_phone_tel }}">{{ contact_phone }}</a> · Desmar</p>
</div>
<script>
document.addEventListener("click", function (e) {
  var chip = e.target.closest(".chip");
  if (chip && window.CCPWidget) CCPWidget.ask(chip.dataset.q);
});
</script>
<script src="/widget.js" data-client-id="{{ client_id }}" async></script>
</body>
</html>"""


DEMO_EXPIRED_PAGE = """<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Το demo έληξε — {{ business_name }}</title>
<style>
  :root { --accent: #0B6E4F; }
  body{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;
       padding:48px 16px;color:#1f2430;background:#fafbfc}
  h1{font-size:24px;margin:0 0 10px}
  .hint{color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 26px}
  .cta{border:1.5px solid var(--accent);border-radius:12px;background:#fff;
       padding:16px 18px}
  .cta strong{color:var(--accent);font-size:16px}
  .cta p{margin:8px 0 0;font-size:14px;line-height:1.6;color:#3a3f4c}
  .cta a{color:var(--accent);font-weight:600;text-decoration:none}
</style>
</head>
<body>
<h1>Αυτό το δοκιμαστικό chatbot έχει λήξει</h1>
<p class="hint">Το demo της «{{ business_name }}» ήταν διαθέσιμο για
περιορισμένο διάστημα και απενεργοποιήθηκε.</p>
<div class="cta">
  <strong>Θέλετε το πλήρες chatbot στο site σας;</strong>
  <p>Απαντά 24/7 στους επισκέπτες σας, χωρίς όρια μηνυμάτων — από 69 €/μήνα
  (+ 100 € εφάπαξ εγκατάσταση).</p>
  <p><a href="mailto:{{ contact_email }}">{{ contact_email }}</a> ·
     <a href="tel:{{ contact_phone_tel }}">{{ contact_phone }}</a> · Desmar</p>
</div>
</body>
</html>"""


def _demo_state(client_id):
    """Κατάσταση demo client ή None (άγνωστος client / λείπει το make_demo /
    σφάλμα βάσης). Σε κάθε αποτυχία η σελίδα πέφτει ήπια στην κλασική
    DEMO_PAGE — η βιτρίνα δεν σκάει ποτέ μπροστά σε υποψήφιο πελάτη."""
    try:
        import make_demo  # το 05-onboarding μπαίνει στο sys.path από το app.py
        return make_demo.get_demo_state(client_id)
    except Exception:
        return None


def _render_demo_client(client_id, state):
    """Σελίδα demo υποψήφιου: banner, ερωτήσεις κλάδου, όριο/λήξη, CTA."""
    from demo_templates import (CONTACT_EMAIL, CONTACT_PHONE, CONTACT_PHONE_TEL,
                                DEMO_BANNER, DEMO_CTA_TITLE, expires_str_el,
                                industry_template)

    business_name = state.get("business_name") or state.get("name") or client_id
    color = state.get("primary_color") or "#0B6E4F"
    if not _COLOR_RE.match(color):
        color = "#0B6E4F"
    return render_template_string(
        DEMO_CLIENT_PAGE,
        client_id=client_id,
        business_name=business_name,
        banner=DEMO_BANNER.format(business_name=business_name),
        cta_title=DEMO_CTA_TITLE,
        questions=industry_template(state.get("industry"))["suggested_questions"],
        answers_left=state.get("answers_left", 0),
        answer_limit=state.get("answer_limit", 0),
        expires_str=expires_str_el(state.get("expires_at")),
        ready=(state.get("status") == "ready"),
        pages_ok=state.get("pages_ok", 0),
        pages_total=state.get("pages_total", 0),
        primary_color=color,
        contact_email=CONTACT_EMAIL,
        contact_phone=CONTACT_PHONE,
        contact_phone_tel=CONTACT_PHONE_TEL,
    )


def _render_demo_expired(client_id, state):
    from demo_templates import CONTACT_EMAIL, CONTACT_PHONE, CONTACT_PHONE_TEL

    return render_template_string(
        DEMO_EXPIRED_PAGE,
        business_name=state.get("business_name") or state.get("name") or client_id,
        contact_email=CONTACT_EMAIL,
        contact_phone=CONTACT_PHONE,
        contact_phone_tel=CONTACT_PHONE_TEL,
    )


@demo_bp.get("/demo")
@demo_bp.get("/demo/<client_id>")
def demo(client_id=None):
    client_id = (client_id or request.args.get("client_id") or "demo").strip()[:64]

    state = _demo_state(client_id)
    if state and state.get("is_demo"):
        if (state.get("expired") or not state.get("is_active")
                or state.get("status") == "expired"):
            return _render_demo_expired(client_id, state)
        return _render_demo_client(client_id, state)

    # Κανονικοί πελάτες / άγνωστα ids: η κλασική σελίδα δοκιμών, όπως πριν.
    return render_template_string(DEMO_PAGE, client_id=client_id)
