// Owner: Agent C. Chat panel in #chat-root. Talks to the server only through window.Api.postChat.
(function () {
  "use strict";

  var HISTORY_LIMIT = 6;
  var STARTERS = ["What is EPS?", "What does revenue mean?", "What is an ETF?"];
  var NOTE = "The assistant explains ideas. It does not tell you what to buy or sell.";
  var STYLE =
    "#chat-root .chat-list{display:flex;flex-direction:column;gap:8px;max-height:420px;overflow-y:auto;margin:8px 0}" +
    "#chat-root .chat-msg{padding:8px 12px;border-radius:10px;max-width:90%;line-height:1.45;white-space:pre-wrap}" +
    "#chat-root .chat-user{align-self:flex-end;background:#e8eef9}" +
    "#chat-root .chat-assistant{align-self:flex-start;background:#f3f4f6}" +
    "#chat-root .chat-system{align-self:center;color:#8a1c1c;font-size:.9em}" +
    "#chat-root .chat-divider{align-self:center;color:#6b7280;font-size:.85em}" +
    "#chat-root .chat-starters{display:flex;flex-wrap:wrap;gap:6px}" +
    "#chat-root .chat-starters[hidden]{display:none}" +
    "#chat-root .chat-starters button,#chat-root .chat-link{border:1px solid #c7cbd1;background:#fff;border-radius:999px;padding:4px 10px;cursor:pointer;font:inherit}" +
    "#chat-root .chat-link{align-self:flex-start;border:none;background:none;color:#1d4ed8;text-decoration:underline;padding:0}" +
    "#chat-root textarea{width:100%;box-sizing:border-box;min-height:64px;font:inherit;padding:8px}" +
    "#chat-root .chat-row{display:flex;gap:8px;align-items:flex-end}" +
    "#chat-root .chat-row button{flex:none}" +
    "#chat-root .chat-note{font-size:.85em;color:#6b7280;margin-top:6px}" +
    "#chat-root :focus-visible{outline:2px solid #1d4ed8;outline-offset:2px}";

  var history = [];
  var context = null;
  var lastTicker = null;
  var busy = false;
  var els = {};

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function scrollDown() {
    els.list.scrollTop = els.list.scrollHeight;
  }

  function addMessage(role, text) {
    var node = el("div", "chat-msg chat-" + role, text);
    els.list.appendChild(node);
    scrollDown();
    return node;
  }

  function addChecklistLink() {
    var btn = el("button", "chat-link", "Open the pre-purchase checklist");
    btn.type = "button";
    btn.addEventListener("click", function () {
      document.dispatchEvent(new CustomEvent("app:open-checklist", { detail: {} }));
    });
    els.list.appendChild(btn);
    scrollDown();
  }

  function setBusy(value) {
    busy = value;
    els.send.disabled = value;
  }

  function send(text) {
    var message = (text || "").trim();
    if (!message || busy) return;
    els.starters.hidden = true;
    addMessage("user", message);
    els.input.value = "";
    setBusy(true);
    var thinking = addMessage("assistant", "Thinking...");

    var profile = window.Profile && window.Profile.get ? window.Profile.get() : null;
    window.Api.postChat({ message: message, history: history.slice(), profile: profile, context: context })
      .then(function (env) {
        thinking.remove();
        if (!env || !env.ok) {
          addMessage("system", env && env.error ? env.error.message : "Something went wrong. Please try again.");
          return;
        }
        addMessage("assistant", env.data.reply);
        if (env.data.show_checklist_link) addChecklistLink();
        history.push({ role: "user", content: message }, { role: "assistant", content: env.data.reply });
        history = history.slice(-HISTORY_LIMIT);
      })
      .catch(function () {
        thinking.remove();
        addMessage("system", "Something went wrong. Please try again.");
      })
      .then(function () {
        setBusy(false);
      });
  }

  function onCompanyLoaded(e) {
    var d = e.detail || {};
    context = { ticker: d.ticker, source: d.source, as_of: d.as_of, snapshot: d.snapshot, earnings: d.earnings };
    if (d.ticker && d.ticker !== lastTicker) {
      lastTicker = d.ticker;
      els.list.appendChild(el("div", "chat-divider", "Now looking at: " + d.ticker));
      scrollDown();
    }
  }

  function build(root) {
    var style = el("style");
    style.textContent = STYLE;
    document.head.appendChild(style);

    root.appendChild(el("h2", null, "Ask a question"));
    els.list = el("div", "chat-list");
    els.list.setAttribute("aria-live", "polite");
    root.appendChild(els.list);

    els.starters = el("div", "chat-starters");
    STARTERS.forEach(function (q) {
      var chip = el("button", null, q);
      chip.type = "button";
      chip.addEventListener("click", function () { send(q); });
      els.starters.appendChild(chip);
    });
    root.appendChild(els.starters);

    var row = el("div", "chat-row");
    els.input = el("textarea");
    els.input.maxLength = 500;
    els.input.setAttribute("aria-label", "Your question");
    els.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send(els.input.value);
      }
    });
    els.send = el("button", null, "Send");
    els.send.type = "button";
    els.send.addEventListener("click", function () { send(els.input.value); });
    row.appendChild(els.input);
    row.appendChild(els.send);
    root.appendChild(row);
    root.appendChild(el("p", "chat-note", NOTE));
  }

  window.Chat = {
    init: function () {
      var root = document.getElementById("chat-root");
      if (!root) return;
      build(root);
      document.addEventListener("app:company-loaded", onCompanyLoaded);
    },
  };
})();
