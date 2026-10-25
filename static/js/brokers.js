// Compare Brokerages tab in #brokers-root. Renders /api/brokerages data side by side; never scores or ranks firms.
// Inputs are checkboxes and one dropdown only: which firms, topics and filters to show. Nothing is saved or sent elsewhere.
(function () {
  "use strict";

  var root = null;
  var meta = null;
  var results = null;
  var form = null;

  var STATES = {
    source_check: ["Source-checked", "Matched word for word against the official source by the app's source check."],
    owner_check: ["Owner-checked", "Checked by the app owner in a browser against the official source. Not a regulatory certification."],
    varies: ["Depends on plan", "The firm offers several pricing plans, so there is no single answer."],
    unknown: ["Unknown", "Not verified yet. The reason and what you can check yourself are shown."],
  };
  var FILTER_RESULTS = { meets: "Meets", does_not_meet: "Does not meet", varies: "Depends on plan", unknown: "Unknown" };
  var TERMS = [
    ["Commission", "A fee a broker charges for placing a trade."],
    ["Per-contract fee", "An options fee charged for each contract you buy or sell. One contract usually covers 100 shares."],
    ["ETF", "An exchange-traded fund: one investment that holds many stocks or bonds and trades like a stock."],
    ["Fractional shares", "Part of one share, so you can invest a dollar amount instead of buying whole shares."],
    ["IRA", "An individual retirement account with tax benefits. Traditional and Roth IRAs are taxed differently."],
    ["Margin", "Money borrowed from the broker to invest, with interest. Losses can be larger than the money you put in."],
    ["Cash sweep", "Where the firm moves cash you have not invested, and what interest it pays you."],
    ["Payment for order flow", "Money a broker receives for sending your orders to certain trading firms. It is a conflict of interest."],
    ["Form CRS", "A short summary a firm must give you about its services, fees, conflicts and disciplinary history."],
    ["Legal entity", "The company you actually open the account with. A brand can use more than one company."],
  ];
  var DEFAULT_CRITERIA = ["minimums_fees", "trading_costs", "account_types", "fractional_shares", "retirement",
    "research_education", "advice", "cash_margin"];

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function link(href, text) {
    var a = el("a", null, text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.appendChild(el("span", "visually-hidden", " (opens in a new tab)"));
    return a;
  }

  function badge(state) {
    var b = el("span", "br-badge br-" + state, STATES[state][0]);
    b.title = STATES[state][1];
    return b;
  }

  function checkbox(name, value, label, checked, hint) {
    var wrap = el("label", "br-check");
    var box = el("input");
    box.type = "checkbox";
    box.name = name;
    box.value = value;
    box.checked = checked;
    wrap.appendChild(box);
    wrap.appendChild(el("span", null, " " + label));
    if (hint) wrap.appendChild(el("span", "br-small muted", hint));
    return wrap;
  }

  function picked(name) {
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]:checked'), function (b) { return b.value; });
  }

  // ---- results ----

  function sourceLine(cell) {
    var p = el("p", "br-source");
    var s = cell.source;
    p.appendChild(document.createTextNode(s.publisher + ": "));
    p.appendChild(link(s.url, s.title));
    var dates = [];
    if (s.effective) dates.push("effective " + s.effective);
    dates.push("checked " + cell.verified_on);
    p.appendChild(el("span", "br-dates", " · " + dates.join(" · ")));
    return p;
  }

  function renderCell(cell, firm) {
    var state = cell.kind === "unknown" ? "unknown" : cell.varies ? "varies" : cell.verification.method;
    var box = el("div", "br-cell br-cell-" + state);
    box.appendChild(el("p", "br-cell-firm", firm.brand));
    box.appendChild(badge(state));
    box.appendChild(el("p", "br-value", cell.display));
    if (cell.kind === "unknown") {
      box.appendChild(el("p", "br-small", "Why unknown: " + cell.reason));
      if (cell.to_verify) box.appendChild(el("p", "br-small", "What you can check: " + cell.to_verify));
      if (cell.check_url) {
        var where = el("p", "br-small");
        where.appendChild(document.createTextNode("Where: "));
        where.appendChild(link(cell.check_url, cell.check_url.replace(/^https:\/\//, "")));
        box.appendChild(where);
      }
    } else {
      var quote = el("blockquote", "br-quote", "“" + cell.quote + "”");
      box.appendChild(quote);
      box.appendChild(el("p", "br-small muted", cell.location));
      box.appendChild(sourceLine(cell));
      if (cell.verification.method === "owner_check") {
        box.appendChild(el("p", "br-small", "Checked by " + (cell.verification.by || "the app owner") + ". Not a regulatory certification."));
      }
    }
    if (cell.stale) box.appendChild(el("p", "br-stale", "May be out of date: checked " + cell.age_days + " days ago."));
    return box;
  }

  function guideLinks(criterion) {
    var wrap = el("p", "br-links");
    (criterion.accounts_101 || []).forEach(function (name) {
      var b = el("button", "button-secondary br-link-button", "Accounts 101: " + name);
      b.type = "button";
      b.addEventListener("click", function () { if (window.Accounts) window.Accounts.open(name); });
      wrap.appendChild(b);
    });
    if (criterion.guide && window.Sign && window.Sign.openAt) {
      var g = el("button", "button-secondary br-link-button", "Related guide in Understand Before You Sign");
      g.type = "button";
      g.dataset.doc = criterion.guide.doc;
      g.dataset.section = criterion.guide.section;
      g.addEventListener("click", function () {
        var tab = document.querySelector('[data-tab="sign"]');
        if (tab) tab.click();
        window.Sign.openAt(criterion.guide.doc, criterion.guide.section);
      });
      wrap.appendChild(g);
    }
    return wrap;
  }

  function renderFirmHeader(firms) {
    var head = el("div", "br-firms card");
    head.style.setProperty("--br-cols", firms.length);
    firms.forEach(function (f) {
      var card = el("div", "br-firm");
      card.appendChild(el("h3", null, f.brand));
      card.appendChild(el("p", "br-small", f.legal_entity + " · CRD " + f.crd));
      if (f.entity_note) card.appendChild(el("p", "br-small muted", f.entity_note));
      var bc = el("p", "br-small");
      bc.appendChild(link(f.brokercheck_url, "BrokerCheck record"));
      card.appendChild(bc);
      head.appendChild(card);
    });
    return head;
  }

  function renderFilters(data) {
    var box = el("section", "card br-filters-result");
    box.appendChild(el("h3", null, "Your filters"));
    box.appendChild(el("p", "br-small muted", "Shows which firms meet each filter you picked. “Unknown” and "
      + "“Depends on plan” are never counted as not meeting. Firms stay in alphabetical order."));
    data.filters.forEach(function (fl) {
      var row = el("div", "br-filter-row");
      row.appendChild(el("h4", null, fl.label));
      var chips = el("ul", "br-filter-chips");
      data.firms.forEach(function (f) {
        var r = fl.results[f.id];
        chips.appendChild(el("li", "br-result br-result-" + r, f.brand + ": " + FILTER_RESULTS[r]));
      });
      row.appendChild(chips);
      box.appendChild(row);
    });
    return box;
  }

  function renderFees(data) {
    var box = el("section", "card br-fees");
    data.fee_examples.forEach(function (fx) {
      box.appendChild(el("h3", null, "Example: " + fx.label + ", " + fx.quantity + " " + fx.unit + (fx.quantity > 1 ? "s" : "")));
      var ul = el("ul", "br-fee-list");
      data.firms.forEach(function (f) {
        var r = fx.results[f.id];
        ul.appendChild(el("li", null, f.brand + ": " + (r ? r.display + " in per-contract fees"
          : "not calculated (the fee is unknown or depends on the plan)")));
      });
      box.appendChild(ul);
      box.appendChild(el("p", "br-small muted", fx.note));
    });
    box.appendChild(el("p", "br-caution", "A $0 commission does not mean investing is free. Fund expenses, regulatory "
      + "fees, prices built into a trade, margin interest and other fees can still apply."));
    return box;
  }

  function renderResults(data) {
    results.textContent = "";
    results.appendChild(renderFirmHeader(data.firms));
    if (data.filters.length) results.appendChild(renderFilters(data));
    data.criteria.forEach(function (cr) {
      var sec = el("section", "card br-criterion");
      sec.appendChild(el("h3", null, cr.label));
      sec.appendChild(el("p", "br-explain", cr.explanation));
      if (cr.accounts_101 || cr.guide) sec.appendChild(guideLinks(cr));
      cr.rows.forEach(function (row) {
        var block = el("div", "br-row");
        block.appendChild(el("h4", null, row.label));
        var grid = el("div", "br-grid");
        grid.style.setProperty("--br-cols", data.firms.length);
        data.firms.forEach(function (f) { grid.appendChild(renderCell(row.cells[f.id], f)); });
        block.appendChild(grid);
        sec.appendChild(block);
      });
      results.appendChild(sec);
      if (cr.id === "trading_costs") results.appendChild(renderFees(data));
    });
  }

  function compare() {
    var firms = picked("br-firm");
    var message = form.querySelector(".br-message");
    message.textContent = "";
    if (firms.length < 2 || firms.length > 4) {
      message.textContent = "Choose between 2 and 4 firms to compare.";
      return;
    }
    var criteria = picked("br-criterion");
    if (!criteria.length) {
      message.textContent = "Choose at least one topic.";
      return;
    }
    results.textContent = "";
    results.appendChild(el("p", "muted", "Loading the comparison…"));
    window.Api.compareBrokerages({ firms: firms, criteria: criteria, filters: picked("br-filter"),
      quantity: form.querySelector("select").value }).then(function (env) {
      results.textContent = "";
      if (!env.ok) {
        results.appendChild(el("p", "error-text", env.error.message));
        return;
      }
      renderResults(env.data);
    });
  }

  // ---- layout ----

  function renderShell() {
    root.textContent = "";
    var intro = el("div", "card br-intro");
    var title = el("h2", null, "Compare Brokerages");
    title.id = "brokers-title";
    intro.appendChild(title);
    intro.appendChild(el("p", "br-lead", "Compare published facts about brokerage firms side by side, so you can see "
      + "costs, account options and limits before you choose where to open an account."));
    intro.appendChild(el("p", null, meta.notice + " " + meta.app_incentives));
    intro.appendChild(el("p", "br-small", "Features such as margin or options trading are not a sign that a strategy is "
      + "right for you or low-risk. Promotions are not shown and never affect this comparison."));
    meta.excluded.forEach(function (x) { intro.appendChild(el("p", "br-small muted", "Not included yet: " + x.brand + ". " + x.reason)); });
    var legend = el("ul", "br-legend");
    Object.keys(STATES).forEach(function (k) {
      var li = el("li");
      li.appendChild(badge(k));
      li.appendChild(document.createTextNode(" " + STATES[k][1]));
      legend.appendChild(li);
    });
    intro.appendChild(legend);
    var terms = el("details", "br-terms");
    terms.appendChild(el("summary", null, "What do these terms mean?"));
    var dl = el("dl");
    TERMS.forEach(function (t) { dl.appendChild(el("dt", null, t[0])); dl.appendChild(el("dd", null, t[1])); });
    terms.appendChild(dl);
    intro.appendChild(terms);
    root.appendChild(intro);

    var layout = el("div", "br-layout");
    form = el("form", "card br-controls");
    form.setAttribute("aria-label", "Comparison choices");
    var firmSet = el("fieldset");
    firmSet.appendChild(el("legend", null, "Firms (choose 2 to 4)"));
    meta.firms.forEach(function (f) { firmSet.appendChild(checkbox("br-firm", f.id, f.brand, true)); });
    form.appendChild(firmSet);
    var critSet = el("fieldset");
    critSet.appendChild(el("legend", null, "What matters to you"));
    meta.criteria.forEach(function (c) {
      critSet.appendChild(checkbox("br-criterion", c.id, c.label, DEFAULT_CRITERIA.indexOf(c.id) >= 0));
    });
    form.appendChild(critSet);
    var filterSet = el("fieldset");
    filterSet.appendChild(el("legend", null, "Optional filters"));
    meta.filters.forEach(function (fl) { filterSet.appendChild(checkbox("br-filter", fl.id, fl.label, false)); });
    form.appendChild(filterSet);
    var qty = el("label", "br-qty", "Options fee example: ");
    var select = el("select");
    [1, 5, 10].forEach(function (n) { var o = el("option", null, n + (n > 1 ? " contracts" : " contract")); o.value = n; select.appendChild(o); });
    qty.appendChild(select);
    form.appendChild(qty);
    var button = el("button", "button-primary", "Compare");
    button.type = "submit";
    form.appendChild(button);
    var message = el("p", "br-message error-text");
    message.setAttribute("role", "alert");
    form.appendChild(message);
    form.addEventListener("submit", function (e) { e.preventDefault(); compare(); });
    layout.appendChild(form);
    results = el("div", "br-results");
    results.setAttribute("aria-live", "polite");
    layout.appendChild(results);
    root.appendChild(layout);
    compare();
  }

  function show() {
    if (!root || meta) return;
    root.textContent = "";
    root.appendChild(el("p", "muted", "Loading the comparison…"));
    window.Api.getBrokerages().then(function (env) {
      if (!env.ok) {
        root.textContent = "";
        root.appendChild(el("p", "error-text", env.error.message));
        return;
      }
      meta = env.data;
      renderShell();
    });
  }

  window.Brokers = {
    init: function () { root = document.getElementById("brokers-root"); },
    show: show,
  };
})();
