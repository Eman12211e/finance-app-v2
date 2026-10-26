// Practice Trading tab in #paper-root: a simulated, synthetic-price trading practice built on /api/paper.
// The signed session lives in localStorage; journal notes live in localStorage too and are never sent to the server.
// Nothing here is a real price, order, account or recommendation.
(function () {
  "use strict";

  var SESSION_KEY = "paper-session-v1";
  var JOURNAL_KEY = "paper-journal-v1";
  var root = null;
  var view = null;       // last verified view from the server
  var busy = false;      // one request at a time: double clicks and overlapping replies cannot race
  var draft = null;      // the previewed order awaiting Confirm or Cancel, with its fixed order id
  var started = false;
  var scenarioId = "synthetic-b";  // market for a new session; the start screen can change it, Reset keeps the current one

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function money(cents) {
    var sign = cents < 0 ? "-" : "";
    var abs = Math.abs(cents);
    var dollars = Math.floor(abs / 100).toLocaleString("en-US");
    return sign + "$" + dollars + "." + String(abs % 100).padStart(2, "0");
  }

  function signed(cents) {
    return (cents > 0 ? "+" : "") + money(cents);
  }

  // ---- browser storage (may be blocked or cleared; every access is guarded) ----

  function readSession() {
    try {
      var raw = window.localStorage.getItem(SESSION_KEY);
      return raw === null ? null : JSON.parse(raw);
    } catch (e) {
      return { damaged: true };
    }
  }

  function writeSession(state) {
    try { window.localStorage.setItem(SESSION_KEY, JSON.stringify(state)); } catch (e) { /* storage unavailable */ }
  }

  function readJournal() {
    try { return JSON.parse(window.localStorage.getItem(JOURNAL_KEY) || "{}") || {}; } catch (e) { return {}; }
  }

  function saveJournalNote(orderId, why, risks) {
    if (!why && !risks) return;
    var journal = readJournal();
    journal[orderId] = { why: why, risks: risks };
    try { window.localStorage.setItem(JOURNAL_KEY, JSON.stringify(journal)); } catch (e) { /* storage unavailable */ }
  }

  function clearAll() {
    try {
      window.localStorage.removeItem(SESSION_KEY);
      window.localStorage.removeItem(JOURNAL_KEY);
    } catch (e) { /* storage unavailable */ }
  }

  function newOrderId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "order-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
  }

  // ---- server calls: the only data sent is the signed session and the order numbers ----

  function call(path, body, onOk) {
    if (busy) return;
    if (view && path !== "new" && path !== "view") {
      var stored = readSession();
      if (stored && !stored.damaged && JSON.stringify(stored) !== JSON.stringify(view.state)) {
        // another tab changed the saved session: reload it instead of acting on a stale copy
        setMessage("Your practice session changed in another tab, so it was reloaded. Check it and try again.", true);
        draft = null;
        call("view", { state: stored }, accept);
        return;
      }
    }
    busy = true;
    render();
    window.Api.paperPost(path, body).then(function (env) {
      busy = false;
      if (env.ok) {
        onOk(env.data);
      } else if (env.error.code === "INVALID_STATE") {
        showDamaged(env.error.message);
        return;
      } else {
        setMessage(env.error.message, true);
      }
      render();
    });
  }

  function accept(data) {
    view = data;
    writeSession(data.state);
  }

  // ---- actions ----

  function startNew() {
    call("new", { scenario: view ? view.scenario.id : scenarioId }, function (data) {
      clearAll();
      accept(data);
      draft = null;
      setMessage("A new practice session started with $10,000.00 of fictional cash.", false);
    });
  }

  function previewOrder(form) {
    var shares = Number(form.querySelector('input[name="pt-shares"]').value);
    var order = {
      symbol: form.querySelector("select").value,
      side: form.querySelector('input[name="pt-side"]:checked').value,
      shares: Number.isInteger(shares) ? shares : form.querySelector('input[name="pt-shares"]').value,
    };
    call("preview", { state: view.state, order: order }, function (data) {
      draft = data.ok ? { id: newOrderId(), order: order, preview: data } : null;
      setMessage(data.ok ? "" : data.problems.map(function (p) { return p.message; }).join(" "), !data.ok);
    });
  }

  function confirmOrder(why, risks) {
    if (!draft) return;
    var d = draft;
    var order = { id: d.id, symbol: d.order.symbol, side: d.order.side, shares: d.order.shares };
    call("confirm", { state: view.state, order: order }, function (data) {
      accept(data);
      saveJournalNote(d.id, why, risks);  // stored locally only; the request above never contains it
      draft = null;
      setMessage(data.duplicate ? "That order was already queued, so it was not added twice."
        : "Order queued. It fills at the next simulated day's opening price.", false);
    });
  }

  function cancelOrder(orderId) {
    call("cancel", { state: view.state, order_id: orderId }, function (data) {
      accept(data);
      setMessage("Order cancelled.", false);
    });
  }

  function advance(days) {
    var remaining = days;
    function next() {
      if (remaining <= 0 || !view || view.day.ended) return;
      remaining -= 1;
      call("advance", { state: view.state, expected_day: view.day.index }, function (data) {
        accept(data);
        draft = null;
        setMessage("", false);
        if (remaining > 0 && !data.day.ended) setTimeout(next, 0);
      });
    }
    next();
  }

  // ---- rendering ----

  var message = { text: "", error: false };

  function setMessage(text, error) {
    message = { text: text, error: error };
  }

  function showDamaged(detail) {
    view = null;
    draft = null;
    root.textContent = "";
    root.appendChild(banner());
    var box = el("div", "card pt-damaged");
    box.setAttribute("role", "alert");
    box.appendChild(el("h2", null, "Your saved practice session could not be opened"));
    box.appendChild(el("p", null, detail || "The saved session is damaged or was changed."));
    box.appendChild(el("p", null, "It has not been replaced. You can start over, which deletes the saved practice "
      + "session and journal notes from this browser."));
    var again = el("button", "button-primary", "Start a new practice session");
    again.type = "button";
    again.addEventListener("click", startNew);
    box.appendChild(again);
    root.appendChild(box);
  }

  function banner() {
    var b = el("div", "pt-banner");
    b.setAttribute("role", "note");
    b.appendChild(el("p", "pt-banner-title", "SIMULATED PRACTICE: not real money, prices or trades"));
    b.appendChild(el("p", null, "All prices are synthetic, all balances are fictional, and no real securities are "
      + "bought or sold. This basic simulator leaves out fees, the bid-ask spread, slippage and market impact."));
    return b;
  }

  function stat(label, value, cls) {
    var box = el("div", "pt-stat");
    box.appendChild(el("p", "pt-stat-label", label));
    box.appendChild(el("p", "pt-stat-value" + (cls ? " " + cls : ""), value));
    return box;
  }

  function plClass(cents) {
    return cents > 0 ? "change-up" : cents < 0 ? "change-down" : "";
  }

  function summaryCard() {
    var p = view.portfolio;
    var card = el("section", "card pt-summary");
    card.setAttribute("aria-label", "Simulated account summary");
    var day = view.day;
    card.appendChild(el("p", "pt-day", "Simulated day " + (day.index + 1) + " of " + view.scenario.days + " · " + day.date
      + (day.ended ? " · scenario ended" : day.is_last ? " · last day" : "")));
    var grid = el("div", "pt-stats");
    grid.appendChild(stat("Fictional cash available", money(p.cash_cents)));
    grid.appendChild(stat("Simulated portfolio value", money(p.portfolio_value_cents)));
    grid.appendChild(stat("Realized gain/loss", signed(p.realized_pl_cents), plClass(p.realized_pl_cents)));
    grid.appendChild(stat("Unrealized gain/loss", signed(p.unrealized_pl_cents), plClass(p.unrealized_pl_cents)));
    grid.appendChild(stat("Total vs. $10,000 start", signed(p.total_pl_cents), plClass(p.total_pl_cents)));
    card.appendChild(grid);
    var controls = el("div", "pt-controls");
    [["Next day", 1], ["Next 5 days", 5]].forEach(function (c) {
      var b = el("button", "button-secondary", c[0]);
      b.type = "button";
      b.dataset.days = c[1];
      b.disabled = busy || day.ended;
      b.addEventListener("click", function () { advance(c[1]); });
      controls.appendChild(b);
    });
    var reset = el("button", "button-secondary pt-reset", "Reset simulation");
    reset.type = "button";
    reset.disabled = busy;
    reset.addEventListener("click", function () { renderResetConfirm(card); });
    controls.appendChild(reset);
    card.appendChild(controls);
    return card;
  }

  function renderResetConfirm(card) {
    if (card.querySelector(".pt-confirm-reset")) return;
    var box = el("div", "pt-confirm-reset");
    box.setAttribute("role", "alertdialog");
    box.appendChild(el("p", null, "Reset the simulation? This deletes your practice session and journal notes from "
      + "this browser and starts again with $10,000.00 of fictional cash. It cannot be undone."));
    var yes = el("button", "button-primary", "Yes, reset");
    yes.type = "button";
    yes.addEventListener("click", startNew);
    var no = el("button", "button-secondary", "Keep my session");
    no.type = "button";
    no.addEventListener("click", function () { box.remove(); });
    box.appendChild(yes);
    box.appendChild(no);
    card.appendChild(box);
    no.focus();
  }

  function ticket() {
    var form = el("form", "card pt-ticket");
    form.setAttribute("aria-label", "Practice order");
    form.appendChild(el("h3", null, "Practice order"));
    var symLabel = el("label", "field", "Fictional ticker ");
    var select = el("select");
    Object.keys(view.quotes).forEach(function (s) {
      var o = el("option", null, s + " · " + money(view.quotes[s].close_cents) + " simulated close");
      o.value = s;
      select.appendChild(o);
    });
    if (draft) select.value = draft.order.symbol;
    symLabel.appendChild(select);
    form.appendChild(symLabel);
    var sides = el("fieldset", "pt-sides");
    sides.appendChild(el("legend", null, "Buy or sell"));
    ["buy", "sell"].forEach(function (side) {
      var l = el("label");
      var r = el("input");
      r.type = "radio";
      r.name = "pt-side";
      r.value = side;
      r.checked = draft ? draft.order.side === side : side === "buy";
      l.appendChild(r);
      l.appendChild(document.createTextNode(" " + side.charAt(0).toUpperCase() + side.slice(1)));
      sides.appendChild(l);
    });
    form.appendChild(sides);
    var qty = el("label", "field", "Whole shares ");
    var input = el("input");
    input.type = "number";
    input.name = "pt-shares";
    input.min = "1";
    input.step = "1";
    input.max = "100000";
    input.inputMode = "numeric";
    input.value = draft ? draft.order.shares : "1";
    qty.appendChild(input);
    form.appendChild(qty);
    form.appendChild(el("p", "pt-small", "Market orders fill at the next simulated day's opening price, which can "
      + "differ from the preview. Cash only: no borrowing, short selling or options."));
    var preview = el("button", "button-primary", "Preview order");
    preview.type = "submit";
    preview.disabled = busy || view.day.ended;
    form.appendChild(preview);
    form.addEventListener("submit", function (e) { e.preventDefault(); previewOrder(form); });
    if (draft) form.appendChild(confirmPanel());
    return form;
  }

  function confirmPanel() {
    var p = draft.preview;
    var box = el("div", "pt-preview");
    box.setAttribute("aria-live", "polite");
    box.appendChild(el("h4", null, "Check before you confirm"));
    box.appendChild(el("p", null, (p.side === "buy" ? "Buy " : "Sell ") + p.shares + " " + p.symbol + ": estimated "
      + (p.side === "buy" ? "cost " : "proceeds ") + money(p.estimated_amount_cents) + " at today's simulated close of "
      + money(p.reference_close_cents) + " per share."));
    box.appendChild(el("p", "pt-small", p.fill_note));
    if (p.warning) box.appendChild(el("p", "error-text", p.warning));
    var journal = el("fieldset", "pt-journal");
    journal.appendChild(el("legend", null, "Practice journal (optional)"));
    journal.appendChild(el("p", "pt-small", "Saved only in this browser and never sent anywhere. Do not include "
      + "personal or account information."));
    var why = el("textarea");
    why.maxLength = 280;
    why.rows = 2;
    why.setAttribute("aria-label", "Why are you making this trade?");
    why.placeholder = "Why are you making this trade?";
    var risks = el("textarea");
    risks.maxLength = 280;
    risks.rows = 2;
    risks.setAttribute("aria-label", "What could go wrong?");
    risks.placeholder = "What could go wrong?";
    journal.appendChild(why);
    journal.appendChild(risks);
    box.appendChild(journal);
    var actions = el("div", "pt-actions");
    var confirm = el("button", "button-primary pt-confirm", "Confirm practice order");
    confirm.type = "button";
    confirm.disabled = busy;
    confirm.addEventListener("click", function () { confirmOrder(why.value.trim(), risks.value.trim()); });
    var cancel = el("button", "button-secondary", "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", function () { draft = null; setMessage("Order not placed.", false); render(); });
    actions.appendChild(confirm);
    actions.appendChild(cancel);
    box.appendChild(actions);
    return box;
  }

  function holdings() {
    var card = el("section", "card pt-holdings");
    card.appendChild(el("h3", null, "Simulated holdings"));
    var positions = view.portfolio.positions;
    if (!positions.length) {
      card.appendChild(el("p", "muted", "No holdings yet."));
      return card;
    }
    var list = el("ul", "pt-list");
    positions.forEach(function (p) {
      var li = el("li", "pt-item");
      li.appendChild(el("p", "pt-item-title", p.symbol + " · " + p.shares + " shares"));
      li.appendChild(el("p", null, "Average cost " + money(p.average_cost_cents) + " · simulated close "
        + money(p.close_cents) + " · value " + money(p.market_value_cents)));
      li.appendChild(el("p", plClass(p.unrealized_pl_cents), "Unrealized " + signed(p.unrealized_pl_cents)));
      list.appendChild(li);
    });
    card.appendChild(list);
    return card;
  }

  function pendingOrders() {
    var card = el("section", "card pt-pending");
    card.appendChild(el("h3", null, "Pending practice orders"));
    var pending = view.orders.filter(function (o) { return o.status === "pending"; });
    if (!pending.length) {
      card.appendChild(el("p", "muted", "None. Orders you confirm wait here until the next simulated open."));
      return card;
    }
    var list = el("ul", "pt-list");
    pending.forEach(function (o) {
      var li = el("li", "pt-item");
      li.appendChild(el("p", "pt-item-title", o.side.toUpperCase() + " " + o.shares + " " + o.symbol));
      var b = el("button", "button-secondary", "Cancel order");
      b.type = "button";
      b.disabled = busy;
      b.addEventListener("click", function () { cancelOrder(o.id); });
      li.appendChild(b);
      list.appendChild(li);
    });
    card.appendChild(list);
    return card;
  }

  function history() {
    var card = el("section", "card pt-history");
    card.appendChild(el("h3", null, "Practice history"));
    var journal = readJournal();
    var fills = {};
    view.portfolio.transactions.forEach(function (t) { fills[t.order_id] = t; });
    var done = view.orders.filter(function (o) { return o.status !== "pending"; }).reverse();
    if (!done.length) {
      card.appendChild(el("p", "muted", "No filled, rejected or cancelled orders yet."));
      return card;
    }
    var list = el("ul", "pt-list");
    done.forEach(function (o) {
      var li = el("li", "pt-item pt-" + o.status);
      var t = fills[o.id];
      li.appendChild(el("p", "pt-item-title", o.side.toUpperCase() + " " + o.shares + " " + o.symbol + " · " + o.status));
      if (t) {
        li.appendChild(el("p", null, "Filled " + t.date + " at " + money(t.price_cents) + " (simulated open) · "
          + money(t.amount_cents) + (t.realized_pl_cents !== null ? " · realized " + signed(t.realized_pl_cents) : "")));
      }
      if (o.reason) li.appendChild(el("p", "pt-small", o.reason));
      var note = journal[o.id];
      if (note) {
        if (note.why) li.appendChild(el("p", "pt-note", "Why: " + note.why));
        if (note.risks) li.appendChild(el("p", "pt-note", "What could go wrong: " + note.risks));
      }
      list.appendChild(li);
    });
    card.appendChild(list);
    return card;
  }

  function learnMore() {
    var card = el("section", "card pt-learn");
    card.appendChild(el("h3", null, "Learn more"));
    var links = el("div", "pt-links");
    var cash = el("button", "button-secondary", "Accounts 101: Cash brokerage");
    cash.type = "button";
    cash.addEventListener("click", function () { if (window.Accounts) window.Accounts.open("Cash brokerage"); });
    links.appendChild(cash);
    [["Paying for trades on time", "brokerage-agreement", "ba-settlement"],
     ["Why this practice has no margin", "margin-agreement", "ma-lose-more"]].forEach(function (g) {
      var b = el("button", "button-secondary", g[0]);
      b.type = "button";
      b.addEventListener("click", function () {
        var tab = document.querySelector('[data-tab="sign"]');
        if (tab) tab.click();
        if (window.Sign && window.Sign.openAt) window.Sign.openAt(g[1], g[2]);
      });
      links.appendChild(b);
    });
    card.appendChild(links);
    card.appendChild(el("p", "pt-small", "Your practice session and journal are kept in this browser's storage. "
      + "Clearing site data deletes them, and anyone using the same browser profile can see them."));
    return card;
  }

  function render() {
    if (!root || !view) return;
    root.textContent = "";
    root.appendChild(banner());
    var title = el("h2", "pt-title", "Practice Trading");
    title.id = "paper-title";
    root.appendChild(title);
    if (message.text) {
      var m = el("p", message.error ? "pt-message error-text" : "pt-message");
      m.setAttribute("role", message.error ? "alert" : "status");
      m.textContent = message.text;
      root.appendChild(m);
    }
    root.appendChild(summaryCard());
    var layout = el("div", "pt-layout");
    var left = el("div", "pt-col");
    left.appendChild(ticket());
    left.appendChild(learnMore());
    var right = el("div", "pt-col");
    right.appendChild(holdings());
    right.appendChild(pendingOrders());
    right.appendChild(history());
    layout.appendChild(left);
    layout.appendChild(right);
    root.appendChild(layout);
  }

  function renderStart() {
    root.textContent = "";
    root.appendChild(banner());
    var box = el("div", "card pt-start");
    var title = el("h2", null, "Practice Trading");
    title.id = "paper-title";
    box.appendChild(title);
    box.appendChild(el("p", null, "Practice placing buy and sell orders with $10,000.00 of fictional cash in a "
      + "synthetic market. Step through simulated days and see how your choices play out, without risking real money."));
    var pick = el("label", "field", "Practice market ");
    var select = el("select");
    select.id = "pt-scenario";
    select.addEventListener("change", function () { scenarioId = select.value; });
    pick.appendChild(select);
    pick.hidden = true;  // shown once the list arrives; without it the default market is used
    box.appendChild(pick);
    window.Api.getPaperScenarios().then(function (env) {
      if (!env.ok) return;
      env.data.scenarios.forEach(function (s) {
        var o = el("option", null, s.label + " · " + s.days + " simulated days");
        o.value = s.id;
        select.appendChild(o);
      });
      select.value = scenarioId;
      pick.hidden = false;
    });
    var go = el("button", "button-primary", "Start a practice session");
    go.type = "button";
    go.addEventListener("click", startNew);
    box.appendChild(go);
    root.appendChild(box);
  }

  function show() {
    if (!root || started) return;
    started = true;
    var saved = readSession();
    if (saved === null) {
      renderStart();
    } else if (saved.damaged) {
      showDamaged("The saved session in this browser could not be read.");
    } else {
      root.textContent = "";
      root.appendChild(el("p", "muted", "Loading your practice session…"));
      call("view", { state: saved }, accept);
    }
  }

  window.Paper = {
    init: function () { root = document.getElementById("paper-root"); },
    show: show,
  };
})();
