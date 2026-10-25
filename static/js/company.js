// Owner: Agent B. Snapshot + earnings panel. Shows server display strings only; never formats financial numbers.
(function () {
  "use strict";

  var NA = "Data not available";
  var EARNINGS_NOTE = "Numbers come from company reports and data providers. Explanations are general education, not advice.";
  var SECTION_ORDER = ["revenue", "profit", "eps", "cash", "dividend"];

  var current = null;
  var selectionId = 0; // stale-response guard: bumps on every ticker selection
  var earningsId = 0; // bumps on every earnings request (ticker or profile change)
  var snapRoot, earnRoot;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function disp(f) {
    return f && typeof f.display === "string" ? f.display : NA;
  }

  function str(v) {
    return typeof v === "string" && v ? v : NA;
  }

  // Dates are not financial numbers; ISO dates are shown as "Jun 27, 2026" in UTC so they never shift a day.
  function dateText(iso) {
    if (!iso) return null;
    var d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    if (isNaN(d)) return null;
    var opts = { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" };
    return d.toLocaleDateString("en-US", opts);
  }

  function badgeText(source, asOf) {
    if (source === "demo") return "Demo data (as of " + (dateText(asOf) || NA) + ")";
    if (source === "cache") {
      var d = new Date(asOf);
      var time = isNaN(d) ? NA : d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
      return "Saved data (as of " + time + ")";
    }
    if (source === "live") return "Live data";
    return null;
  }

  function fireLoaded() {
    if (!current) return;
    document.dispatchEvent(new CustomEvent("app:company-loaded", {
      detail: {
        ticker: current.ticker, source: current.source, as_of: current.as_of,
        snapshot: current.snapshot, earnings: current.earnings,
      },
    }));
  }

  function skeleton(root, label) {
    root.textContent = "";
    root.removeAttribute("data-explanation-source");
    root.setAttribute("aria-busy", "true");
    root.appendChild(el("p", "visually-hidden", label));
    for (var i = 0; i < 4; i++) root.appendChild(el("div", "skeleton"));
  }

  function showError(root, message, retry) {
    root.textContent = "";
    root.removeAttribute("aria-busy");
    root.removeAttribute("data-explanation-source");
    root.appendChild(el("p", "error-text", message || "Something went wrong. Please try again."));
    var btn = el("button", "button-secondary", "Try again");
    btn.type = "button";
    btn.addEventListener("click", retry);
    root.appendChild(btn);
  }

  function row(dl, label, value) {
    dl.appendChild(el("dt", null, label));
    dl.appendChild(el("dd", null, value));
  }

  // ---- snapshot ----

  function renderSnapshot() {
    var s = current.snapshot;
    snapRoot.textContent = "";
    snapRoot.removeAttribute("aria-busy");

    var head = el("div", "card-head");
    var title = el("h2", "company-name", s.name || s.ticker);
    head.appendChild(title);
    head.appendChild(el("span", "ticker-tag", s.ticker));
    if (s.is_etf) head.appendChild(el("span", "etf-tag", "ETF"));
    var badge = badgeText(current.source, current.as_of);
    if (badge) head.appendChild(el("span", "source-badge source-" + current.source, badge));
    snapRoot.appendChild(head);

    var priceRow = el("div", "price-row");
    priceRow.appendChild(el("span", "price", disp(s.price)));
    var change = s.change_percent || {};
    var dir = change.value > 0 ? "up" : change.value < 0 ? "down" : "flat";
    priceRow.appendChild(el("span", "change change-" + dir, disp(change)));
    snapRoot.appendChild(priceRow);

    var dl = el("dl", "facts");
    row(dl, "Sector", str(s.sector));
    row(dl, "Exchange", str(s.exchange));
    row(dl, "Market cap", disp(s.market_cap));
    row(dl, "Dividend yield", disp(s.dividend_yield));
    if (s.is_etf) row(dl, "Expense ratio", disp(s.expense_ratio));
    snapRoot.appendChild(dl);

    snapRoot.appendChild(el("p", "description", str(s.description)));

    var profile = window.Profile && window.Profile.get();
    var note = profile && window.Profile.noteFor(profile.risk);
    if (note) snapRoot.appendChild(el("p", "profile-note", note));
  }

  // ---- earnings ----

  function line(parent, label, value) {
    if (value === undefined || value === null) return;
    var p = el("p", "detail");
    p.appendChild(el("span", "detail-label", label + ": "));
    p.appendChild(document.createTextNode(value));
    parent.appendChild(p);
  }

  function explain(parent, text) {
    if (typeof text === "string" && text) parent.appendChild(el("p", "explain", text));
  }

  function renderSection(key, sec) {
    var box = el("section", "earnings-section");
    box.appendChild(el("h4", null, sec.title || key));
    if (key === "revenue" || key === "profit") {
      box.appendChild(el("p", "main-value", disp(sec.value)));
      line(box, "Same quarter last year", disp(sec.prior_year_value));
      line(box, "Change", disp(sec.change_percent));
    } else if (key === "eps") {
      if (sec.period_label) box.appendChild(el("p", "muted", sec.period_label));
      line(box, "Actual", disp(sec.actual));
      line(box, "Analyst estimate", disp(sec.estimate));
      line(box, "Difference", disp(sec.difference));
      line(box, "Reported", dateText(sec.report_date));
      if (sec.source_label) box.appendChild(el("p", "muted", sec.source_label));
    } else if (key === "cash") {
      box.appendChild(el("p", "main-value", disp(sec.value)));
    } else if (key === "dividend") {
      line(box, "Pays a dividend", sec.pays_dividend === true ? "Yes" : sec.pays_dividend === false ? "No" : NA);
      line(box, "Last dividend per share", disp(sec.last_amount));
      line(box, "Ex-dividend date", dateText(sec.last_ex_date) || NA);
    }
    explain(box, sec.explain);
    return box;
  }

  function renderEarnings() {
    var d = current.earnings;
    earnRoot.textContent = "";
    earnRoot.removeAttribute("aria-busy");
    if (d.explanation_source) earnRoot.setAttribute("data-explanation-source", d.explanation_source);

    earnRoot.appendChild(el("h2", null, "Earnings"));
    if (d.is_etf) {
      earnRoot.appendChild(el("p", "etf-message", d.etf_message));
      explain(earnRoot, d.etf_explain);
    } else {
      if (d.period && d.period.label) earnRoot.appendChild(el("p", "muted", d.period.label));
      if (d.headline) {
        earnRoot.appendChild(el("p", "headline", d.headline.label || NA));
        explain(earnRoot, d.headline.explain);
      }
      var sections = d.sections || {};
      SECTION_ORDER.forEach(function (key) {
        if (sections[key]) earnRoot.appendChild(renderSection(key, sections[key]));
      });
    }

    var questions = d.questions_to_think_about || [];
    if (questions.length) {
      earnRoot.appendChild(el("h3", null, "Questions to think about"));
      var ul = el("ul", "questions");
      questions.forEach(function (q) { ul.appendChild(el("li", null, q)); });
      earnRoot.appendChild(ul);
    }
    earnRoot.appendChild(el("p", "note", EARNINGS_NOTE));
  }

  function showProfilePrompt() {
    earnRoot.textContent = "";
    earnRoot.removeAttribute("aria-busy");
    earnRoot.appendChild(el("p", "muted", "Choose your profile to see the earnings explanations."));
    var btn = el("button", "button-secondary", "Set your profile");
    btn.type = "button";
    btn.addEventListener("click", function () { window.Profile.open(); });
    earnRoot.appendChild(btn);
  }

  // ---- loading ----

  function loadEarnings() {
    if (!current) return;
    var sel = selectionId;
    var id = ++earningsId;
    var ticker = current.ticker;
    var profile = window.Profile && window.Profile.get();
    if (!profile) return showProfilePrompt();
    skeleton(earnRoot, "Loading earnings");
    window.Api.getEarnings(ticker, profile).then(function (env) {
      if (sel !== selectionId || id !== earningsId) return; // a newer request owns the panel
      if (!env || !env.ok) return showError(earnRoot, env && env.error && env.error.message, loadEarnings);
      current.earnings = env.data;
      if (!current.source) {
        current.source = env.source;
        current.as_of = env.as_of;
      }
      renderEarnings();
      fireLoaded();
    });
  }

  function loadSnapshot() {
    var sel = selectionId;
    var ticker = current.ticker;
    skeleton(snapRoot, "Loading company");
    window.Api.getSnapshot(ticker).then(function (env) {
      if (sel !== selectionId) return;
      if (!env || !env.ok) return showError(snapRoot, env && env.error && env.error.message, loadSnapshot);
      current.snapshot = env.data;
      current.source = env.source;
      current.as_of = env.as_of;
      renderSnapshot();
      fireLoaded();
    });
  }

  function onTickerSelected(e) {
    var ticker = e.detail && e.detail.ticker;
    selectionId++;
    if (!ticker) {
      current = null;
      snapRoot.textContent = "";
      earnRoot.textContent = "";
      snapRoot.appendChild(el("p", "muted", "Pick a ticker from your watchlist."));
      return;
    }
    current = { ticker: ticker, source: null, as_of: null, snapshot: null, earnings: null };
    loadSnapshot();
    loadEarnings();
  }

  function onProfileChanged() {
    if (!current) return;
    if (current.snapshot) renderSnapshot(); // profile note depends on risk
    current.earnings = null;
    loadEarnings();
  }

  window.Company = {
    init: function () {
      snapRoot = document.getElementById("snapshot-root");
      earnRoot = document.getElementById("earnings-root");
      if (!snapRoot || !earnRoot) return;
      snapRoot.appendChild(el("p", "muted", "Pick a ticker from your watchlist."));
      document.addEventListener("app:ticker-selected", onTickerSelected);
      document.addEventListener("app:profile-changed", onProfileChanged);
    },
    getCurrent: function () {
      if (!current) return null;
      return {
        ticker: current.ticker, source: current.source, as_of: current.as_of,
        snapshot: current.snapshot, earnings: current.earnings,
      };
    },
  };
})();
