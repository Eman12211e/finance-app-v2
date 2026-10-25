// Owner: Agent B. Watchlist in #watchlist-root, stored in localStorage.
(function () {
  "use strict";

  var KEY = "fe_watchlist";
  var DEFAULT = ["AAPL", "MSFT", "KO", "NVDA", "VOO"];
  var MAX = 8;
  var TICKER_RE = /^[A-Z]{1,5}(\.[A-Z])?$/;

  var tickers = [];
  var selected = null;
  var els = {};

  function load() {
    try {
      var stored = JSON.parse(localStorage.getItem(KEY));
      if (Array.isArray(stored)) {
        return stored.filter(function (t) { return typeof t === "string" && TICKER_RE.test(t); }).slice(0, MAX);
      }
    } catch (e) { /* fall through to defaults */ }
    return DEFAULT.slice();
  }

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(tickers));
    } catch (e) { /* storage unavailable: keep the list for this session only */ }
  }

  function fire(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail: detail }));
  }

  function changed() {
    save();
    render();
    fire("app:watchlist-changed", { tickers: tickers.slice() });
  }

  function select(ticker) {
    selected = ticker;
    render();
    fire("app:ticker-selected", { ticker: ticker });
  }

  function remove(ticker) {
    tickers = tickers.filter(function (t) { return t !== ticker; });
    changed();
    if (selected === ticker) select(tickers.length ? tickers[0] : null);
  }

  function showMessage(text) {
    els.message.textContent = text;
  }

  function add(raw) {
    var ticker = (raw || "").trim().toUpperCase();
    if (!TICKER_RE.test(ticker)) return showMessage("Use 1 to 5 letters, like AAPL or BRK.B.");
    if (tickers.indexOf(ticker) !== -1) return showMessage("That ticker is already on your watchlist.");
    if (tickers.length >= MAX) return showMessage("Your watchlist can hold up to " + MAX + " tickers.");
    showMessage("");
    els.input.value = "";
    tickers.push(ticker);
    changed();
    select(ticker);
  }

  function render() {
    els.list.textContent = "";
    tickers.forEach(function (t) {
      var li = document.createElement("li");
      var pick = document.createElement("button");
      pick.type = "button";
      pick.className = "ticker-button" + (t === selected ? " is-selected" : "");
      pick.textContent = t;
      pick.setAttribute("aria-pressed", t === selected ? "true" : "false");
      pick.addEventListener("click", function () { select(t); });
      var rm = document.createElement("button");
      rm.type = "button";
      rm.className = "remove-button";
      rm.textContent = "×";
      rm.setAttribute("aria-label", "Remove " + t + " from watchlist");
      rm.addEventListener("click", function () { remove(t); });
      li.appendChild(pick);
      li.appendChild(rm);
      els.list.appendChild(li);
    });
    if (!tickers.length) {
      var empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Add a ticker to get started.";
      els.list.appendChild(empty);
    }
  }

  function build(root) {
    els.list = document.createElement("ul");
    els.list.className = "watchlist";
    var form = document.createElement("form");
    form.className = "watchlist-add";
    var label = document.createElement("label");
    label.className = "visually-hidden";
    label.htmlFor = "watchlist-input";
    label.textContent = "Add a ticker";
    els.input = document.createElement("input");
    els.input.id = "watchlist-input";
    els.input.type = "text";
    els.input.placeholder = "Add ticker";
    els.input.autocomplete = "off";
    els.input.maxLength = 7;
    var btn = document.createElement("button");
    btn.type = "submit";
    btn.className = "button-secondary";
    btn.textContent = "Add";
    els.message = document.createElement("p");
    els.message.className = "form-message";
    els.message.setAttribute("aria-live", "polite");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      add(els.input.value);
    });
    form.appendChild(label);
    form.appendChild(els.input);
    form.appendChild(btn);
    root.appendChild(els.list);
    root.appendChild(form);
    root.appendChild(els.message);
  }

  window.Watchlist = {
    init: function () {
      var root = document.getElementById("watchlist-root");
      if (!root) return;
      tickers = load();
      build(root);
      render();
      // Auto-select after every module's init() has run, so Company is already listening.
      if (tickers.length) setTimeout(function () { select(tickers[0]); }, 0);
    },
    get: function () {
      return tickers.slice();
    },
  };
})();
