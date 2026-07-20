/* ==========================================================================
   core-chatbot-platform — widget.js (πηγαίος κώδικας)

   Vanilla JavaScript, καμία εξωτερική βιβλιοθήκη.

   Ο πελάτης βάζει στο site του ΜΟΝΟ αυτό:
     <script src="https://<platform>/widget.js" data-client-id="XXX" async></script>

   Το widget:
   1. Βρίσκει το δικό του <script> tag → client_id + base URL της πλατφόρμας.
   2. Τραβάει configuration από  GET /api/v1/widget/<client_id>/config
      (χρώμα, λογότυπο, όνομα, welcome message).
   3. Ζητάει συγκατάθεση GDPR πριν από το πρώτο μήνυμα.
   4. Στέλνει μηνύματα σε  POST /api/v1/chat/<client_id>
      με {message, conversation_id, visitor_id} → {reply, conversation_id, ...}.
   5. Κρατάει ιστορικό/συγκατάθεση/visitor_id σε SessionStorage
      (σβήνονται όταν κλείσει το tab — GDPR-friendly by design).
   6. Link «Διαγραφή δεδομένων» → DELETE /api/v1/chat/<client_id>/visitor/<visitor_id>.

   ΣΗΜΕΙΩΣΗ BUILD: το __WIDGET_CSS__ παρακάτω αντικαθίσταται από το
   περιεχόμενο του widget.css όταν τρέχει το 04-widget/build.py.
   ========================================================================== */
(function () {
  "use strict";

  var WIDGET_CSS = ".ccp-root { --ccp-primary: #2563eb; --ccp-primary-text: #ffffff; position: fixed; bottom: 20px; right: 20px; z-index: 2147483000; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; font-size: 15px; line-height: 1.45; -webkit-font-smoothing: antialiased; } .ccp-root *, .ccp-root *::before, .ccp-root *::after { box-sizing: border-box; } .ccp-launcher { width: 60px; height: 60px; border: none; border-radius: 50%; background: var(--ccp-primary); color: var(--ccp-primary-text); cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25); transition: transform 0.15s ease, box-shadow 0.15s ease; padding: 0; } .ccp-launcher:hover { transform: scale(1.06); box-shadow: 0 8px 24px rgba(0,0,0,0.3); } .ccp-launcher svg { width: 28px; height: 28px; display: block; } .ccp-panel { position: absolute; bottom: 76px; right: 0; width: 360px; height: 520px; max-height: calc(100vh - 110px); background: #ffffff; border-radius: 16px; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.22); display: none; flex-direction: column; overflow: hidden; } .ccp-panel.ccp-open { display: flex; } .ccp-header { background: var(--ccp-primary); color: var(--ccp-primary-text); padding: 14px 16px; display: flex; align-items: center; gap: 10px; flex-shrink: 0; } .ccp-logo { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; background: rgba(255, 255, 255, 0.25); flex-shrink: 0; } .ccp-title { font-weight: 600; font-size: 15px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } .ccp-close { background: none; border: none; color: inherit; font-size: 22px; line-height: 1; cursor: pointer; padding: 2px 6px; opacity: 0.85; } .ccp-close:hover { opacity: 1; } .ccp-messages { flex: 1; overflow-y: auto; padding: 14px 12px; background: #f5f6f8; display: flex; flex-direction: column; gap: 8px; } .ccp-msg { max-width: 82%; padding: 9px 13px; border-radius: 14px; white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; } .ccp-msg-bot { align-self: flex-start; background: #ffffff; color: #1f2430; border: 1px solid #e6e8ee; border-bottom-left-radius: 4px; } .ccp-msg-user { align-self: flex-end; background: var(--ccp-primary); color: var(--ccp-primary-text); border-bottom-right-radius: 4px; } .ccp-msg-error { align-self: flex-start; background: #fdecec; color: #8a1f1f; border: 1px solid #f5c2c2; border-bottom-left-radius: 4px; font-size: 14px; } .ccp-typing { align-self: flex-start; background: #ffffff; border: 1px solid #e6e8ee; border-radius: 14px; border-bottom-left-radius: 4px; padding: 12px 15px; display: flex; gap: 5px; } .ccp-typing span { width: 7px; height: 7px; border-radius: 50%; background: #9aa1ad; animation: ccp-bounce 1.2s infinite ease-in-out; } .ccp-typing span:nth-child(2) { animation-delay: 0.15s; } .ccp-typing span:nth-child(3) { animation-delay: 0.3s; } @keyframes ccp-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-5px); opacity: 1; } } .ccp-inputbar { display: flex; gap: 8px; padding: 10px; background: #ffffff; border-top: 1px solid #e6e8ee; flex-shrink: 0; } .ccp-input { flex: 1; border: 1px solid #d6dae2; border-radius: 22px; padding: 10px 14px; font: inherit; outline: none; resize: none; background: #fff; color: #1f2430; } .ccp-input:focus { border-color: var(--ccp-primary); } .ccp-send { width: 42px; height: 42px; border: none; border-radius: 50%; background: var(--ccp-primary); color: var(--ccp-primary-text); cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0; } .ccp-send:disabled { opacity: 0.5; cursor: default; } .ccp-send svg { width: 18px; height: 18px; display: block; } .ccp-footer { text-align: center; font-size: 11px; color: #8a90a0; padding: 5px 10px 8px; background: #ffffff; flex-shrink: 0; } .ccp-footer a { color: #8a90a0; text-decoration: underline; cursor: pointer; } .ccp-consent { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 24px 20px; background: #f5f6f8; gap: 14px; } .ccp-consent p { margin: 0; color: #3a3f4c; font-size: 14px; } .ccp-consent-accept { border: none; border-radius: 22px; background: var(--ccp-primary); color: var(--ccp-primary-text); padding: 10px 26px; font: inherit; font-weight: 600; cursor: pointer; } .ccp-consent-decline { background: none; border: none; color: #8a90a0; font: inherit; font-size: 13px; text-decoration: underline; cursor: pointer; } @media (max-width: 480px) { .ccp-panel { position: fixed; inset: 0; width: 100%; height: 100%; max-height: none; border-radius: 0; bottom: 0; right: 0; } }";

  /* ---- 1. Ποιος πελάτης, ποια πλατφόρμα ---------------------------------- */
  var script =
    document.currentScript ||
    document.querySelector("script[data-client-id][src*='widget.js']");
  if (!script) return;

  var CLIENT_ID = script.getAttribute("data-client-id");
  if (!CLIENT_ID) return;

  // Το backend είναι στο ίδιο origin με το widget.js (π.χ. https://xxx.onrender.com)
  var BASE = new URL(script.src, window.location.href).origin;

  /* ---- SessionStorage κλειδιά -------------------------------------------- */
  var K = {
    consent: "ccp:" + CLIENT_ID + ":consent",
    visitor: "ccp:" + CLIENT_ID + ":visitor",
    conv: "ccp:" + CLIENT_ID + ":conv",
    history: "ccp:" + CLIENT_ID + ":history",
  };

  function ssGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function ssSet(key, value) {
    try { sessionStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }
  function ssDel(key) {
    try { sessionStorage.removeItem(key); } catch (e) { /* ignore */ }
  }

  function visitorId() {
    var v = ssGet(K.visitor);
    if (!v) {
      v = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : "v-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
      ssSet(K.visitor, v);
    }
    return v;
  }

  function loadHistory() {
    try { return JSON.parse(ssGet(K.history) || "[]"); } catch (e) { return []; }
  }
  function saveHistory(history) {
    ssSet(K.history, JSON.stringify(history.slice(-40))); // κρατάμε έως 40 μηνύματα
  }

  /* ---- 2. Δημιουργία UI --------------------------------------------------- */
  var config = {
    name: "Chat",
    primary_color: "#2563eb",
    logo_url: "",
    welcome_message: "Γεια σας! Πώς μπορώ να βοηθήσω;",
  };

  var root, panel, launcher, messagesEl, inputEl, sendBtn, consentEl, chatUI;
  var history = loadHistory();
  var sending = false;

  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // textContent = ασφαλές (όχι XSS)
    return node;
  }

  function injectCSS() {
    var style = document.createElement("style");
    style.textContent = WIDGET_CSS;
    document.head.appendChild(style);
  }

  function buildUI() {
    root = el("div", "ccp-root");
    root.style.setProperty("--ccp-primary", config.primary_color);

    // Launcher
    launcher = el("button", "ccp-launcher");
    launcher.setAttribute("aria-label", "Άνοιγμα συνομιλίας");
    launcher.innerHTML = ICON_CHAT;
    launcher.addEventListener("click", togglePanel);

    // Panel
    panel = el("div", "ccp-panel");

    // Header
    var header = el("div", "ccp-header");
    if (config.logo_url) {
      var logo = el("img", "ccp-logo");
      logo.src = config.logo_url;
      logo.alt = "";
      header.appendChild(logo);
    }
    header.appendChild(el("div", "ccp-title", config.name));
    var closeBtn = el("button", "ccp-close", "×");
    closeBtn.setAttribute("aria-label", "Κλείσιμο");
    closeBtn.addEventListener("click", togglePanel);
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Chat UI (μηνύματα + input + footer) — κρύβεται πίσω από το consent
    chatUI = document.createDocumentFragment();

    messagesEl = el("div", "ccp-messages");

    var inputbar = el("div", "ccp-inputbar");
    inputEl = el("input", "ccp-input");
    inputEl.type = "text";
    inputEl.placeholder = "Γράψτε το μήνυμά σας...";
    inputEl.maxLength = 2000;
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") send();
    });
    sendBtn = el("button", "ccp-send");
    sendBtn.setAttribute("aria-label", "Αποστολή");
    sendBtn.innerHTML = ICON_SEND;
    sendBtn.addEventListener("click", send);
    inputbar.appendChild(inputEl);
    inputbar.appendChild(sendBtn);

    var footer = el("div", "ccp-footer");
    var gdprLink = el("a", "", "Διαγραφή των δεδομένων μου");
    gdprLink.addEventListener("click", gdprDelete);
    footer.appendChild(gdprLink);

    chatUI.appendChild(messagesEl);
    chatUI.appendChild(inputbar);
    chatUI.appendChild(footer);

    root.appendChild(panel);
    root.appendChild(launcher);
    document.body.appendChild(root);
  }

  /* ---- 3. GDPR consent flow ---------------------------------------------- */
  function showConsent() {
    consentEl = el("div", "ccp-consent");
    consentEl.appendChild(
      el("p", "", "Για να συνομιλήσετε με τον ψηφιακό βοηθό, χρειάζεται η " +
        "συγκατάθεσή σας για την προσωρινή επεξεργασία της συνομιλίας " +
        "(GDPR). Μπορείτε να ζητήσετε διαγραφή ανά πάσα στιγμή.")
    );
    var accept = el("button", "ccp-consent-accept", "Συμφωνώ, ας μιλήσουμε");
    accept.addEventListener("click", function () {
      ssSet(K.consent, "1");
      panel.removeChild(consentEl);
      startChat();
    });
    var decline = el("button", "ccp-consent-decline", "Όχι, ευχαριστώ");
    decline.addEventListener("click", togglePanel);
    consentEl.appendChild(accept);
    consentEl.appendChild(decline);
    panel.appendChild(consentEl);
  }

  function startChat() {
    panel.appendChild(chatUI);
    if (history.length === 0) {
      addMsg("bot", config.welcome_message); // μόνο εμφάνιση — δεν πάει στον server
    } else {
      history.forEach(function (m) { addMsg(m.role === "user" ? "user" : "bot", m.content, true); });
    }
    inputEl.focus();
  }

  /* ---- 4. Μηνύματα -------------------------------------------------------- */
  function addMsg(kind, text, skipSave) {
    var cls = kind === "user" ? "ccp-msg ccp-msg-user"
      : kind === "error" ? "ccp-msg ccp-msg-error"
      : "ccp-msg ccp-msg-bot";
    messagesEl.appendChild(el("div", cls, text));
    messagesEl.scrollTop = messagesEl.scrollHeight;
    if (!skipSave && kind !== "error") {
      history.push({ role: kind === "user" ? "user" : "assistant", content: text });
      saveHistory(history);
    }
  }

  function showTyping() {
    var t = el("div", "ccp-typing");
    t.appendChild(el("span"));
    t.appendChild(el("span"));
    t.appendChild(el("span"));
    messagesEl.appendChild(t);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return t;
  }

  function send() {
    var text = inputEl.value.trim();
    if (!text || sending) return;
    sending = true;
    sendBtn.disabled = true;
    inputEl.value = "";
    addMsg("user", text);
    var typing = showTyping();

    fetch(BASE + "/api/v1/chat/" + encodeURIComponent(CLIENT_ID), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        conversation_id: ssGet(K.conv) || null,
        visitor_id: visitorId(),
      }),
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, data: d }; });
      })
      .then(function (res) {
        messagesEl.removeChild(typing);
        if (res.ok && res.data.reply) {
          if (res.data.conversation_id) ssSet(K.conv, String(res.data.conversation_id));
          addMsg("bot", res.data.reply);
        } else {
          addMsg("error", res.data.error || "Κάτι πήγε στραβά. Δοκιμάστε ξανά.");
        }
      })
      .catch(function () {
        if (typing.parentNode) messagesEl.removeChild(typing);
        addMsg("error", "Πρόβλημα σύνδεσης. Δοκιμάστε ξανά σε λίγο.");
      })
      .then(function () {
        sending = false;
        sendBtn.disabled = false;
        inputEl.focus();
      });
  }

  /* ---- 5. GDPR delete ----------------------------------------------------- */
  function gdprDelete() {
    if (!window.confirm("Να διαγραφούν όλα τα δεδομένα της συνομιλίας σας;")) return;
    fetch(
      BASE + "/api/v1/chat/" + encodeURIComponent(CLIENT_ID) +
      "/visitor/" + encodeURIComponent(visitorId()),
      { method: "DELETE" }
    )
      .catch(function () { /* ακόμα κι αν αποτύχει, καθαρίζουμε τοπικά */ })
      .then(function () {
        ssDel(K.conv);
        ssDel(K.history);
        history = [];
        messagesEl.textContent = "";
        addMsg("bot", "Τα δεδομένα σας διαγράφηκαν. " + config.welcome_message);
      });
  }

  /* ---- 6. Άνοιγμα/κλείσιμο ------------------------------------------------ */
  var chatStarted = false;
  function togglePanel() {
    var open = panel.classList.toggle("ccp-open");
    if (open && !chatStarted) {
      chatStarted = true;
      if (ssGet(K.consent) === "1") startChat();
      else showConsent();
    } else if (open && inputEl && inputEl.parentNode) {
      inputEl.focus();
    }
  }

  /* ---- 7. Εκκίνηση: config από το backend -------------------------------- */
  function init() {
    fetch(BASE + "/api/v1/widget/" + encodeURIComponent(CLIENT_ID) + "/config")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (cfg) {
        if (cfg) {
          config.name = cfg.name || config.name;
          config.primary_color = cfg.primary_color || config.primary_color;
          config.logo_url = cfg.logo_url || "";
          config.welcome_message = cfg.welcome_message || config.welcome_message;
        }
      })
      .catch(function () { /* με defaults αν αποτύχει το config */ })
      .then(function () {
        injectCSS();
        buildUI();
      });
  }

  if (document.body) init();
  else document.addEventListener("DOMContentLoaded", init);
})();
