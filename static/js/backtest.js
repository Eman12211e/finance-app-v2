// Test a strategy (P5) inside Practice Trading: the setup form and the results of a hypothetical test from
// POST /api/backtest/run. Read-only: it sends the signed session and three choices and never changes the session, the
// practice account, orders or cash. Every sentence is the owner-approved text in docs/P5_CONTENT.md. The browser only
// formats the numbers the API returns; it works nothing out.
(function () {
  "use strict";

  var RULES = {
    sma_cross: { name: "SMA crossover 20 / 50",
                 line: "Buys when the 20-day average crosses above the 50-day average; sells when it crosses back below.",
                 start: "The test starts in cash and waits for a fresh crossing. If the 20-day average is already above "
                   + "the 50-day average on Day 50, that is not treated as a buy that happened earlier. The first crossing "
                   + "the test can see is on Day 51, so its first fill can be at the Day 52 open." },
    rsi_threshold: { name: "RSI 14 below 30 / above 70",
                     line: "Buys when RSI 14 closes below 30; sells when it closes above 70.",
                     start: "RSI 14 already has values on Day 50. If it closed below 30 that day, the rule buys at the Day "
                       + "51 open, the same day buy and hold buys. This rule could start sooner, but it uses the same Day "
                       + "50 start as the crossover rule so every test covers the same days." },
  };
  var COSTS = { example: "Example costs", none: "No costs" };
  var COST_POINT = {
    example: "Example costs: each fill is 0.10% worse than the opening price: a buy pays 0.10% more and a sell receives "
      + "0.10% less, rounded to the cent against the trader. No commission.",
    none: "No costs: every fill is at the opening price exactly. Real trading usually has some cost.",
  };
  var HOW = [
    "Decisions are made after each day's close, using only prices up to that day. They fill at the next day's opening "
      + "price, the same rule as your practice orders. The opening price can be different from the close the decision "
      + "was based on, sometimes by a lot.",
    "It starts with $10,000.00 in cash and buys as many whole shares as the cash allows, then sells all of them on the "
      + "way out. It never borrows, so cash never goes below zero. Cash left over after buying whole shares stays as cash.",
    null,  // the cost setting's point
    "Days 1–50 are price history used only to build the 50-day average. Nothing is invested and no return is counted "
      + "for them; the test and buy and hold both start at the Day 50 close.",
    "Only days you have reached in Practice Trading are used. Your practice account, orders and cash are not changed.",
  ];
  var NOT_A_FORECAST = "A backtest replays a fixed rule on prices that have already happened and reports what that rule "
    + "would have done. It cannot show what the rule would do on prices that have not happened yet. These prices were "
    + "made by a computer program, and even with real prices the past is only one of many ways things could have gone. "
    + "A rule can look good because it happened to suit this particular stretch of prices. The rules here use textbook "
    + "settings chosen before any of these prices existed, and nothing is adjusted to make them fit, but a fixed rule "
    + "is still only being tested on one set of prices.";
  var HALVES_NOTE = "This only describes what happened in two stretches of synthetic prices. It is not evidence that the "
    + "rule works, and neither half tells you how the other, or any later stretch, will go.";
  var STANDING = "This is a hypothetical test on computer-generated prices. A rule that did well here can do badly on "
    + "other prices. Past results, real or simulated, do not tell you what will happen next.";
  var MINUS = "−";

  var ctx = null;      // from paper.js: the verified session and its helpers
  var setupBox = null, resultsBox = null, form = null;
  var choice = { symbol: null, preset: "sma_cross", costs: "example" };
  var shown = null;    // what the results area shows: null (nothing yet), {data}, {error, message} or {cleared}
  var running = null;  // the request in flight: {preset, symbol, day}

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function money(cents) {
    var abs = Math.abs(cents);
    return (cents < 0 ? MINUS : "") + "$" + Math.floor(abs / 100).toLocaleString("en-US") + "."
      + String(abs % 100).padStart(2, "0");
  }

  function pct(value, signed) {  // the API's rounded percentage, shown with two decimals and a real minus sign
    var text = Math.abs(value).toFixed(2) + "%";
    if (value < 0) return MINUS + text;
    return (signed && value > 0 ? "+" : "") + text;
  }

  function changeSpan(value) {  // sign, arrow (CSS) and colour together, never colour alone
    return el("span", value > 0 ? "pt-up" : value < 0 ? "pt-down" : null, pct(value, true));
  }

  function shortDate(iso) {
    return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  }

  function longDate(iso) {
    return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US",
      { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }

  function dayOf(index) {
    return "Day " + (index + 1);
  }

  function plural(n, one, many) {
    return n + " " + (n === 1 ? one : many);
  }

  function para(cls, parts) {  // a paragraph from text and nodes
    var p = el("p", cls);
    parts.forEach(function (part) { p.appendChild(typeof part === "string" ? document.createTextNode(part) : part); });
    return p;
  }

  function panel(cls, headingTag, headingText, headingId) {
    var section = el("section", "card pt-bt-panel" + (cls ? " " + cls : ""));
    var h = el(headingTag, null, headingText);
    h.id = headingId;
    section.setAttribute("aria-labelledby", headingId);
    section.appendChild(h);
    return section;
  }

  function sim(text) {
    return el("span", "pt-sim", text || "Simulated");
  }

  // ---- the setup form (the order-ticket rail on wide screens, above the results on phones) ----

  function renderSetup() {
    setupBox.textContent = "";
    var f = el("form", "pt-bt-setup-form");
    f.setAttribute("aria-labelledby", "pt-bt-setup-title");
    f.noValidate = true;
    var head = el("div", "pt-ticket-head");
    var h = el("h2", null, "Test a strategy");
    h.id = "pt-bt-setup-title";
    head.appendChild(h);
    head.appendChild(sim());
    f.appendChild(head);
    f.appendChild(el("p", "pt-small", "Replay a fixed rule on the days you have reached, next to buying and holding the "
      + "same ticker."));

    var label = el("label", "pt-label", "Ticker");
    label.htmlFor = "pt-bt-symbol";
    var select = el("select", "pt-bt-select");
    select.id = "pt-bt-symbol";
    select.dataset.key = "bt-symbol";
    ctx.symbols().forEach(function (s) {
      var o = el("option", null, s);  // as in the mockups; the names are in the ticker list beside it
      o.value = s;
      select.appendChild(o);
    });
    select.value = choice.symbol;
    select.addEventListener("change", function () { choice.symbol = select.value; });
    var tickerField = el("div");
    tickerField.appendChild(label);
    tickerField.appendChild(select);
    f.appendChild(tickerField);

    f.appendChild(radios("Rule", "pt-bt-rule", Object.keys(RULES).map(function (k) {
      return { value: k, title: RULES[k].name, note: RULES[k].line };
    }), "preset"));
    f.appendChild(radios("Trading costs", "pt-bt-costs", [
      { value: "example", title: COSTS.example, note: "0.10% per fill" }, { value: "none", title: COSTS.none }], "costs"));

    var run = el("button", "button-primary pt-block", "Run test");
    run.type = "submit";
    run.dataset.key = "bt-run";
    f.appendChild(run);
    var status = el("p", "pt-tiny pt-bt-status visually-hidden");
    status.setAttribute("role", "status");
    f.appendChild(status);
    var foot = el("p", "pt-tiny muted");
    f.appendChild(foot);
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      runTest();
    });
    setupBox.appendChild(f);
    form = { select: select, run: run, status: status, foot: foot };
    updateSetup();
  }

  function radios(legendText, name, options, key) {
    var fs = el("fieldset", "pt-bt-choice");
    fs.appendChild(el("legend", "pt-label", legendText));
    options.forEach(function (o) {
      var row = el("label", "pt-bt-option");
      var input = el("input");
      input.type = "radio";
      input.name = name;
      input.value = o.value;
      input.checked = choice[key] === o.value;
      input.dataset.key = name + "-" + o.value;
      input.addEventListener("change", function () {
        if (!input.checked) return;
        choice[key] = o.value;
        if (!shown || !shown.data) renderResults();  // the How this test works points follow the choice until a run
      });
      row.appendChild(input);
      var text = el("span", "pt-bt-option-text");
      text.appendChild(el("strong", null, o.title));
      if (o.note) text.appendChild(el("span", "pt-tiny muted", o.note));
      row.appendChild(text);
      fs.appendChild(row);
    });
    return fs;
  }

  function updateSetup() {
    if (!form) return;
    form.foot.textContent = "Uses Days 1–" + (ctx.day().index + 1) + ". Your practice account is not changed.";
    form.run.textContent = running ? "Running test…" : "Run test";
    form.run.setAttribute("aria-disabled", running ? "true" : "false");  // stays focusable while busy
    form.status.textContent = running ? "Running " + RULES[running.preset].name + " on " + running.symbol + "." : "";
    form.status.classList.toggle("visually-hidden", !running);  // after a run it only announces; the result is below
  }

  // ---- the request ----

  function runTest() {
    if (running) return;
    var day = ctx.day().index;
    running = { preset: choice.preset, symbol: choice.symbol, costs: choice.costs, day: day };
    updateSetup();
    var req = running;
    window.Api.postBacktest({ state: ctx.state(), symbol: req.symbol, preset: req.preset, costs: req.costs })
      .then(function (env) {
        if (running !== req) return;  // the workspace was rebuilt meanwhile
        running = null;
        if (ctx.day().index !== req.day) {  // the practice day moved on while this ran: its answer is out of date
          shown = { cleared: true };
        } else if (env.ok) {
          shown = { data: env.data, day: req.day };
        } else if (env.error.code === "INVALID_STATE") {
          shown = null;
          ctx.onInvalidState(env.error.message);
          return;
        } else {
          shown = { error: env.error.code, message: env.error.message, request: req, day: req.day };
        }
        updateSetup();
        renderResults();
        form.status.textContent = announcement();
        var heading = resultsBox.querySelector("h2[tabindex]");
        if (heading) heading.focus();
      });
  }

  function announcement() {  // a short summary for the polite status line; the full result is under the heading
    if (!shown) return "";
    if (shown.cleared) return "";
    if (shown.error) return "The test could not run.";
    var d = shown.data;
    if (!d.result) return "Not enough data yet.";
    return "Test finished. " + outcomeText(d);
  }

  // ---- the results ----

  function renderResults() {
    resultsBox.textContent = "";
    if (shown && shown.error) {
      renderError();
    } else if (shown && shown.data && !shown.data.result) {
      renderNotEnough(shown.data);
    } else if (shown && shown.data) {
      renderResult(shown.data);
    } else {
      if (shown && shown.cleared) {
        resultsBox.appendChild(el("p", "pt-message", "The practice day changed, so the previous result was cleared. "
          + "Run the test again to include the new day."));
      }
      resultsBox.appendChild(howItWorks(choice.preset, choice.costs));
      resultsBox.appendChild(el("p", "pt-bt-standing", STANDING));
    }
  }

  function heading(text) {  // the results heading takes focus after Run test
    var h = el("h2", "pt-bt-title", text);
    h.id = "pt-bt-title";
    h.tabIndex = -1;
    return h;
  }

  function renderError() {
    var box = el("section", "card pt-bt-panel");
    box.setAttribute("aria-labelledby", "pt-bt-title");
    box.appendChild(heading("The test could not run"));
    var detail = shown.error === "NETWORK_ERROR" ? "The server did not answer." : shown.message;
    box.appendChild(el("p", "pt-error-line", detail + " Your practice session is unchanged."));
    var retry = el("button", "button-secondary", "Try again");
    retry.type = "button";
    retry.dataset.key = "bt-retry";
    retry.addEventListener("click", function () {
      choice.symbol = shown.request.symbol;
      choice.preset = shown.request.preset;
      choice.costs = shown.request.costs;
      renderSetup();
      runTest();
    });
    box.appendChild(retry);
    resultsBox.appendChild(box);
  }

  function renderNotEnough(d) {
    var box = el("section", "card pt-bt-panel pt-bt-waiting");
    box.setAttribute("aria-labelledby", "pt-bt-title");
    box.appendChild(heading("Not enough data yet"));
    box.appendChild(el("p", null, "This test needs " + d.needed_days + " trading days of history: 50 to build the 50-day "
      + "average and at least 20 to test on. You have reached " + d.available_days + " so far."));
    box.appendChild(el("p", "pt-small", "Advance " + (d.needed_days - d.available_days) + " more days in Practice "
      + "Trading to run it. Nothing is estimated in the meantime."));
    resultsBox.appendChild(box);
  }

  function pointsText(diff) {
    if (diff === 0) return null;
    return Math.abs(diff).toFixed(2) + " points " + (diff > 0 ? "higher" : "lower");
  }

  function outcomeText(d) {
    var r = d.result, s = r.strategy.metrics, b = r.benchmark.metrics;
    var points = pointsText(r.difference_pp);
    return "This rule ended at " + money(s.final_value_cents) + " (" + pct(s.total_return_pct, true) + "). Buying and "
      + "holding " + d.symbol + " over the same days ended at " + money(b.final_value_cents) + " ("
      + pct(b.total_return_pct, true) + "), so the rule ended "
      + (points ? points + "." : "level with buying and holding (0.00 points).");
  }

  function quiet(r) {  // no fills, no skipped entries and no signal on the last day
    return !r.strategy.fills.length && !r.strategy.skipped.length && !r.unacted_signal;
  }

  function renderResult(d) {
    var r = d.result, w = d.window, rule = RULES[d.preset];
    var main = el("section", "card pt-bt-panel pt-bt-results");
    main.setAttribute("aria-labelledby", "pt-bt-title");
    var head = el("div", "pt-bt-head");
    var title = heading(rule.name + " on " + d.symbol);
    head.appendChild(title);
    head.appendChild(sim("Simulated: hypothetical results on synthetic prices"));
    main.appendChild(head);
    main.appendChild(el("p", "pt-small", "Results are measured from the Day 50 close (" + shortDate(w.start_date)
      + "), when both start with $10,000.00 in cash, to the " + dayOf(w.last_index) + " close ("
      + longDate(w.last_date) + "): " + w.evaluation_days + " trading days. Days 1–50 are price history used only to "
      + "build the 50-day average; nothing is invested and no return is counted for them. " + COSTS[d.costs] + "."));
    if (quiet(r)) {
      main.appendChild(noTrades(d));
    } else {
      var points = pointsText(r.difference_pp);
      var s = r.strategy.metrics, b = r.benchmark.metrics;
      main.appendChild(para("pt-bt-outcome", ["This rule ended at ", el("strong", null, money(s.final_value_cents)),
        " (" + pct(s.total_return_pct, true) + "). Buying and holding " + d.symbol + " over the same days ended at ",
        el("strong", null, money(b.final_value_cents)), " (" + pct(b.total_return_pct, true) + "), so the rule ended ",
        el("strong", null, points || "level with buying and holding"), points ? "." : " (0.00 points)."]));
    }
    main.appendChild(metricsTable(r, w));
    resultsBox.appendChild(main);
    if (!quiet(r)) resultsBox.appendChild(fillsPanel(d));
    resultsBox.appendChild(howItWorks(d.preset, d.costs));
    resultsBox.appendChild(halvesPanel(d));
    resultsBox.appendChild(el("p", "pt-bt-standing", STANDING));
  }

  function noTrades(d) {
    var r = d.result, b = r.benchmark.metrics, last = dayOf(d.window.last_index);
    var box = el("div", "pt-bt-state");
    box.appendChild(el("h3", null, "No trades: the rule never triggered"));
    box.appendChild(el("p", "pt-small", d.preset === "sma_cross"
      ? "The 20-day average did not cross above the 50-day average from the Day 50 close to " + last
        + ", so the rule stayed in cash at $10,000.00 (0.00%)."
      : "RSI 14 never closed below 30 from the Day 50 close to " + last
        + ", so the rule stayed in cash at $10,000.00 (0.00%)."));
    box.appendChild(el("p", "pt-small", "Buying and holding " + d.symbol + " over the same days ended at "
      + money(b.final_value_cents) + " (" + pct(b.total_return_pct, true) + ")."));
    if (d.preset === "sma_cross") {
      box.appendChild(el("p", "pt-small muted", "The test starts in cash and waits for a fresh crossing. It does not "
        + "assume a trade happened before the Day 50 close."));
    }
    return box;
  }

  function swatchHead(text, cls) {
    var th = el("th");
    th.scope = "col";
    var i = el("i", "pt-bt-swatch " + cls);
    i.setAttribute("aria-hidden", "true");
    th.appendChild(i);
    th.appendChild(document.createTextNode(text));
    return th;
  }

  function rowHead(text, note) {
    var th = el("th", null, text);
    th.scope = "row";
    if (note) th.appendChild(el("span", "pt-bt-note", note));
    return th;
  }

  function cell(content, label, note) {
    var td = el("td");
    td.dataset.label = label;
    td.appendChild(typeof content === "string" ? document.createTextNode(content) : content);
    if (note) td.appendChild(el("span", "pt-bt-note", note));
    return td;
  }

  function trades(m) {
    return plural(m.buys, "buy", "buys") + ", " + plural(m.sells, "sell", "sells");
  }

  function metricsTable(r, w) {
    var table = el("table", "pt-bt-table pt-bt-metrics");
    table.appendChild(el("caption", null, "Results from the Day 50 close to the " + dayOf(w.last_index) + " close ("
      + w.evaluation_days + " trading days)"));
    var thead = el("thead"), hr = el("tr"), corner = el("th");
    corner.scope = "col";
    corner.appendChild(el("span", "visually-hidden", "Measure"));
    hr.appendChild(corner);
    hr.appendChild(swatchHead("This rule", "pt-bt-strat"));
    hr.appendChild(swatchHead("Buy and hold", "pt-bt-bench"));
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = el("tbody");
    var rows = [
      ["Value at the end", function (m) { return money(m.final_value_cents); }],
      ["Total return", function (m) { return changeSpan(m.total_return_pct); }],
      ["Largest drop from a high", function (m) {
        return m.max_drawdown ? MINUS + pct(m.max_drawdown_pct) : "No drop";
      }, function (m) {
        return m.max_drawdown ? shortDate(m.max_drawdown.peak.date) + " to " + shortDate(m.max_drawdown.trough.date) : null;
      }],
      ["Daily volatility", function (m) { return pct(m.daily_volatility_pct); }],
      ["Trades", trades],
      ["Days invested", function (m) { return m.days_invested + " of " + m.evaluation_days; }],
      ["Costs paid", function (m) { return money(m.costs_paid_cents); }],
    ];
    rows.forEach(function (row) {
      var tr = el("tr");
      tr.appendChild(rowHead(row[0]));
      [["This rule", r.strategy.metrics], ["Buy and hold", r.benchmark.metrics]].forEach(function (side) {
        tr.appendChild(cell(row[1](side[1]), side[0], row[2] ? row[2](side[1]) : null));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    var tfoot = el("tfoot"), fr = el("tr");
    fr.appendChild(rowHead("Compared with buy and hold"));
    var points = pointsText(r.difference_pp);
    var td = cell(points ? points + " total return" : "Level with buy and hold (0.00 points)", "Compared with buy and hold");
    td.colSpan = 2;
    fr.appendChild(td);
    tfoot.appendChild(fr);
    table.appendChild(tfoot);
    return table;
  }

  function fillsPanel(d) {
    var r = d.result, s = r.strategy, last = d.window.last_index;
    var box = panel(null, "h3", "What the rule did", "pt-bt-fills-title");
    if (s.fills.length) {
      var table = el("table", "pt-bt-table pt-bt-fills");
      table.setAttribute("aria-labelledby", "pt-bt-fills-title");
      var heads = ["Signal at the close of", "Filled at the open of", "Action", "Shares", "Open", "Fill price", "Cost",
        "Cash after"];
      var thead = el("thead"), hr = el("tr");
      heads.forEach(function (h) {
        var th = el("th", null, h);
        th.scope = "col";
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      var tbody = el("tbody");
      s.fills.forEach(function (f) {
        var tr = el("tr");
        tr.appendChild(cell(dayOf(f.signal_index), heads[0], shortDate(f.signal_date)));
        tr.appendChild(cell(dayOf(f.index), heads[1], shortDate(f.date)));
        [f.side === "buy" ? "In: bought" : "Out: sold", String(f.shares), money(f.open_cents), money(f.price_cents),
          money(f.cost_cents), money(f.cash_after_cents)].forEach(function (v, i) {
          tr.appendChild(cell(v, heads[i + 2]));
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      box.appendChild(table);
    }
    s.skipped.forEach(function (k) {
      box.appendChild(el("p", "pt-small", "Signal at the close of " + dayOf(k.signal_index) + ": buy. Not filled: the "
        + "cash did not cover one share at the " + dayOf(k.index) + " fill price of " + money(k.price_cents)
        + ". The money stayed in cash."));
    });
    if (s.end.shares > 0) {
      box.appendChild(el("p", "pt-small", "Still holding " + s.end.shares + " shares at the end, valued at the "
        + dayOf(last) + " close of " + money(s.end.close_cents) + ". They were not sold, so no further cost was charged."));
    }
    if (r.unacted_signal) {
      box.appendChild(el("p", "pt-small", "Signal on " + dayOf(r.unacted_signal.index) + ", the last day so far: "
        + r.unacted_signal.side + ". Not acted on, because there is no next open yet."));
    }
    box.appendChild(benchmarkLine(r.benchmark));
    return box;
  }

  function benchmarkLine(b) {
    if (b.fills.length) {
      var f = b.fills[0];
      return el("p", "pt-small muted", "Buy and hold bought " + f.shares + " shares at the " + dayOf(f.index) + " open ("
        + money(f.open_cents) + ", fill price " + money(f.price_cents) + ") and kept them.");
    }
    var k = b.skipped[0];
    return el("p", "pt-small muted", "Buy and hold could not afford one share at the " + dayOf(k.index) + " open (fill "
      + "price " + money(k.price_cents) + "), so it stayed in cash.");
  }

  function howItWorks(preset, costs) {
    var section = el("section", "card pt-bt-panel");
    section.setAttribute("aria-label", "How this test works");
    var details = el("details", "pt-bt-how");
    details.open = true;
    details.appendChild(el("summary", null, "How this test works"));
    var list = el("ul", "pt-small");
    HOW.forEach(function (text) { list.appendChild(el("li", null, text || COST_POINT[costs])); });
    list.appendChild(el("li", null, RULES[preset].start));
    details.appendChild(list);
    details.appendChild(el("h4", null, "Why this is not a forecast"));
    details.appendChild(el("p", "pt-small", NOT_A_FORECAST));
    section.appendChild(details);
    return section;
  }

  function halvesPanel(d) {
    var h = d.result.halves;
    var box = panel("pt-bt-halves" + (h ? "" : " pt-bt-waiting"), "h3", "Earlier and later halves", "pt-bt-halves-title");
    if (!h) {
      box.appendChild(el("p", "pt-small", "Too short to split: each half needs at least 40 test days, and there are "
        + d.window.evaluation_days + " so far. Available from Day 130."));
      return box;
    }
    box.appendChild(el("p", "pt-small", "The same rule, tested again on each half from a fresh $10,000."));
    var table = el("table", "pt-bt-table");
    table.setAttribute("aria-labelledby", "pt-bt-halves-title");
    var thead = el("thead"), hr = el("tr");
    [["Stretch"], ["This rule", "pt-bt-strat"], ["Buy and hold", "pt-bt-bench"]].forEach(function (c) {
      if (c[1]) {
        hr.appendChild(swatchHead(c[0], c[1]));
      } else {
        var th = el("th", null, c[0]);
        th.scope = "col";
        hr.appendChild(th);
      }
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = el("tbody");
    [["Earlier half", h.earlier], ["Later half", h.later]].forEach(function (row) {
      var w = row[1].window, tr = el("tr");
      tr.appendChild(rowHead(row[0], dayOf(w.start_index) + " close to " + dayOf(w.last_index) + " close ("
        + shortDate(w.start_date) + " – " + shortDate(w.last_date) + ")"));
      tr.appendChild(cell(changeSpan(row[1].strategy.metrics.total_return_pct), "This rule"));
      tr.appendChild(cell(changeSpan(row[1].benchmark.metrics.total_return_pct), "Buy and hold"));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    box.appendChild(table);
    box.appendChild(el("p", "pt-small muted", HALVES_NOTE));
    return box;
  }

  // ---- hooks for paper.js ----

  window.Backtest = {
    // a new workspace (new session, reset, reload or market change): start with the trade ticker and no result
    mount: function (setup, results, context) {
      setupBox = setup;
      resultsBox = results;
      ctx = context;
      choice = { symbol: ctx.symbol(), preset: "sma_cross", costs: "example" };
      shown = null;
      running = null;
      renderSetup();
      renderResults();
    },
    setSymbol: function (symbol) {  // a click in the ticker list while this view is open
      choice.symbol = symbol;
      if (form) form.select.value = symbol;
    },
    dayChanged: function () {  // a result is only for the day it ran on
      if (!ctx) return;
      if (shown && (shown.data || shown.error) && shown.day !== ctx.day().index) {
        shown = { cleared: true };
        renderResults();
      }
      updateSetup();
    },
  };
})();
