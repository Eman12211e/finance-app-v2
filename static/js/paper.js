// Practice Trading tab in #paper-root: a simulated, synthetic-price trading practice built on /api/paper.
// The signed session lives in localStorage; journal notes live in localStorage too and are never sent to the server.
// Nothing here is a real price, order, account or recommendation.
// The workspace is built once per loaded session; each action then redraws only the regions it changed.
(function () {
  "use strict";

  var SESSION_KEY = "paper-session-v1";
  var JOURNAL_KEY = "paper-journal-v1";
  var INDICATORS_KEY = "paper-indicators-v1";  // chart overlays chosen in this browser; never part of the session
  var DRAWINGS_KEY = "paper-drawings-v1";  // your chart drawings, per market and ticker; never sent anywhere
  var MAX_DRAWINGS = 20;  // per ticker
  var OVERLAYS = [["sma", 20], ["sma", 50], ["ema", 12], ["ema", 26]];  // the approved presets drawn on the price
  var MAX_OVERLAYS = 2;
  var PANES = [["rsi", 14], ["macd", [12, 26, 9]]];  // the approved presets drawn in panes below the price
  var MAX_PANES = 2;
  var WEEK_LABELS = { partial: "Partial Week", final_short: "Final Short Week" };
  var SVG_NS = "http://www.w3.org/2000/svg";
  var MAX_SHARES = 100000;  // the engine's limit per order
  var PHONE = window.matchMedia("(max-width: 720px)");
  var root = null;
  var view = null;       // last verified view from the server
  var market = null;     // bars up to the current day, for the watchlist; the server never sends later bars
  var busy = false;      // one request at a time: double clicks and overlapping replies cannot race
  var draft = null;      // the previewed order awaiting Confirm or Back, with its fixed order id
  var started = false;
  var scenarioId = "synthetic-b";  // market for a new session; the start screen can change it, Reset keeps the current one
  var regions = null;    // live containers of the workspace, or null on the start and damaged screens
  var ui = freshUi();

  function freshUi() {
    var saved = readIndicators();
    return { symbol: null, side: "buy", shares: "1", mode: "edit", queuedId: null, queuedText: "", problem: "",
             historyOpen: true, historyFilter: "", watchOpen: !PHONE.matches, sheetOpen: false, timeframe: "daily",
             overlays: saved.overlays, panes: saved.panes, indMenuOpen: false, learnOpen: {}, whatOpen: null,
             drawMode: null, drawStart: null };
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function button(cls, text, onClick) {
    var b = el("button", cls, text);
    b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
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

  // gain or loss: sign, arrow (CSS) and colour together, never colour alone
  function pl(value, text) {
    return el("span", value > 0 ? "pt-up" : value < 0 ? "pt-down" : null, text === undefined ? signed(value) : text);
  }

  function sim(text) {
    return el("span", "pt-sim", text || "Simulated");
  }

  function niceDate(iso) {
    return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US",
      { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }

  function info(symbol) {
    return view.scenario.symbols[symbol] || {};
  }

  function closeOf(symbol) {
    return view.quotes[symbol].close_cents;
  }

  function describe(o) {
    return (o.side === "buy" ? "Buy " : "Sell ") + o.shares + " " + o.symbol;
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
      window.localStorage.removeItem(INDICATORS_KEY);  // a new session starts with every indicator off
      window.localStorage.removeItem(DRAWINGS_KEY);  // and with no drawings
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
        ui.mode = "edit";
        call("view", { state: stored }, load);
        return;
      }
    }
    setBusy(true);
    window.Api.paperPost(path, body).then(function (env) {
      setBusy(false);
      if (env.ok) {
        onOk(env.data);
      } else if (env.error.code === "INVALID_STATE") {
        showDamaged(env.error.message);
      } else {
        setMessage(env.error.message, true);
      }
    });
  }

  // A disabled button drops focus to the page, so the focused control is remembered while busy and refocused after.
  var focusKey = null;

  function setBusy(on) {
    busy = on;
    if (!root) return;
    var active = document.activeElement;
    if (on && root.contains(active) && active.dataset.key) focusKey = active.dataset.key;
    root.setAttribute("aria-busy", on ? "true" : "false");
    root.querySelectorAll("[data-busy]").forEach(function (b) {
      b.disabled = busy || (b.dataset.busy === "open" && !!view && view.day.ended);
    });
    if (!on && focusKey && (!document.activeElement || document.activeElement === document.body)) {
      var again = root.querySelector('[data-key="' + focusKey + '"]');
      if (again && !again.disabled) again.focus();
    }
  }

  function accept(data) {
    view = data;
    writeSession(data.state);
  }

  function load(data) {
    accept(data);
    if (!ui.symbol || !view.quotes[ui.symbol]) ui.symbol = Object.keys(view.quotes)[0];
    buildWorkspace();
    loadMarket();
  }

  function loadMarket() {
    call("market", { state: view.state }, function (data) {
      market = data;
      refresh(["watch"]);
      fillTrendDates();  // the keyboard trend-line dates follow the new day
    });
  }

  // ---- actions ----

  function startNew() {
    call("new", { scenario: view ? view.scenario.id : scenarioId }, function (data) {
      clearAll();
      draft = null;
      market = null;
      ui = freshUi();
      setMessage("A new practice session started with $10,000.00 of fictional cash.", false);
      load(data);
    });
  }

  // after the owner confirms: drop this session and its journal, then pick a market on the start screen
  function goToStart() {
    if (busy) return;
    clearAll();
    closeSheet(true);
    view = null;
    draft = null;
    market = null;
    ui = freshUi();
    message = { text: "", error: false };
    renderStart();
    document.getElementById("paper-title").focus();
  }

  function previewOrder() {
    var typed = regions.form.input.value.trim().toUpperCase();
    if (typed !== ui.symbol) {
      if (!view.quotes[typed]) {
        ui.problem = "Pick a ticker from the list.";
        updateTicketFigures();
        regions.form.input.focus();
        return;
      }
      selectSymbol(typed);
    }
    var shares = Number(ui.shares);
    var order = { symbol: ui.symbol, side: ui.side, shares: Number.isInteger(shares) ? shares : ui.shares };
    call("preview", { state: view.state, order: order }, function (data) {
      draft = data.ok ? { id: newOrderId(), order: order, preview: data } : null;
      ui.problem = data.ok ? "" : data.problems.map(function (p) { return p.message; }).join(" ");
      if (data.ok) {
        ui.mode = "review";
        renderTicket("pt-ticket-title");  // the preview replaces the ticket body in place
      } else {
        updateTicketFigures();
        regions.form.shares.focus();
      }
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
      ui.mode = "queued";
      ui.queuedId = d.id;
      ui.queuedText = data.duplicate ? "That order was already queued, so it was not added twice."
        : describe(order) + " will fill at the next simulated open. Press Next day to see it fill.";
      renderTicket("pt-ticket-title");
      refresh(["pending"]);
    });
  }

  function cancelOrder(orderId) {
    call("cancel", { state: view.state, order_id: orderId }, function (data) {
      accept(data);
      setMessage("Order cancelled.", false);
      if (ui.queuedId === orderId && ui.mode === "queued") {
        ui.mode = "edit";
        renderTicket("pt-ticket-title");
      }
      refresh(["pending", "history", "ticket"]);
    });
  }

  function advance(days) {
    var remaining = days;
    var waiting = view.orders.filter(function (o) { return o.status === "pending"; }).map(function (o) { return o.id; });
    function next() {
      if (remaining <= 0 || !view || view.day.ended) {
        finish();
        return;
      }
      remaining -= 1;
      call("advance", { state: view.state, expected_day: view.day.index }, function (data) {
        accept(data);
        setMessage("", false);
        if (ui.mode !== "edit") {
          draft = null;  // a preview was priced at a close that is no longer today's
          ui.mode = "edit";
          renderTicket();
        }
        refresh(["strip", "positions", "pending", "history", "ticket"]);
        setTimeout(next, 0);
      });
    }
    function finish() {
      var fills = {};
      view.portfolio.transactions.forEach(function (t) { fills[t.order_id] = t; });
      var filled = {};
      view.orders.forEach(function (o) {
        if (waiting.indexOf(o.id) === -1 || o.status === "pending") return;
        var t = fills[o.id];
        if (t) {
          filled[o.symbol] = true;
          toast((o.side === "buy" ? "Bought " : "Sold ") + o.shares + " " + o.symbol + " at " + money(t.price_cents),
            "Simulated fill at the " + niceDate(t.date) + " open. " + (o.side === "buy" ? "Cost " : "Proceeds ")
            + money(t.amount_cents) + (t.realized_pl_cents !== null ? ". Realized " + signed(t.realized_pl_cents) : "") + ".");
        } else {
          toast(describe(o) + " was " + o.status, o.reason || "", true);
        }
      });
      flashRows(Object.keys(filled));
      refresh(["chart"]);  // a new day: new bars and indicator values for the chart
      loadMarket();
    }
    next();
  }

  function selectSymbol(symbol) {
    ui.symbol = symbol;
    ui.problem = "";
    if (ui.mode === "edit" && regions.form) {
      regions.form.input.value = symbol;
      updateTicketFigures();
    } else {
      draft = null;
      ui.mode = "edit";
      renderTicket();
    }
    root.querySelectorAll(".pt-watch-item").forEach(function (b) {
      b.setAttribute("aria-current", b.dataset.symbol === symbol ? "true" : "false");
    });
    refresh(["chart"]);
  }

  // from the watchlist or the positions table: on phones this opens the trade sheet
  function pickToTrade(symbol) {
    selectSymbol(symbol);
    if (PHONE.matches) openSheet("pt-shares");
  }

  // ---- messages, toasts and row feedback ----

  var message = { text: "", error: false };

  function setMessage(text, error) {
    message = { text: text, error: error };
    if (regions) showMessage();
  }

  function showMessage() {
    var box = regions.message;
    box.textContent = "";
    if (!message.text) return;
    var m = el("p", message.error ? "pt-message error-text" : "pt-message", message.text);
    if (message.error) m.setAttribute("role", "alert");
    box.appendChild(m);
  }

  function toast(title, detail, bad) {
    var t = el("div", "pt-toast" + (bad ? " pt-toast-bad" : ""));
    var p = el("p");
    p.appendChild(el("strong", null, title));
    if (detail) p.appendChild(el("span", "pt-small", detail));
    t.appendChild(p);
    var close = button("pt-toast-close", "×", function () { t.remove(); });
    close.setAttribute("aria-label", "Dismiss notification");
    t.appendChild(close);
    regions.toasts.appendChild(t);
    setTimeout(function () { t.remove(); }, 5000);
  }

  function flashRows(symbols) {
    symbols.forEach(function (s) {
      var row = regions.positions.querySelector('tr[data-symbol="' + s + '"]');
      if (!row) return;
      row.classList.add("pt-flash");
      setTimeout(function () { row.classList.remove("pt-flash"); }, 2000);
    });
  }

  // ---- the workspace ----

  function banner() {
    var b = el("div", "pt-banner");
    b.setAttribute("role", "note");
    b.appendChild(el("p", "pt-banner-title", "SIMULATED PRACTICE: not real money, prices or trades"));
    b.appendChild(el("p", null, "All prices are synthetic, all balances are fictional, and no real securities are "
      + "bought or sold. This basic simulator leaves out fees, the bid-ask spread, slippage and market impact."));
    return b;
  }

  function region(tag, cls, labelId) {
    var node = el(tag, cls);
    if (labelId) node.setAttribute("aria-labelledby", labelId);
    return node;
  }

  function buildWorkspace() {
    closeSheet(true);
    disposeChart();
    root.textContent = "";
    root.appendChild(banner());
    var title = el("h2", "visually-hidden", "Practice Trading");
    title.id = "paper-title";
    root.appendChild(title);
    var notice = el("p", "pt-notice");
    notice.appendChild(sim());
    notice.appendChild(el("span", null, view.scenario.label + ": " + view.scenario.notice));
    root.appendChild(notice);
    regions = {
      message: el("div", "pt-message-box"),
      watch: region("aside", "card pt-watch"),
      strip: region("section", "card pt-strip", "pt-strip-title"),
      chart: region("section", "pt-chart", "pt-chart-title"),
      positions: region("section", "card pt-positions", "pt-positions-title"),
      pending: region("section", "card pt-pending", "pt-pending-title"),
      history: region("div", "pt-history-box"),
      ticket: region("aside", "card pt-ticket", "pt-ticket-title"),
      toasts: el("div", "pt-toasts"),
      form: null,
    };
    regions.message.setAttribute("aria-live", "polite");
    regions.watch.setAttribute("aria-label", "Practice tickers");
    regions.ticket.id = "pt-ticket";
    regions.toasts.setAttribute("role", "status");
    regions.toasts.setAttribute("aria-atomic", "false");  // announce each new fill, not every toast again
    regions.ticket.addEventListener("keydown", sheetKeys);
    root.appendChild(regions.message);

    var layout = el("div", "pt-layout");
    var centre = el("div", "pt-centre");
    [regions.strip, regions.chart, regions.positions, regions.pending, regions.history, learnMore()].forEach(function (n) {
      centre.appendChild(n);
    });
    layout.appendChild(regions.watch);
    layout.appendChild(centre);
    layout.appendChild(regions.ticket);
    root.appendChild(layout);

    regions.tradeBar = button("button-primary pt-trade-bar", "Trade", function () { openSheet(); });
    regions.tradeBar.setAttribute("aria-haspopup", "dialog");
    regions.tradeBar.setAttribute("aria-controls", "pt-ticket");
    regions.tradeBar.setAttribute("aria-expanded", "false");
    regions.scrim = el("div", "pt-scrim");
    regions.scrim.hidden = true;
    regions.scrim.addEventListener("click", function () { closeSheet(); });
    root.appendChild(regions.tradeBar);
    root.appendChild(regions.scrim);
    root.appendChild(regions.toasts);

    showMessage();
    renderTicket();
    refresh(["watch", "strip", "chart", "positions", "pending", "history"]);
    dock();
  }

  var RENDER = {};

  // Redraws the named regions. Focus inside a redrawn region returns to the same control (data-key), or to the
  // region's heading if that control is gone, so keyboard users never lose their place.
  function refresh(names, focusId) {
    if (!regions) return;
    names.forEach(function (name) {
      if (name === "ticket") {
        if (ui.mode === "edit" && regions.form) updateTicketFigures();
        else renderTicket();
        return;
      }
      var box = regions[name];
      var active = document.activeElement;
      var key = box.contains(active) ? active.getAttribute("data-key") : null;
      var hadFocus = box.contains(active) && active !== document.body;
      box.textContent = "";
      RENDER[name](box);
      if (hadFocus) {
        var again = (key && box.querySelector('[data-key="' + key + '"]')) || box.querySelector('[tabindex="-1"]');
        if (again) again.focus();
      }
    });
    setBusy(busy);
    if (focusId) {
      var f = document.getElementById(focusId);
      if (f) f.focus();
    }
  }

  // ---- portfolio header strip: figures, day counter, progress and day controls ----

  function figure(label, value, hero) {
    var box = el("div", "pt-figure" + (hero ? " pt-hero" : ""));
    var l = el("span", "pt-figure-label", label);
    if (hero) {
      l.appendChild(document.createTextNode(" "));
      l.appendChild(sim());
    }
    box.appendChild(l);
    var v = el("span", "pt-figure-value");
    if (typeof value === "string") v.textContent = value;
    else value.forEach(function (n, k) {
      if (k) v.appendChild(document.createTextNode(" / "));
      v.appendChild(n);
    });
    box.appendChild(v);
    return box;
  }

  RENDER.strip = function (box) {
    var p = view.portfolio, day = view.day, total = view.scenario.days;
    var h = el("h3", "visually-hidden", "Your simulated account");
    h.id = "pt-strip-title";
    h.tabIndex = -1;
    box.appendChild(h);
    var top = el("div", "pt-strip-top");
    top.appendChild(figure("Portfolio value", money(p.portfolio_value_cents), true));
    top.appendChild(figure("Fictional cash", money(p.cash_cents)));
    top.appendChild(figure("Total since $10,000 start", [pl(p.total_pl_cents)]));
    top.appendChild(figure("Realized / unrealized", [pl(p.realized_pl_cents), pl(p.unrealized_pl_cents)]));

    var dayBox = el("div", "pt-day");
    var line = el("p", "pt-day-line");
    line.appendChild(el("strong", null, "Day " + (day.index + 1) + " of " + total));
    line.appendChild(el("span", "muted", " " + niceDate(day.date)
      + (day.ended ? ", scenario ended" : day.is_last ? ", last day" : "")));
    dayBox.appendChild(line);
    var bar = el("div", "pt-progress");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-label", "Scenario progress");
    bar.setAttribute("aria-valuemin", "1");
    bar.setAttribute("aria-valuemax", String(total));
    bar.setAttribute("aria-valuenow", String(day.index + 1));
    bar.setAttribute("aria-valuetext", "Day " + (day.index + 1) + " of " + total);
    var fillBar = el("span");
    fillBar.style.width = ((day.index + 1) / total * 100).toFixed(1) + "%";
    bar.appendChild(fillBar);
    dayBox.appendChild(bar);

    var controls = el("div", "pt-day-controls");
    if (day.ended) {
      controls.appendChild(el("p", "pt-small", "This practice scenario has ended."));
    } else {
      [["Next day", 1], ["Next 5 days", 5]].forEach(function (c) {
        var b = button("button-secondary", c[0], function () { advance(c[1]); });
        b.dataset.busy = "open";
        b.dataset.key = "next-" + c[1];
        controls.appendChild(b);
      });
    }
    var more = button("button-secondary pt-more", day.ended ? "Start again" : "More", null);
    more.dataset.key = "more";
    more.setAttribute("aria-expanded", "false");
    more.setAttribute("aria-controls", "pt-session-menu");
    if (!day.ended) more.setAttribute("aria-label", "More session actions");
    var menu = el("div", "pt-session-menu");
    menu.id = "pt-session-menu";
    menu.hidden = true;
    var reset = button("button-secondary pt-reset", "Reset simulation", function () { renderResetConfirm(menu, false); });
    reset.dataset.busy = "";
    reset.dataset.key = "reset";
    menu.appendChild(reset);
    var change = button("button-secondary pt-change", "Change practice market", function () { renderResetConfirm(menu, true); });
    change.dataset.busy = "";
    change.dataset.key = "change";
    menu.appendChild(change);
    more.addEventListener("click", function () {
      menu.hidden = !menu.hidden;
      more.setAttribute("aria-expanded", menu.hidden ? "false" : "true");
      if (!menu.hidden) reset.focus();
    });
    menu.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      menu.hidden = true;
      more.setAttribute("aria-expanded", "false");
      more.focus();
    });
    controls.appendChild(more);
    dayBox.appendChild(controls);
    dayBox.appendChild(menu);
    top.appendChild(dayBox);
    box.appendChild(top);
  };

  function renderResetConfirm(menu, toStart) {
    var old = menu.querySelector(".pt-confirm-reset");
    if (old) old.remove();
    var box = el("div", "pt-confirm-reset");
    box.setAttribute("role", "alertdialog");
    box.setAttribute("aria-label", toStart ? "Change the practice market" : "Reset the simulation");
    box.appendChild(el("p", null, toStart
      ? "Change the practice market? This deletes your practice session and journal notes from this browser and goes "
        + "back to the start screen, where you can pick a market. It cannot be undone."
      : "Reset the simulation? This deletes your practice session and journal notes from "
        + "this browser and starts again with $10,000.00 of fictional cash. It cannot be undone."));
    var yes = toStart ? button("button-primary", "Yes, change market", goToStart) : button("button-primary", "Yes, reset", startNew);
    yes.dataset.busy = "";
    var no = button("button-secondary", "Keep my session", function () {
      box.remove();
      menu.querySelector(toStart ? ".pt-change" : ".pt-reset").focus();
    });
    box.appendChild(yes);
    box.appendChild(no);
    menu.appendChild(box);
    no.focus();
  }

  // ---- price chart: TradingView Lightweight Charts (vendored, static/vendor). Bars never pass today. ----

  var chart = null;  // the live chart; rebuilt with its region, so zoom resets on a new ticker, day or timeframe

  function disposeChart() {
    if (chart) chart.remove();
    chart = null;
    drawLayer = null;
  }

  // ---- drawings (P4 step 7): horizontal and trend lines, kept in this browser as dates and dollar prices ----
  // They are only ever drawn: never sent to the server, never part of prices, orders, fills or the portfolio.

  var drawLayer = null;  // the live chart's drawing handles: adding or removing a drawing never rebuilds the chart

  function readAllDrawings() {
    try {
      var all = JSON.parse(window.localStorage.getItem(DRAWINGS_KEY) || "{}");
      return all && typeof all === "object" && !Array.isArray(all) ? all : {};
    } catch (e) {
      return {};
    }
  }

  function validDrawing(d) {  // saved drawings are re-checked: only well-formed lines are drawn
    var day = /^\d{4}-\d{2}-\d{2}$/;
    var price = function (v) { return typeof v === "number" && isFinite(v) && v > 0 && v < 10000000; };
    if (!d || typeof d.id !== "string") return false;
    if (d.kind === "h") return price(d.price);
    return d.kind === "t" && !!d.a && !!d.b && day.test(d.a.date) && day.test(d.b.date) && d.a.date < d.b.date
      && price(d.a.price) && price(d.b.price);
  }

  function drawingsKey() {
    return view.scenario.id + "|" + ui.symbol;
  }

  function drawingsFor() {
    var list = readAllDrawings()[drawingsKey()];
    return (Array.isArray(list) ? list : []).filter(validDrawing).slice(0, MAX_DRAWINGS);
  }

  function saveDrawings(list) {
    var all = readAllDrawings();
    all[drawingsKey()] = list;
    try { window.localStorage.setItem(DRAWINGS_KEY, JSON.stringify(all)); } catch (e) { /* storage unavailable */ }
    syncDrawings();
  }

  function dollars(price) {
    return money(Math.round(price * 100));
  }

  function describeDrawing(d, dayText) {
    var day = dayText || niceDate;
    return d.kind === "h" ? "Horizontal line at " + dollars(d.price)
      : "Trend line from " + day(d.a.date) + " (" + dollars(d.a.price) + ") to " + day(d.b.date) + " (" + dollars(d.b.price) + ")";
  }

  function drawStatus(text, error) {
    var status = document.getElementById("pt-draw-status");
    if (!status) return;
    status.textContent = text;
    status.classList.toggle("error-text", !!error);
  }

  function addDrawing(d) {
    var list = drawingsFor();
    if (list.length >= MAX_DRAWINGS) {
      drawStatus("You have " + MAX_DRAWINGS + " drawings on " + ui.symbol + ". Remove one to add another.", true);
      return false;
    }
    d.id = "d" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    list.push(d);
    saveDrawings(list);
    drawStatus("Added: " + describeDrawing(d) + ".", false);
    return true;
  }

  function removeDrawing(id) {
    var list = drawingsFor(), gone = list.filter(function (d) { return d.id === id; })[0];
    saveDrawings(list.filter(function (d) { return d.id !== id; }));
    if (gone) drawStatus("Removed: " + describeDrawing(gone) + ".", false);
    var next = document.querySelector("#pt-draw-list button") || document.querySelector('[data-key="draw-add-h"]');
    if (next) next.focus();  // the removed row's button is gone: keep the keyboard in the panel
  }

  function clearDrawings() {
    if (!drawingsFor().length) return;
    saveDrawings([]);
    drawStatus("Cleared every drawing on " + ui.symbol + ".", false);
  }

  // Clear drawings removes every line on this ticker at once, so it asks first (like Reset); Remove does not
  function confirmClear() {
    var list = drawingsFor(), panel = document.getElementById("pt-drawings");
    if (!list.length || !panel) return;
    var old = panel.querySelector(".pt-confirm-clear");
    if (old) old.remove();
    var box = el("div", "pt-confirm-reset pt-confirm-clear");
    box.setAttribute("role", "alertdialog");
    box.setAttribute("aria-label", "Clear drawings");
    box.appendChild(el("p", null, "Clear all " + list.length + " drawing" + (list.length === 1 ? "" : "s") + " on "
      + ui.symbol + "? This cannot be undone."));
    var yes = button("button-primary", "Yes, clear drawings", function () {
      box.remove();
      clearDrawings();
      var next = document.querySelector('[data-key="draw-add-h"]');
      if (next) next.focus();
    });
    yes.dataset.key = "draw-clear-yes";
    var no = button("button-secondary", "Keep drawings", function () {
      box.remove();
      var back = document.querySelector('[data-key="draw-clear-panel"]');
      if (back) back.focus();
    });
    no.dataset.key = "draw-clear-no";
    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        no.click();
      }
    });
    box.appendChild(yes);
    box.appendChild(no);
    panel.appendChild(box);
    box.scrollIntoView({ block: "nearest" });
    no.focus();
  }

  function modeText() {
    if (ui.drawMode === "h") return "Horizontal line: click or tap the chart at the price you want. Press Esc to cancel.";
    if (ui.drawMode === "t") {
      return "Trend line: click or tap the " + (ui.drawStart ? "second" : "first") + " point on the chart. Press Esc to cancel.";
    }
    return "";
  }

  function setDrawMode(mode) {
    ui.drawMode = mode;
    ui.drawStart = null;
    if (!root) return;
    root.querySelectorAll("[data-draw]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.draw === mode ? "true" : "false");
    });
    showBanner();
    if (drawLayer) drawLayer.pending(null);
  }

  function showBanner(note) {
    var banner = document.getElementById("pt-draw-banner");
    if (!banner) return;
    banner.hidden = !ui.drawMode;
    banner.querySelector("span").textContent = note || modeText();
  }

  // the chart and the panel follow the stored drawings
  function syncDrawings() {
    var list = drawingsFor();
    if (drawLayer) drawLayer.sync(list);
    var items = document.getElementById("pt-draw-list");
    if (!items) return;
    items.textContent = "";
    list.forEach(function (d) {
      var li = el("li");
      var swatch = el("span", "pt-swatch pt-swatch-draw");
      swatch.setAttribute("aria-hidden", "true");
      li.appendChild(swatch);
      li.appendChild(el("span", null, describeDrawing(d)));
      var remove = button("button-secondary", "Remove", function () { removeDrawing(d.id); });
      remove.setAttribute("aria-label", "Remove " + describeDrawing(d).replace(/^./, function (c) { return c.toLowerCase(); }));
      li.appendChild(remove);
      items.appendChild(li);
    });
    var empty = document.getElementById("pt-draw-empty");
    if (empty) empty.hidden = list.length > 0;
    var asking = document.querySelector(".pt-confirm-clear");
    if (asking && !list.length) asking.remove();  // nothing left to clear
    root.querySelectorAll("[data-clear]").forEach(function (b) { b.disabled = !list.length; });
  }

  // the trend-line picker lists the daily closes up to today (the watchlist's bars; never later)
  function fillTrendDates() {
    var from = document.getElementById("pt-tline-from"), to = document.getElementById("pt-tline-to");
    if (!from || !to) return;
    var ready = marketIsCurrent() && market.bars[ui.symbol];
    [from, to].forEach(function (sel, k) {
      var keep = sel.value;
      sel.textContent = "";
      if (!ready) {
        sel.appendChild(el("option", null, "Loading dates…"));
        sel.disabled = true;
        return;
      }
      sel.disabled = false;
      market.dates.forEach(function (d, j) {
        var o = el("option", null, niceDate(d) + " close (" + money(market.bars[ui.symbol][j].c) + ")");
        o.value = d;
        sel.appendChild(o);
      });
      var n = market.dates.length;
      sel.value = keep && market.dates.indexOf(keep) !== -1 ? keep : market.dates[k === 0 ? Math.max(0, n - 21) : n - 1];
    });
  }

  function addTypedLine() {
    var input = document.getElementById("pt-hline-price"), raw = input.value.replace(/[$,\s]/g, "");
    var ok = /^\d+(\.\d{1,2})?$/.test(raw) && Number(raw) > 0 && Number(raw) <= 100000;
    input.setAttribute("aria-invalid", ok ? "false" : "true");
    if (!ok) {
      drawStatus("Enter a price in dollars from 0.01 to 100,000, like 210.00.", true);
      input.focus();
      return;
    }
    if (addDrawing({ kind: "h", price: Number(raw) })) input.value = "";
  }

  function addPickedTrend() {
    var from = document.getElementById("pt-tline-from"), to = document.getElementById("pt-tline-to");
    if (from.disabled) return;
    var a = market.dates.indexOf(from.value), b = market.dates.indexOf(to.value);
    to.setAttribute("aria-invalid", b > a ? "false" : "true");
    if (!(b > a)) {
      drawStatus("Choose an end date after the start date.", true);
      to.focus();
      return;
    }
    var bars = market.bars[ui.symbol];
    addDrawing({ kind: "t", a: { date: from.value, price: bars[a].c / 100 }, b: { date: to.value, price: bars[b].c / 100 } });
  }

  function drawingsPanel() {
    var panel = el("section", "pt-drawings");
    panel.id = "pt-drawings";
    panel.setAttribute("aria-labelledby", "pt-drawings-title");
    var h = el("h4", null, "Your drawings ");
    h.id = "pt-drawings-title";
    h.appendChild(el("span", "pt-tiny muted", "(kept in this browser only; they never change prices, orders or your portfolio)"));
    panel.appendChild(h);
    var empty = el("p", "pt-small", "No drawings on " + ui.symbol + " yet. Use Horizontal line or Trend line above the "
      + "chart, or add one with the keyboard.");
    empty.id = "pt-draw-empty";
    panel.appendChild(empty);
    var list = el("ul", "pt-draw-list");
    list.id = "pt-draw-list";
    panel.appendChild(list);
    var status = el("p", "pt-tiny pt-draw-status");
    status.id = "pt-draw-status";
    status.setAttribute("aria-live", "polite");
    panel.appendChild(status);

    var form = el("fieldset", "pt-draw-form");
    form.appendChild(el("legend", null, "Add a line with the keyboard"));
    var row1 = el("div", "pt-draw-row");
    var priceLabel = el("label", null, "Horizontal line price ($)");
    var price = el("input");
    price.id = "pt-hline-price";
    price.type = "text";
    price.inputMode = "decimal";
    price.autocomplete = "off";
    price.placeholder = "210.00";
    price.setAttribute("aria-describedby", "pt-draw-status");
    price.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); addTypedLine(); } });
    priceLabel.appendChild(price);
    row1.appendChild(priceLabel);
    var addH = button("button-secondary", "Add horizontal line", addTypedLine);
    addH.dataset.key = "draw-add-h";
    row1.appendChild(addH);
    form.appendChild(row1);
    var row2 = el("div", "pt-draw-row");
    [["pt-tline-from", "Trend line from"], ["pt-tline-to", "to"]].forEach(function (f) {
      var label = el("label", null, f[1]);
      var sel = el("select");
      sel.id = f[0];
      sel.setAttribute("aria-describedby", "pt-draw-status");
      label.appendChild(sel);
      row2.appendChild(label);
    });
    var addT = button("button-secondary", "Add trend line", addPickedTrend);
    addT.dataset.key = "draw-add-t";
    row2.appendChild(addT);
    form.appendChild(row2);
    form.appendChild(el("p", "pt-tiny muted", "A keyboard trend line joins the two days' closing prices."));
    panel.appendChild(form);
    var clear = button("button-secondary pt-draw-clear", "Clear drawings", confirmClear);
    clear.dataset.key = "draw-clear-panel";
    clear.dataset.clear = "";
    panel.appendChild(clear);
    return panel;
  }

  // trend lines drawn on the price pane; dates and prices become pixels only while drawing, so zoom and scroll follow
  function trendLines(state) {
    var chartApi = null, series = null;
    var renderer = {
      draw: function (target) {
        if (!chartApi || !series) return;
        target.useMediaCoordinateSpace(function (scope) {
          var ctx = scope.context, ts = chartApi.timeScale();
          ctx.save();
          ctx.strokeStyle = state.ink;
          ctx.fillStyle = state.ink;
          ctx.lineWidth = 1.5;
          var dot = function (x, y) { ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 2 * Math.PI); ctx.fill(); };
          state.lines.concat(state.pending ? [state.pending] : []).forEach(function (l) {
            var x1 = ts.timeToCoordinate(l.t1), y1 = series.priceToCoordinate(l.p1);
            if (x1 === null || y1 === null) return;
            if (l.t2) {
              var x2 = ts.timeToCoordinate(l.t2), y2 = series.priceToCoordinate(l.p2);
              if (x2 === null || y2 === null) return;
              ctx.beginPath();
              ctx.moveTo(x1, y1);
              ctx.lineTo(x2, y2);
              ctx.stroke();
              dot(x2, y2);
            }
            dot(x1, y1);
          });
          ctx.restore();
        });
      },
    };
    return {
      attached: function (param) { chartApi = param.chart; series = param.series; state.redraw = param.requestUpdate; },
      detached: function () { chartApi = null; series = null; },
      paneViews: function () { return [{ renderer: function () { return renderer; } }]; },
    };
  }

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function withAlpha(color, alpha) {  // tokens are #rrggbb; the canvas needs a plain colour string
    return /^#[0-9a-f]{6}$/i.test(color) ? color + alpha : color;
  }

  // Chart data (bars and indicator values) come from the server (/api/analysis/indicators), which owns the indicator
  // maths and the completed-week rules; nothing is calculated here. One reply per market, ticker, day, timeframe and
  // overlay set, kept so a theme change redraws without asking again; a reply that arrives after any of them changed
  // is ignored.
  var chartData = null;

  function presetOf(o, presets) {  // the approved preset {type, period} matches, if any (MACD's period is a list)
    return presets.filter(function (p) {
      return o && p[0] === o.type && JSON.stringify(p[1]) === JSON.stringify(o.period);
    })[0];
  }

  function readIndicators() {  // saved choices are re-checked: approved presets only, each once, within the limits
    var out = { overlays: [], panes: [] };
    try {
      var saved = JSON.parse(window.localStorage.getItem(INDICATORS_KEY) || "[]");
      (Array.isArray(saved) ? saved : []).forEach(function (o) {
        [[OVERLAYS, out.overlays, MAX_OVERLAYS], [PANES, out.panes, MAX_PANES]].forEach(function (g) {
          var p = presetOf(o, g[0]);
          if (p && g[1].length < g[2] && !g[1].some(function (x) { return presetOf(x, [p]); })) {
            g[1].push({ type: p[0], period: p[1] });
          }
        });
      });
    } catch (e) { /* unreadable: every indicator starts off */ }
    return out;
  }

  function chosen() {
    return ui.overlays.concat(ui.panes);
  }

  function writeIndicators() {
    try { window.localStorage.setItem(INDICATORS_KEY, JSON.stringify(chosen())); } catch (e) { /* storage unavailable */ }
  }

  function indicatorName(o) {
    return o.type.toUpperCase() + " " + (Array.isArray(o.period) ? o.period.join("-") : o.period);
  }

  function chartKey() {
    return [view.scenario.id, ui.symbol, view.day.index, ui.timeframe, JSON.stringify(chosen())].join("|");
  }

  function loadChart(key) {
    if (chartData && chartData.key === key) return;
    chartData = { key: key };
    window.Api.postAnalysis({ state: view.state, symbol: ui.symbol, timeframe: ui.timeframe, indicators: chosen() })
      .then(function (env) {
        if (!regions || !view || chartKey() !== key) return;
        chartData = env.ok ? { key: key, data: env.data } : { key: key, error: env.error.message };
        refresh(["chart"]);
      });
  }

  var guideText = null;  // data/indicator_guide.json via /api/analysis/guide, loaded once

  function loadGuide() {
    if (guideText) return;
    guideText = { loading: true };
    window.Api.getAnalysisGuide().then(function (env) {
      guideText = env.ok ? env.data : null;  // on failure the cards still show their readings; Learn more waits
      if (env.ok && regions) refresh(["chart"]);
    });
  }

  function presetKey(type, period) {
    return type + "-" + [].concat(period).join("-");
  }

  // the full approved explanation for one preset: What it shows, How people read it, Watch out, and the footer
  function explanation(type, period, withFooter) {
    var entry = guideText && guideText.indicators && guideText.indicators[type];
    var box = el("div", "pt-explain");
    if (!entry) {
      box.appendChild(el("p", "pt-tiny muted", "The explanation is loading."));
      return box;
    }
    var n = Array.isArray(period) ? period.join("-") : String(period);
    box.appendChild(el("p", "pt-summary-tag", guideText.label));
    var dl = el("dl");
    [["What it shows", entry.what], ["How people read it", entry.how], ["Watch out", entry.watch]].forEach(function (row) {
      dl.appendChild(el("dt", null, row[0]));
      dl.appendChild(el("dd", null, row[1].split("{n}").join(n)));
    });
    box.appendChild(dl);
    if (withFooter) box.appendChild(el("p", "pt-edu-note", guideText.footer));
    return box;
  }

  function toggleIndicator(p, on) {
    var list = presetOf({ type: p[0], period: p[1] }, PANES) ? "panes" : "overlays";
    ui[list] = ui[list].filter(function (o) { return !presetOf(o, [p]); });
    if (on && ui[list].length < (list === "panes" ? MAX_PANES : MAX_OVERLAYS)) ui[list].push({ type: p[0], period: p[1] });
    writeIndicators();
    refresh(["chart"]);
  }

  function setMenu(open, focusButton) {
    ui.indMenuOpen = open;
    var menu = document.getElementById("pt-ind-menu"), btn = root.querySelector('[data-key="ind-button"]');
    if (!menu || !btn) return;
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (PHONE.matches && open) {
      menu.setAttribute("role", "dialog");
      menu.setAttribute("aria-modal", "true");
    } else {
      menu.removeAttribute("role");
      menu.removeAttribute("aria-modal");
    }
    if (open) menu.querySelector("input:not([disabled]), button").focus();
    else if (focusButton) btn.focus();
  }

  function indicatorTools() {
    var wrap = el("div", "pt-tools");
    var bar = el("div", "pt-toolbar");
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Analysis tools");
    var btn = button("pt-tool", "Indicators" + (chosen().length ? " (" + chosen().length + ")" : ""), function () {
      setMenu(!ui.indMenuOpen, true);
    });
    btn.dataset.key = "ind-button";
    btn.setAttribute("aria-controls", "pt-ind-menu");
    btn.setAttribute("aria-expanded", ui.indMenuOpen ? "true" : "false");
    bar.appendChild(btn);
    [["h", "Horizontal line"], ["t", "Trend line"]].forEach(function (m) {
      var b = button("pt-tool", m[1], function () { setDrawMode(ui.drawMode === m[0] ? null : m[0]); });
      b.dataset.draw = m[0];
      b.dataset.key = "draw-" + m[0];
      b.setAttribute("aria-pressed", ui.drawMode === m[0] ? "true" : "false");
      bar.appendChild(b);
    });
    var clear = button("pt-tool", "Clear drawings", confirmClear);
    clear.dataset.key = "draw-clear";
    clear.dataset.clear = "";
    bar.appendChild(clear);
    bar.appendChild(el("span", "pt-tool-note", ui.overlays.length + " of " + MAX_OVERLAYS + " lines on the price, "
      + ui.panes.length + " of " + MAX_PANES + " panes"));
    wrap.appendChild(bar);
    var banner = el("div", "pt-draw-banner");
    banner.id = "pt-draw-banner";
    banner.setAttribute("role", "status");
    banner.appendChild(el("span", null, modeText()));
    var cancel = button("button-secondary", "Cancel", function () { setDrawMode(null); });
    cancel.dataset.key = "draw-cancel";
    banner.appendChild(cancel);
    banner.hidden = !ui.drawMode;
    wrap.appendChild(banner);

    var menu = el("div", "pt-ind-menu");
    menu.id = "pt-ind-menu";
    menu.hidden = !ui.indMenuOpen;
    menu.setAttribute("aria-label", "Indicators");
    var full = ui.overlays.length >= MAX_OVERLAYS;
    [["On the price (" + MAX_OVERLAYS + " at most)", OVERLAYS, ui.overlays, MAX_OVERLAYS, true],
     ["Below the chart (" + MAX_PANES + " at most)", PANES, ui.panes, MAX_PANES, false]].forEach(function (g) {
      var group = el("fieldset", "pt-ind-group");
      group.appendChild(el("legend", null, g[0]));
      g[1].forEach(function (p) {
        var slot = g[2].findIndex(function (o) { return presetOf(o, [p]); });
        var item = el("div", "pt-ind-item");
        var row = el("label", "pt-ind-row");
        var box = el("input");
        box.type = "checkbox";
        box.checked = slot !== -1;
        box.disabled = g[2].length >= g[3] && slot === -1;
        box.dataset.key = "ind-" + p[0] + "-" + [].concat(p[1]).join("-");
        box.setAttribute("aria-describedby", "pt-ind-limit");
        box.addEventListener("change", function () { toggleIndicator(p, box.checked); });
        row.appendChild(box);
        if (g[4]) {  // price lines show their line style; panes are named on their own scale
          var swatch = el("span", "pt-swatch" + (slot === 1 ? " pt-swatch-b" : slot === 0 ? "" : " pt-swatch-off"));
          swatch.setAttribute("aria-hidden", "true");
          row.appendChild(swatch);
        }
        row.appendChild(document.createTextNode(indicatorName({ type: p[0], period: p[1] })
          + (g[4] && slot === 0 ? " (solid line)" : g[4] && slot === 1 ? " (dashed line)" : "")));
        item.appendChild(row);
        var key = presetKey(p[0], p[1]);
        var what = button("pt-what", "What is this?", null);
        what.dataset.key = "what-" + key;
        what.setAttribute("aria-label", "What is " + indicatorName({ type: p[0], period: p[1] }) + "?");
        what.setAttribute("aria-controls", "pt-what-" + key);
        what.setAttribute("aria-expanded", ui.whatOpen === key ? "true" : "false");
        var panel = explanation(p[0], p[1], true);
        panel.id = "pt-what-" + key;
        panel.classList.add("pt-what-panel");
        panel.hidden = ui.whatOpen !== key;
        what.addEventListener("click", function () {  // opens the explanation only; the indicator stays as it is
          ui.whatOpen = ui.whatOpen === key ? null : key;
          menu.querySelectorAll(".pt-what").forEach(function (b) {
            var mine = b === what && ui.whatOpen === key;
            b.setAttribute("aria-expanded", mine ? "true" : "false");
            document.getElementById(b.getAttribute("aria-controls")).hidden = !mine;
          });
        });
        item.appendChild(what);
        item.appendChild(panel);
        group.appendChild(item);
      });
      menu.appendChild(group);
    });
    var limit = el("p", "pt-tiny muted", full ? "Two lines are already on the price. Turn one off to add another."
      : "Up to two lines on the price and two panes below it. Periods are fixed presets.");
    limit.id = "pt-ind-limit";
    menu.appendChild(limit);
    menu.appendChild(el("p", "pt-tiny muted", "Indicator values describe past simulated prices only. They never change "
      + "your cash, orders or fills, and they are not a recommendation."));
    var done = button("button-secondary pt-ind-done", "Done", function () { setMenu(false, true); });
    done.dataset.key = "ind-done";
    menu.appendChild(done);
    menu.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setMenu(false, true);
      } else if (e.key === "Tab" && PHONE.matches) {  // the phone sheet keeps Tab inside it
        var items = [].filter.call(menu.querySelectorAll("input, button"), function (n) { return !n.disabled; });
        var first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
    wrap.appendChild(menu);
    var scrim = el("div", "pt-ind-scrim");
    scrim.addEventListener("click", function () { setMenu(false, true); });
    wrap.appendChild(scrim);
    return wrap;
  }

  function timeKey(t) {  // crosshair times come back as strings or {year, month, day}
    if (typeof t === "string" || !t) return t;
    return t.year + "-" + String(t.month).padStart(2, "0") + "-" + String(t.day).padStart(2, "0");
  }

  function lineValue(v, digits, prefix) {  // a value as shown, or "Not enough data" when there is none
    return v === null || v === undefined ? "Not enough data" : (prefix === undefined ? "$" : prefix) + v.toFixed(digits || 2);
  }

  RENDER.chart = function (box) {
    disposeChart();
    var symbol = ui.symbol, i = info(symbol), weeklyView = ui.timeframe === "weekly";
    var head = el("div", "pt-chart-head");
    var h = el("h3", null, symbol + " price chart ");
    h.id = "pt-chart-title";
    h.appendChild(sim());
    head.appendChild(h);
    var frames = el("div", "pt-segmented pt-frames");
    frames.setAttribute("role", "group");
    frames.setAttribute("aria-label", "Chart timeframe");
    [["daily", "Daily"], ["weekly", "Weekly"]].forEach(function (f) {
      var b = button(null, f[1], function () {
        ui.timeframe = f[0];
        refresh(["chart"]);
      });
      b.dataset.key = "tf-" + f[0];
      b.setAttribute("aria-pressed", ui.timeframe === f[0] ? "true" : "false");
      frames.appendChild(b);
    });
    head.appendChild(frames);
    box.appendChild(head);
    box.appendChild(el("p", "pt-small", (i.name || symbol) + (i.sector ? ", " + i.sector + " sector" : "")));
    box.appendChild(indicatorTools());
    var legend = el("p", "pt-chart-legend pt-tiny");
    var canvas = el("div", "pt-chart-canvas pt-panes-" + ui.panes.length);
    canvas.setAttribute("aria-hidden", "true");  // the summary below is the text version of the chart
    var lineList = el("ul", "pt-line-legend");
    var summary = el("p", "pt-small pt-chart-summary");
    box.appendChild(legend);
    box.appendChild(canvas);
    box.appendChild(lineList);
    box.appendChild(summary);
    var credit = el("p", "pt-tiny muted", "Chart by ");
    var link = el("a", null, "TradingView Lightweight Charts™");
    link.href = "https://www.tradingview.com/";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    credit.appendChild(link);
    credit.appendChild(document.createTextNode(", © 2026 TradingView, Inc. Prices shown are simulated."));
    box.appendChild(credit);
    loadGuide();
    var LC = window.LightweightCharts;
    if (!LC) {
      summary.textContent = "The chart could not load. Your prices and trades are still in the positions table and history.";
      return;
    }
    if (!chartData || chartData.key !== chartKey() || !(chartData.data || chartData.error)) {
      summary.textContent = "Loading simulated prices…";
      loadChart(chartKey());
      return;
    }
    if (chartData.error) {
      summary.textContent = "The chart could not load: " + chartData.error;
      return;
    }

    var data = chartData.data, bars = data.bars;
    var up = token("--up"), down = token("--down"), surface = token("--surface");
    chart = LC.createChart(canvas, {
      autoSize: true,
      layout: { background: { type: "solid", color: surface }, textColor: token("--muted"),
                fontFamily: token("--font-text"), attributionLogo: false },  // the credit line below links instead
      grid: { vertLines: { color: token("--surface-2") }, horzLines: { color: token("--surface-2") } },
      rightPriceScale: { borderColor: token("--border"), scaleMargins: { top: 0.08, bottom: 0.25 } },
      timeScale: { borderColor: token("--border"), rightOffset: 2, fixLeftEdge: true, maxBarSpacing: 28 },
      handleScroll: { vertTouchDrag: false },  // a vertical swipe on a phone still scrolls the page
    });
    // each scale formats its own numbers: dollars on the price, 0-100 for RSI, plain for MACD
    var dollars = { type: "custom", minMove: 0.01, formatter: function (p) { return "$" + p.toFixed(2); } };
    var candles = chart.addSeries(LC.CandlestickSeries, { upColor: up, downColor: down, borderUpColor: up,
      borderDownColor: down, wickUpColor: up, wickDownColor: down, priceFormat: dollars });
    candles.setData(bars.map(function (b) {
      var point = { time: b.time, open: b.o / 100, high: b.h / 100, low: b.l / 100, close: b.c / 100 };
      if (b.status === "partial") point.color = surface;  // a hollow candle: this week is not finished
      return point;
    }));
    var volume = chart.addSeries(LC.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume",
      lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volume.setData(bars.map(function (b) {
      return { time: b.time, value: b.v, color: withAlpha(b.c >= b.o ? up : down, "59") };
    }));

    // overlays: the server's values as they are; the first line solid, the second dashed, each named on the scale
    var lines = data.indicators.filter(function (ind) { return presetOf(ind, OVERLAYS); }).map(function (ind, k) {
      var values = ind.series[ind.type], name = indicatorName(ind), dashed = k === 1;
      var points = [];
      values.forEach(function (v, j) { if (v !== null) points.push({ time: bars[j].time, value: v }); });
      if (points.length) {
        chart.addSeries(LC.LineSeries, { color: token(dashed ? "--ind-b" : "--ind-a"), lineWidth: 2,
          lineStyle: dashed ? LC.LineStyle.Dashed : LC.LineStyle.Solid, title: name, priceLineVisible: false,
          crosshairMarkerVisible: false, priceFormat: dollars }).setData(points);
      }
      return { name: name, values: values, dashed: dashed };
    });

    // panes below the price, in the order chosen; one chart, so time, zoom and crosshair stay in step
    function pointsOf(values, color) {
      var out = [];
      values.forEach(function (v, j) {
        if (v !== null) out.push(color ? { time: bars[j].time, value: v, color: color(v) } : { time: bars[j].time, value: v });
      });
      return out;
    }
    var muted = token("--muted");
    var panes = data.indicators.filter(function (ind) { return presetOf(ind, PANES); }).map(function (ind, k) {
      var pane = k + 1, name = indicatorName(ind);
      var lineOptions = { lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, lastValueVisible: true };
      if (ind.type === "rsi") {
        var rsi = chart.addSeries(LC.LineSeries, Object.assign({ color: token("--ind-a"), title: name,
          priceFormat: { type: "custom", minMove: 0.1, formatter: function (v) { return v.toFixed(1); } },
          autoscaleInfoProvider: function () { return { priceRange: { minValue: 0, maxValue: 100 } }; } }, lineOptions), pane);
        rsi.setData(pointsOf(ind.series.rsi));
        [70, 30].forEach(function (level) {  // the educational guides: above 70 and below 30
          rsi.createPriceLine({ price: level, color: muted, lineWidth: 1, lineStyle: LC.LineStyle.Dashed,
            axisLabelVisible: true, title: "" });
        });
        rsi.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
      } else {
        var plain = { type: "custom", minMove: 0.01, formatter: function (v) { return v.toFixed(2); } };
        var hist = chart.addSeries(LC.HistogramSeries, { priceFormat: plain, priceLineVisible: false,
          lastValueVisible: false }, pane);
        hist.setData(pointsOf(ind.series.histogram, function (v) { return withAlpha(v >= 0 ? up : down, "73"); }));
        var line = chart.addSeries(LC.LineSeries, Object.assign({ color: token("--ind-a"), title: "MACD",
          priceFormat: plain, autoscaleInfoProvider: function (original) {  // the scale always reaches the zero line
            var r = original();
            if (r && r.priceRange) {
              r.priceRange.minValue = Math.min(r.priceRange.minValue, 0);
              r.priceRange.maxValue = Math.max(r.priceRange.maxValue, 0);
            }
            return r;
          } }, lineOptions), pane);
        line.setData(pointsOf(ind.series.macd));
        chart.addSeries(LC.LineSeries, Object.assign({ color: token("--ind-b"), lineStyle: LC.LineStyle.Dashed,
          title: "Signal", priceFormat: plain }, lineOptions), pane).setData(pointsOf(ind.series.signal));
        line.createPriceLine({ price: 0, color: muted, lineWidth: 1, lineStyle: LC.LineStyle.Dotted,
          axisLabelVisible: true, title: "" });  // the zero line
        line.priceScale().applyOptions({ scaleMargins: { top: 0.12, bottom: 0.12 } });
      }
      return { name: name, type: ind.type, series: ind.series };
    });
    if (panes.length) chart.panes()[0].setStretchFactor(panes.length === 1 ? 2.4 : 2);  // the price keeps most room

    var barTimeFor = function (date) {  // a trade's bar: its day, or the week it falls in
      var hit = bars.filter(function (b) { return b.time <= date; });
      return hit.length ? hit[hit.length - 1].time : date;
    };
    var marks = view.portfolio.transactions.filter(function (t) { return t.symbol === symbol; }).map(function (t) {
      var buy = t.side === "buy";
      return { time: barTimeFor(t.date), position: buy ? "belowBar" : "aboveBar", shape: buy ? "arrowUp" : "arrowDown",
               color: buy ? up : down, text: (buy ? "B " : "S ") + t.shares };
    });
    var trades = marks.length;
    var last = bars[bars.length - 1];
    var lastLabel = WEEK_LABELS[last.status];
    if (lastLabel) {
      marks.push({ time: last.time, position: "aboveBar", shape: "circle", color: token("--muted"), text: lastLabel });
    }
    marks.sort(function (a, b) { return a.time < b.time ? -1 : a.time > b.time ? 1 : 0; });
    LC.createSeriesMarkers(candles, marks);

    var ink = token("--text"), priceLines = [], trend = { ink: ink, lines: [], pending: null, redraw: function () {} };
    var dayText = weeklyView ? function (date) { return "the week of " + niceDate(barTimeFor(date)); } : null;
    var drawSummary = el("span");
    candles.attachPrimitive(trendLines(trend));
    drawLayer = {
      sync: function (list) {
        priceLines.forEach(function (pl) { candles.removePriceLine(pl); });
        priceLines = list.filter(function (d) { return d.kind === "h"; }).map(function (d) {
          return candles.createPriceLine({ price: d.price, color: ink, lineWidth: 1, lineStyle: LC.LineStyle.Dashed,
            axisLabelVisible: true, title: "Your line" });
        });
        // a date between weekly bars belongs to the week it falls in
        trend.lines = list.filter(function (d) { return d.kind === "t"; }).map(function (d) {
          return { t1: barTimeFor(d.a.date), p1: d.a.price, t2: barTimeFor(d.b.date), p2: d.b.price };
        });
        trend.redraw();
        drawSummary.textContent = list.length ? " Your drawings: " + list.map(function (d) {
          return describeDrawing(d, dayText).replace(/^./, function (c) { return c.toLowerCase(); });
        }).join("; ") + "." : "";
      },
      pending: function (at) {
        trend.pending = at ? { t1: barTimeFor(at.date), p1: at.price } : null;
        trend.redraw();
      },
    };
    function onChartPoint(p) {
      var price = candles.coordinateToPrice(p.point.y);
      if (price === null || !(price > 0)) return;  // above or below the price range shown
      var at = { date: timeKey(p.time), price: Math.round(price * 100) / 100 };  // the nearest bar's date, in cents
      if (ui.drawMode === "h") {
        addDrawing({ kind: "h", price: at.price });
        setDrawMode(null);
      } else if (!ui.drawStart) {
        ui.drawStart = at;
        drawLayer.pending(at);
        showBanner();
      } else if (at.date === ui.drawStart.date) {
        showBanner("Trend line: choose a second point on a different " + (weeklyView ? "week" : "day") + ". Press Esc to cancel.");
      } else {
        var ends = [ui.drawStart, at].sort(function (x, y) { return x.date < y.date ? -1 : 1; });
        addDrawing({ kind: "t", a: ends[0], b: ends[1] });
        setDrawMode(null);
      }
    }
    // The browser's pointer events, not the chart's click events: the chart treats a quick second click or tap as a
    // double-click and drops it, which would lose a trend line's second point. A press that moves is a pan, not a point.
    var pressed = null;
    canvas.addEventListener("pointerdown", function (e) { pressed = { x: e.clientX, y: e.clientY }; });
    canvas.addEventListener("pointerup", function (e) {
      if (!ui.drawMode || !chart || !pressed || Math.abs(e.clientX - pressed.x) > 6 || Math.abs(e.clientY - pressed.y) > 6) return;
      var r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, size = chart.paneSize(0);
      if (x > size.width || y > size.height) return;  // the price pane only, not its scale or the panes below
      var time = chart.timeScale().coordinateToTime(x);
      if (time !== null) onChartPoint({ time: time, point: { x: x, y: y } });
    });
    // a few bars fill the width from the left; a long history opens on the latest 90 bars (zoom out for the rest)
    var shownBars = Math.min(bars.length, 90);
    if (lastLabel) {
      // the Partial / Final Short Week label sits over the last bar, and "Your line" labels sit at the right edge:
      // leave about 120 px after the last bar so they never cover each other. Empty slots also narrow the bars, so
      // solve for them: k slots of width W / (n + k) make 120 px, unless bars are already at their widest (28 px).
      var plotWidth = Math.max(canvas.clientWidth - 70, 160);
      var slots = Math.ceil(120 * shownBars / (plotWidth - 120));
      if (plotWidth / (shownBars + Math.ceil(120 / 28)) >= 28) slots = Math.ceil(120 / 28);
      chart.timeScale().setVisibleLogicalRange({ from: bars.length - shownBars, to: bars.length - 1 + slots });
      requestAnimationFrame(function () {  // the measured gap, for the visual regression check
        if (!chart) return;
        var x = chart.timeScale().timeToCoordinate(last.time);
        if (x !== null) canvas.dataset.weekLabelRoom = String(Math.round(chart.paneSize(0).width - x));
      });
    } else if (bars.length > 90) {
      chart.timeScale().setVisibleLogicalRange({ from: bars.length - 90, to: bars.length + 1 });
    } else {
      chart.timeScale().fitContent();
    }

    var indexOf = {};
    bars.forEach(function (b, j) { indexOf[b.time] = j; });
    function readout(j) {
      var b = bars[j];
      var text = (weeklyView ? (WEEK_LABELS[b.status] || "Week") + " of " : "") + niceDate(b.time) + ": open "
        + money(b.o) + ", high " + money(b.h) + ", low " + money(b.l) + ", close " + money(b.c) + ", volume "
        + b.v.toLocaleString("en-US") + ".";
      var partial = b.status === "partial";
      lines.forEach(function (l) {
        text += " " + l.name + " " + (partial ? "not calculated for a Partial Week" : lineValue(l.values[j])) + ".";
      });
      panes.forEach(function (pn) {
        text += " " + pn.name + " " + (partial ? "not calculated for a Partial Week" : paneValue(pn, j)) + ".";
      });
      legend.textContent = text;
    }
    readout(bars.length - 1);
    chart.subscribeCrosshairMove(function (p) {
      var j = indexOf[timeKey(p.time)];
      readout(j === undefined ? bars.length - 1 : j);
    });

    function paneValue(pn, j) {
      if (pn.type === "rsi") return lineValue(pn.series.rsi[j], 1, "");
      return "MACD " + lineValue(pn.series.macd[j], 2, "") + ", signal " + lineValue(pn.series.signal[j], 2, "")
        + ", histogram " + lineValue(pn.series.histogram[j], 2, "");
    }

    // each line's latest value: the last completed bar (a Partial Week has none)
    var settled = last.status === "partial" ? bars.length - 2 : bars.length - 1;
    var lineText = lines.map(function (l) {
      var item = el("li");
      var swatch = el("span", "pt-swatch" + (l.dashed ? " pt-swatch-b" : ""));
      swatch.setAttribute("aria-hidden", "true");
      item.appendChild(swatch);
      var value = settled >= 0 ? lineValue(l.values[settled]) : "Not enough data";
      item.appendChild(document.createTextNode(l.name + " "));
      item.appendChild(el("strong", null, value));
      lineList.appendChild(item);
      return l.name + " (" + (l.dashed ? "dashed" : "solid") + ") " + value;
    });
    var paneText = panes.map(function (pn) {
      var value = settled >= 0 ? paneValue(pn, settled) : "Not enough data";
      var item = el("li");
      item.appendChild(document.createTextNode(pn.name + " "));
      item.appendChild(el("strong", null, value));
      lineList.appendChild(item);
      return pn.name + (pn.type === "rsi" ? " (0 to 100, guides at 30 and 70) " : ": ") + value;
    });
    if (!lines.length && !panes.length) lineList.remove();

    var high = Math.max.apply(null, bars.map(function (b) { return b.h; }));
    var low = Math.min.apply(null, bars.map(function (b) { return b.l; }));
    summary.textContent = (weeklyView ? "Weekly" : "Daily") + " simulated prices from " + niceDate(bars[0].time)
      + " to " + niceDate(view.day.date) + ": last close " + money(last.c) + ", highest " + money(high) + ", lowest "
      + money(low) + ". " + (trades ? trades + (trades === 1 ? " of your trades is" : " of your trades are")
      + " marked: B for a buy, S for a sell." : "Your trades in " + symbol + " will be marked on the chart.")
      + (lineText.length ? " Lines on the price: " + lineText.join(", ") + "."
        + (weeklyView ? " Weekly lines use completed weeks only." : "") : "")
      + (paneText.length ? " Panes below the price: " + paneText.join("; ") + "."
        + (weeklyView && !lineText.length ? " Weekly values use completed weeks only." : "") : "")
      + (lastLabel === "Partial Week" ? " The last bar is a Partial Week: this week so far, which can still change."
        : lastLabel ? " The last bar is the Final Short Week: the scenario's final " + last.days + " trading days." : "")
      + " Scroll or pinch to zoom and drag to move through time.";
    summary.appendChild(drawSummary);
    if (data.indicators.length) box.appendChild(explanationCards(data.indicators));
    box.appendChild(drawingsPanel());
    syncDrawings();
    fillTrendDates();
    if (ui.drawStart) drawLayer.pending(ui.drawStart);
  };

  // One card per active indicator: the reading the API chose from unrounded values, then Learn more (closed by
  // default) with the approved explanation. Nothing is calculated here.
  function explanationCards(items) {
    var wrap = el("div", "pt-cards");
    var lineSlot = 0;
    items.forEach(function (ind) {
      var key = presetKey(ind.type, ind.period), name = indicatorName(ind);
      var entry = guideText && guideText.indicators && guideText.indicators[ind.type];
      var style = presetOf(ind, OVERLAYS) ? (lineSlot++ === 0 ? "solid line" : "dashed line") : entry ? entry.style : "";
      var card = el("section", "pt-card");
      var head = el("h4", null, name + (style ? " (" + style + ")" : "") + " ");
      head.id = "pt-card-" + key;
      head.appendChild(sim());
      card.setAttribute("aria-labelledby", head.id);
      card.appendChild(head);
      card.appendChild(el("p", "pt-card-now", ind.reading));
      var more = el("details", "pt-learn-more");
      more.open = !!ui.learnOpen[key];
      more.addEventListener("toggle", function () { ui.learnOpen[key] = more.open; });
      var summary = el("summary", null, "Learn more");
      summary.dataset.key = "learn-" + key;
      summary.setAttribute("aria-label", "Learn more about " + name);
      more.appendChild(summary);
      more.appendChild(explanation(ind.type, ind.period, false));
      card.appendChild(more);
      card.appendChild(el("p", "pt-edu-note", guideText && guideText.footer
        ? guideText.footer : "Education only. An indicator describes past simulated prices; it is not a recommendation to buy or sell."));
      wrap.appendChild(card);
    });
    return wrap;
  }

  // ---- watchlist ----

  function marketIsCurrent() {
    return market && market.dates.length === view.day.index + 1;
  }

  function sparkline(bars) {
    var closes = bars.slice(-30).map(function (b) { return b.c; });
    var lo = Math.min.apply(null, closes), hi = Math.max.apply(null, closes), span = hi - lo || 1;
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 100 24");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("class", "pt-spark-box");
    var line = document.createElementNS(SVG_NS, "polyline");
    line.setAttribute("points", closes.map(function (c, k) {
      return (k * 100 / Math.max(closes.length - 1, 1)).toFixed(1) + "," + (22 - (c - lo) / span * 20).toFixed(1);
    }).join(" "));
    line.setAttribute("class", "pt-spark " + (closes[closes.length - 1] >= closes[0] ? "pt-rise" : "pt-fall"));
    svg.appendChild(line);
    return svg;
  }

  function watchItem(symbol) {
    var i = info(symbol);
    var b = button("pt-watch-item", null, function () { pickToTrade(symbol); });
    b.dataset.symbol = symbol;
    b.dataset.key = "watch-" + symbol;
    b.setAttribute("aria-current", symbol === ui.symbol ? "true" : "false");
    b.appendChild(el("strong", null, symbol));
    b.appendChild(el("span", "pt-num", money(closeOf(symbol))));
    b.appendChild(el("span", "pt-tiny muted", i.name || ""));
    if (marketIsCurrent() && view.day.index > 0) {
      var bars = market.bars[symbol];
      var change = bars[bars.length - 1].c / bars[bars.length - 2].c - 1;
      var text = (change > 0 ? "+" : "") + (change * 100).toFixed(1) + "%";
      b.appendChild(pl(Math.round(change * 10000), text));
    } else {
      b.appendChild(el("span", "pt-tiny muted", view.day.index === 0 ? "First day" : ""));
    }
    if (marketIsCurrent()) b.appendChild(sparkline(market.bars[symbol]));
    return b;
  }

  RENDER.watch = function (box) {
    var details = el("details", "pt-watch-box");
    details.open = ui.watchOpen;
    details.addEventListener("toggle", function () { ui.watchOpen = details.open; });
    var summary = el("summary");
    summary.dataset.key = "watch-summary";
    var h = el("h2", null, "Practice tickers ");
    h.appendChild(sim());
    summary.appendChild(h);
    details.appendChild(summary);
    var groups = [];  // [sector or "", [symbols]] in scenario order
    Object.keys(view.quotes).forEach(function (s) {
      var sector = info(s).sector || "";
      var g = groups.filter(function (x) { return x[0] === sector; })[0];
      if (!g) groups.push(g = [sector, []]);
      g[1].push(s);
    });
    groups.forEach(function (g) {
      if (g[0]) details.appendChild(el("h3", "pt-sector", g[0]));
      var list = el("ul", "pt-watchlist");
      g[1].forEach(function (s) {
        var li = el("li");
        li.appendChild(watchItem(s));
        list.appendChild(li);
      });
      details.appendChild(list);
    });
    details.appendChild(el("p", "pt-tiny muted", "Simulated closing prices. Change is since the previous simulated day. "
      + "Select a ticker to trade it."));
    box.appendChild(details);
  };

  // ---- positions, pending orders, history ----

  RENDER.positions = function (box) {
    var h = el("h3", null, "Positions ");
    h.id = "pt-positions-title";
    h.tabIndex = -1;
    h.appendChild(sim());
    box.appendChild(h);
    var positions = view.portfolio.positions;
    if (!positions.length) {
      box.appendChild(el("p", "muted", "No holdings yet. Choose a ticker, preview an order and confirm it to start."));
      return;
    }
    var table = el("table", "pt-table");
    table.setAttribute("aria-labelledby", "pt-positions-title");
    var head = el("tr");
    ["Ticker", "Shares", "Avg cost", "Last", "Market value", "Unrealized"].forEach(function (c) {
      var th = el("th", null, c);
      th.scope = "col";
      head.appendChild(th);
    });
    var thead = el("thead");
    thead.appendChild(head);
    table.appendChild(thead);
    var body = el("tbody");
    positions.forEach(function (p) {
      var tr = el("tr");
      tr.dataset.symbol = p.symbol;
      tr.addEventListener("click", function (e) { if (!e.target.closest("button")) pickToTrade(p.symbol); });
      var first = el("td");
      first.dataset.label = "Ticker";
      var pick = button("pt-link", p.symbol, function () { pickToTrade(p.symbol); });
      pick.dataset.key = "pos-" + p.symbol;
      pick.setAttribute("aria-label", "Trade " + p.symbol);
      first.appendChild(pick);
      if (info(p.symbol).sector) first.appendChild(el("span", "pt-tiny muted", info(p.symbol).sector));
      tr.appendChild(first);
      [["Shares", String(p.shares)], ["Avg cost", money(p.average_cost_cents)], ["Last", money(p.close_cents)],
       ["Market value", money(p.market_value_cents)]].forEach(function (c) {
        var td = el("td", null, c[1]);
        td.dataset.label = c[0];
        tr.appendChild(td);
      });
      var last = el("td");
      last.dataset.label = "Unrealized";
      last.appendChild(pl(p.unrealized_pl_cents));
      tr.appendChild(last);
      body.appendChild(tr);
    });
    table.appendChild(body);
    box.appendChild(table);
    box.appendChild(el("p", "pt-tiny muted", "Last is the latest simulated close. Select a ticker to trade it."));
  };

  RENDER.pending = function (box) {
    var h = el("h3", null, "Pending orders");
    h.id = "pt-pending-title";
    h.tabIndex = -1;
    box.appendChild(h);
    var pending = view.orders.filter(function (o) { return o.status === "pending"; });
    if (!pending.length) {
      box.appendChild(el("p", "muted", "None. Orders you confirm wait here until the next simulated open."));
      return;
    }
    var list = el("ul", "pt-list");
    pending.forEach(function (o) {
      var li = el("li", "pt-item");
      li.appendChild(el("p", "pt-item-title", describe(o)));
      li.appendChild(el("p", "pt-small", "Fills at the next simulated open."));
      var b = button("button-secondary", "Cancel order", function () { cancelOrder(o.id); });
      b.dataset.busy = "";
      b.dataset.key = "cancel-" + o.id;
      b.setAttribute("aria-label", "Cancel order: " + describe(o));
      li.appendChild(b);
      list.appendChild(li);
    });
    box.appendChild(list);
  };

  RENDER.history = function (box) {
    var journal = readJournal();
    var fills = {};
    view.portfolio.transactions.forEach(function (t) { fills[t.order_id] = t; });
    var done = view.orders.filter(function (o) { return o.status !== "pending"; }).reverse();
    var details = el("details", "card pt-history");
    details.open = ui.historyOpen;
    details.addEventListener("toggle", function () { ui.historyOpen = details.open; });
    var summary = el("summary", null, "History (" + done.length + ")");
    summary.dataset.key = "history-summary";
    details.appendChild(summary);
    box.appendChild(details);
    if (!done.length) {
      details.appendChild(el("p", "muted", "No filled, rejected or cancelled orders yet."));
      return;
    }
    var symbols = done.map(function (o) { return o.symbol; }).filter(function (s, k, all) { return all.indexOf(s) === k; });
    if (symbols.indexOf(ui.historyFilter) === -1) ui.historyFilter = "";
    var filter = el("label", "pt-small pt-filter", "Show ");
    var select = el("select");
    select.dataset.key = "history-filter";
    [""].concat(symbols).forEach(function (s) {
      var o = el("option", null, s || "All tickers");
      o.value = s;
      select.appendChild(o);
    });
    select.value = ui.historyFilter;
    select.addEventListener("change", function () { ui.historyFilter = select.value; refresh(["history"]); });
    filter.appendChild(select);
    details.appendChild(filter);
    var list = el("ul", "pt-history-list");
    done.filter(function (o) { return !ui.historyFilter || o.symbol === ui.historyFilter; }).forEach(function (o) {
      var li = el("li", "pt-" + o.status);
      var t = fills[o.id];
      var line = el("p");
      if (t) {
        line.appendChild(el("strong", null, (o.side === "buy" ? "Bought " : "Sold ") + o.shares + " " + o.symbol));
        line.appendChild(document.createTextNode(" at " + money(t.price_cents) + ", simulated fill on " + niceDate(t.date)
          + ". " + (o.side === "buy" ? "Cost " : "Proceeds ") + money(t.amount_cents) + "."));
      } else {
        line.appendChild(el("strong", null, describe(o) + " " + o.status));
      }
      li.appendChild(line);
      if (t && t.realized_pl_cents !== null) {
        var r = el("p", "pt-small", "Realized ");
        r.appendChild(pl(t.realized_pl_cents));
        li.appendChild(r);
      }
      if (o.reason) li.appendChild(el("p", "pt-small", o.reason));
      var note = journal[o.id];
      if (note) {
        if (note.why) li.appendChild(el("p", "pt-note", "Why: " + note.why));
        if (note.risks) li.appendChild(el("p", "pt-note", "What could go wrong: " + note.risks));
      }
      list.appendChild(li);
    });
    details.appendChild(list);
  };

  function learnMore() {
    var card = el("section", "card pt-learn");
    card.setAttribute("aria-labelledby", "pt-learn-title");
    var h = el("h3", null, "Learn more");
    h.id = "pt-learn-title";
    card.appendChild(h);
    var links = el("div", "pt-links");
    links.appendChild(button("button-secondary", "Accounts 101: Cash brokerage", function () {
      if (window.Accounts) window.Accounts.open("Cash brokerage");
    }));
    [["Paying for trades on time", "brokerage-agreement", "ba-settlement"],
     ["Why this practice has no margin", "margin-agreement", "ma-lose-more"]].forEach(function (g) {
      links.appendChild(button("button-secondary", g[0], function () {
        var tab = document.querySelector('[data-tab="sign"]');
        if (tab) tab.click();
        if (window.Sign && window.Sign.openAt) window.Sign.openAt(g[1], g[2]);
      }));
    });
    card.appendChild(links);
    card.appendChild(el("p", "pt-small", "Your practice session and journal are kept in this browser's storage. "
      + "Clearing site data deletes them, and anyone using the same browser profile can see them."));
    return card;
  }

  // ---- order ticket: edit, review (after Preview) and queued (after Confirm), swapped in place ----

  function renderTicket(focusId) {
    var box = regions.ticket;
    var hadFocus = box.contains(document.activeElement);
    regions.form = null;
    box.textContent = "";
    var head = el("div", "pt-ticket-head");
    var h = el("h2", null, ui.mode === "review" ? "Check your practice order"
      : ui.mode === "queued" ? "Order queued" : "Practice order");
    h.id = "pt-ticket-title";
    h.tabIndex = -1;
    head.appendChild(h);
    head.appendChild(sim());
    var close = button("pt-sheet-close", "×", function () { closeSheet(); });
    close.setAttribute("aria-label", "Close trade sheet");
    head.appendChild(close);
    box.appendChild(head);
    box.appendChild(ui.mode === "review" ? reviewPanel() : ui.mode === "queued" ? queuedPanel() : editForm());
    setBusy(busy);
    var target = focusId ? document.getElementById(focusId) : hadFocus ? h : null;
    if (target) target.focus();
  }

  function field(labelText, id) {
    var l = el("label", "pt-label", labelText);
    l.htmlFor = id;
    return l;
  }

  function editForm() {
    var form = el("form", "pt-form");
    form.noValidate = true;
    form.addEventListener("submit", function (e) { e.preventDefault(); previewOrder(); });

    var combo = el("div", "pt-combo");
    combo.appendChild(field("Ticker", "pt-ticker"));
    var input = el("input");
    input.id = "pt-ticker";
    input.type = "text";
    input.value = ui.symbol;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", "pt-ticker-list");
    input.setAttribute("aria-describedby", "pt-ticker-info");
    var list = el("ul", "pt-combo-list");
    list.id = "pt-ticker-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Practice tickers");
    list.hidden = true;
    var tickerInfo = el("p", "pt-tiny muted");
    tickerInfo.id = "pt-ticker-info";
    combo.appendChild(input);
    combo.appendChild(list);
    combo.appendChild(tickerInfo);
    form.appendChild(combo);
    setupCombo(input, list);

    var sides = el("div", "pt-segmented");
    sides.setAttribute("role", "group");
    sides.setAttribute("aria-label", "Order side");
    ["buy", "sell"].forEach(function (side) {
      var b = button(null, side === "buy" ? "Buy" : "Sell", function () {
        ui.side = side;
        ui.problem = "";
        updateTicketFigures();
      });
      b.dataset.side = side;
      sides.appendChild(b);
    });
    form.appendChild(sides);

    var qty = el("div", "pt-qty");
    qty.appendChild(field("Shares", "pt-shares"));
    var stepper = el("div", "pt-stepper");
    var shares = el("input");
    shares.id = "pt-shares";
    shares.type = "text";
    shares.inputMode = "numeric";
    shares.autocomplete = "off";
    shares.value = ui.shares;
    shares.setAttribute("aria-describedby", "pt-shares-help pt-ticket-problem");
    shares.addEventListener("input", function () {
      ui.shares = shares.value.trim();
      ui.problem = "";
      updateTicketFigures();
    });
    function step(by) {
      var n = /^\d+$/.test(ui.shares) ? Number(ui.shares) : 0;
      ui.shares = String(Math.min(Math.max(n + by, 1), MAX_SHARES));
      shares.value = ui.shares;
      ui.problem = "";
      updateTicketFigures();
    }
    var minus = button("pt-step", "−", function () { step(-1); });
    minus.setAttribute("aria-label", "One share fewer");
    var plus = button("pt-step", "+", function () { step(1); });
    plus.setAttribute("aria-label", "One share more");
    var max = button("button-secondary pt-max", "Max", function () {
      ui.shares = String(limits().max);
      shares.value = ui.shares;
      ui.problem = "";
      updateTicketFigures();
    });
    max.setAttribute("aria-describedby", "pt-shares-help");
    stepper.appendChild(minus);
    stepper.appendChild(shares);
    stepper.appendChild(plus);
    stepper.appendChild(max);
    qty.appendChild(stepper);
    var help = el("p", "pt-tiny muted");
    help.id = "pt-shares-help";
    qty.appendChild(help);
    form.appendChild(qty);

    var estimate = el("div", "pt-estimate");
    var estLabel = el("span", "pt-small");
    var estValue = el("strong");
    estimate.appendChild(estLabel);
    estimate.appendChild(estValue);
    form.appendChild(estimate);
    var problem = el("p", "pt-error-line");
    problem.id = "pt-ticket-problem";
    problem.setAttribute("aria-live", "polite");
    form.appendChild(problem);
    form.appendChild(el("p", "pt-small", "Market orders fill at the next simulated day's opening price, which can "
      + "differ from the preview. Cash only: no borrowing, short selling or options."));
    var preview = el("button", "button-primary pt-block", "Preview order");
    preview.type = "submit";
    preview.dataset.busy = "open";
    preview.dataset.key = "preview";
    form.appendChild(preview);

    regions.form = { input: input, info: tickerInfo, sides: sides, shares: shares, help: help, max: max,
                     estLabel: estLabel, estValue: estValue, problem: problem };
    updateTicketFigures();
    return form;
  }

  // What the engine would allow right now, mirroring its preview checks: cash after pending buys at today's
  // closes, or shares held minus pending sells. Preview stays the authority.
  function limits() {
    var pending = view.orders.filter(function (o) { return o.status === "pending"; });
    if (ui.side === "buy") {
      var reserved = pending.filter(function (o) { return o.side === "buy"; })
        .reduce(function (sum, o) { return sum + o.shares * closeOf(o.symbol); }, 0);
      var available = Math.max(view.portfolio.cash_cents - reserved, 0);
      return { available: available, max: Math.min(Math.floor(available / closeOf(ui.symbol)), MAX_SHARES) };
    }
    var held = view.portfolio.positions.filter(function (p) { return p.symbol === ui.symbol; })
      .reduce(function (sum, p) { return sum + p.shares; }, 0);
    var selling = pending.filter(function (o) { return o.side === "sell" && o.symbol === ui.symbol; })
      .reduce(function (sum, o) { return sum + o.shares; }, 0);
    return { max: Math.max(held - selling, 0) };
  }

  function updateTicketFigures() {
    var f = regions && regions.form;
    if (!f) return;
    var symbol = ui.symbol, i = info(symbol), lim = limits(), buy = ui.side === "buy";
    f.info.textContent = (i.name || symbol) + (i.sector ? ", " + i.sector : "") + ". Simulated close "
      + money(closeOf(symbol)) + ".";
    f.sides.querySelectorAll("button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.side === ui.side ? "true" : "false");
    });
    var whole = /^\d+$/.test(ui.shares) && Number(ui.shares) >= 1;
    var amount = whole ? Number(ui.shares) * closeOf(symbol) : null;
    f.estLabel.textContent = buy ? "Estimated cost" : "Estimated proceeds";
    f.estValue.textContent = amount === null ? "Enter shares" : money(amount);
    f.help.textContent = "Whole shares only. " + (buy
      ? "Up to " + lim.max.toLocaleString("en-US") + " at today's simulated close, after pending buys."
      : "You can sell up to " + lim.max.toLocaleString("en-US") + " " + symbol + ", counting pending sells.");
    f.max.disabled = lim.max < 1;
    var problem = ui.problem;
    if (!problem && ui.shares !== "" && !whole) problem = "Enter a whole number of shares, like 1 or 10.";
    if (!problem && whole && buy && amount > lim.available) {
      problem = "That costs about " + money(amount) + "; you have " + money(lim.available) + " available after pending buys.";
    }
    if (!problem && whole && !buy && Number(ui.shares) > lim.max) {
      problem = "You can sell at most " + lim.max + " shares of " + symbol + ", counting pending sells.";
    }
    f.problem.textContent = problem;
    f.problem.hidden = !problem;
    f.shares.setAttribute("aria-invalid", problem ? "true" : "false");
  }

  // Searchable ticker picker (ARIA combobox with a listbox): type to filter by ticker, name or sector, arrows to move,
  // Enter to choose, Escape to close.
  function setupCombo(input, list) {
    var matches = [], active = -1;
    function matching(q) {
      q = q.trim().toLowerCase();
      return Object.keys(view.quotes).filter(function (s) {
        var i = info(s);
        return !q || (s + " " + (i.name || "") + " " + (i.sector || "")).toLowerCase().indexOf(q) !== -1;
      });
    }
    function open(q) {
      matches = matching(q);
      list.textContent = "";
      matches.forEach(function (s) {
        var i = info(s);
        var li = el("li", "pt-option");
        li.id = "pt-opt-" + s;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", s === ui.symbol ? "true" : "false");
        li.appendChild(el("strong", null, s));
        li.appendChild(el("span", "pt-tiny muted", (i.name || "") + (i.sector ? ", " + i.sector : "")));
        li.addEventListener("mousedown", function (e) { e.preventDefault(); });  // keep focus in the input
        li.addEventListener("click", function () { choose(s); });
        list.appendChild(li);
      });
      if (!matches.length) {
        var none = el("li", "pt-option pt-tiny muted", "No practice ticker matches.");
        none.setAttribute("role", "option");
        none.setAttribute("aria-disabled", "true");
        list.appendChild(none);
      }
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }
    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }
    function highlight() {
      [].forEach.call(list.children, function (li, k) { li.classList.toggle("pt-active", k === active); });
      if (active >= 0) {
        input.setAttribute("aria-activedescendant", "pt-opt-" + matches[active]);
        list.children[active].scrollIntoView({ block: "nearest" });
      }
    }
    function choose(s) {
      close();
      input.value = s;
      selectSymbol(s);
    }
    input.addEventListener("input", function () {
      open(input.value);
      active = matches.length ? 0 : -1;
      highlight();
    });
    input.addEventListener("click", function () {
      if (list.hidden) open("");
      else close();
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (list.hidden) open("");
        if (!matches.length) return;
        active = e.key === "ArrowDown" ? Math.min(active + 1, matches.length - 1) : Math.max(active - 1, 0);
        highlight();
      } else if (e.key === "Enter" && !list.hidden && active >= 0) {
        e.preventDefault();  // choose the option; Enter with the list closed submits the ticket
        choose(matches[active]);
      } else if (e.key === "Escape" && !list.hidden) {
        e.preventDefault();
        e.stopPropagation();  // close the list, not the trade sheet
        close();
      }
    });
    input.addEventListener("blur", function () {
      close();
      var typed = input.value.trim().toUpperCase();
      if (view.quotes[typed]) {
        if (typed !== ui.symbol) selectSymbol(typed);
        input.value = typed;
      } else if (!typed) {
        input.value = ui.symbol;
      }
    });
  }

  function reviewPanel() {
    var p = draft.preview, buy = p.side === "buy";
    var wrap = el("div", "pt-form");
    var box = el("div", "pt-review");
    box.appendChild(el("p", "pt-review-what", describe(p)));
    var dl = el("dl");
    [["Today's simulated close", money(p.reference_close_cents)],
     [buy ? "Estimated cost" : "Estimated proceeds", money(p.estimated_amount_cents)],
     ["Cash after it fills, estimated", money(view.portfolio.cash_cents + (buy ? -1 : 1) * p.estimated_amount_cents)],
     ["Fills at", "Next simulated day's open"]].forEach(function (row) {
      dl.appendChild(el("dt", null, row[0]));
      dl.appendChild(el("dd", null, row[1]));
    });
    box.appendChild(dl);
    box.appendChild(el("p", "pt-small", p.fill_note));
    if (p.warning) box.appendChild(el("p", "pt-error-line", p.warning));
    wrap.appendChild(box);

    var journal = el("fieldset", "pt-journal");
    journal.appendChild(el("legend", null, "Practice journal (optional)"));
    var why = el("textarea");
    why.id = "pt-why";
    why.maxLength = 280;
    why.rows = 2;
    var risks = el("textarea");
    risks.id = "pt-risks";
    risks.maxLength = 280;
    risks.rows = 2;
    journal.appendChild(field("Why are you making this trade?", "pt-why"));
    journal.appendChild(why);
    journal.appendChild(field("What could go wrong?", "pt-risks"));
    journal.appendChild(risks);
    journal.appendChild(el("p", "pt-tiny muted", "Saved only in this browser and never sent anywhere. Do not include "
      + "personal or account information."));
    wrap.appendChild(journal);

    var actions = el("div", "pt-actions");
    var confirm = button("button-primary pt-confirm", "Confirm practice order", function () {
      confirmOrder(why.value.trim(), risks.value.trim());
    });
    confirm.dataset.busy = "open";
    actions.appendChild(confirm);
    actions.appendChild(button("button-secondary", "Back", function () {
      draft = null;  // Back keeps ticker, side and shares; nothing was sent
      ui.mode = "edit";
      renderTicket("pt-shares");
    }));
    wrap.appendChild(actions);
    return wrap;
  }

  function queuedPanel() {
    var wrap = el("div", "pt-form");
    var status = el("p", null, ui.queuedText);
    status.setAttribute("role", "status");
    wrap.appendChild(status);
    var actions = el("div", "pt-actions");
    var stillPending = view.orders.some(function (o) { return o.id === ui.queuedId && o.status === "pending"; });
    if (stillPending) {
      var cancel = button("button-secondary", "Cancel this order", function () { cancelOrder(ui.queuedId); });
      cancel.dataset.busy = "";
      actions.appendChild(cancel);
    }
    actions.appendChild(button("button-primary", "New order", function () {
      ui.mode = "edit";
      renderTicket("pt-ticker");
    }));
    wrap.appendChild(actions);
    return wrap;
  }

  // ---- phone: the ticket becomes a bottom sheet opened by the Trade button ----

  function openSheet(focusId) {
    if (!PHONE.matches || ui.sheetOpen) {
      if (focusId && document.getElementById(focusId)) document.getElementById(focusId).focus();
      return;
    }
    ui.sheetOpen = true;
    var t = regions.ticket;
    t.classList.add("pt-open");
    t.setAttribute("role", "dialog");
    t.setAttribute("aria-modal", "true");
    regions.scrim.hidden = false;
    regions.tradeBar.setAttribute("aria-expanded", "true");
    document.body.classList.add("pt-sheet-open");
    var target = focusId ? document.getElementById(focusId) : t.querySelector("#pt-ticker, button.button-primary");
    (target || t.querySelector("h2")).focus();
  }

  function closeSheet(silent) {
    if (!ui.sheetOpen || !regions) return;
    ui.sheetOpen = false;
    var t = regions.ticket;
    t.classList.remove("pt-open");
    t.removeAttribute("role");
    t.removeAttribute("aria-modal");
    regions.scrim.hidden = true;
    regions.tradeBar.setAttribute("aria-expanded", "false");
    document.body.classList.remove("pt-sheet-open");
    if (!silent) regions.tradeBar.focus();
  }

  function sheetKeys(e) {
    if (!ui.sheetOpen) return;
    if (e.key === "Escape") {
      closeSheet();
      return;
    }
    if (e.key !== "Tab") return;  // keep Tab inside the open sheet
    var items = [].filter.call(regions.ticket.querySelectorAll("button, input, textarea, select"), function (n) {
      return !n.disabled && n.offsetParent !== null;
    });
    if (!items.length) return;
    var first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  // the Trade bar and toasts sit above the fixed bottom tabs and the sticky disclaimer footer
  function dock() {
    if (!root) return;
    var footer = document.getElementById("disclaimer-footer"), tabs = document.querySelector(".tabs"), h = 0;
    if (tabs && getComputedStyle(tabs).position === "fixed") h += tabs.offsetHeight;
    if (footer && getComputedStyle(footer).position === "sticky") h += footer.offsetHeight;
    root.style.setProperty("--pt-dock", h + "px");
  }

  // ---- start and damaged screens ----

  function showDamaged(detail) {
    closeSheet(true);
    disposeChart();
    view = null;
    draft = null;
    regions = null;
    root.textContent = "";
    root.appendChild(banner());
    var box = el("div", "card pt-damaged");
    box.setAttribute("role", "alert");
    box.appendChild(el("h2", null, "Your saved practice session could not be opened"));
    box.appendChild(el("p", null, detail || "The saved session is damaged or was changed."));
    box.appendChild(el("p", null, "It has not been replaced. You can start over, which deletes the saved practice "
      + "session and journal notes from this browser."));
    box.appendChild(button("button-primary", "Start a new practice session", startNew));
    root.appendChild(box);
  }

  function renderStart() {
    disposeChart();
    regions = null;
    root.textContent = "";
    root.appendChild(banner());
    var wrap = el("div", "pt-empty");
    var box = el("section", "card pt-start");
    box.setAttribute("aria-labelledby", "paper-title");
    box.appendChild(sim("Simulated practice"));
    var title = el("h2", null, "Practice trading with money that isn't real");
    title.id = "paper-title";
    title.tabIndex = -1;
    box.appendChild(title);
    box.appendChild(el("p", null, "You get $10,000.00 of fictional cash and a made-up market to try buying and selling, "
      + "one simulated day at a time, without risking real money."));
    var pick = el("fieldset", "pt-markets");
    pick.appendChild(el("legend", null, "Practice market"));
    pick.hidden = true;  // shown once the list arrives; without it the default market is used
    box.appendChild(pick);
    window.Api.getPaperScenarios().then(function (env) {
      if (!env.ok) return;
      env.data.scenarios.forEach(function (s) {
        var label = el("label", "pt-market");
        var radio = el("input");
        radio.type = "radio";
        radio.name = "pt-market";
        radio.value = s.id;
        radio.checked = s.id === scenarioId;
        radio.addEventListener("change", function () { scenarioId = s.id; });
        var symbols = Object.keys(s.symbols);
        var sectors = symbols.map(function (k) { return s.symbols[k].sector; })
          .filter(function (x, k, all) { return x && all.indexOf(x) === k; });
        var text = el("span", "pt-market-text");
        text.appendChild(el("strong", null, s.label));
        text.appendChild(el("span", "pt-small muted", symbols.length + " fictional companies"
          + (sectors.length ? " in " + sectors.length + " sectors" : "") + ", " + s.days + " simulated days"));
        label.appendChild(radio);
        label.appendChild(text);
        pick.appendChild(label);
      });
      pick.hidden = false;
    });
    box.appendChild(button("button-primary pt-start-button", "Start practicing with $10,000", startNew));
    wrap.appendChild(box);

    var how = el("section", "pt-how");
    how.setAttribute("aria-labelledby", "pt-how-title");
    var h = el("h3", null, "How this works");
    h.id = "pt-how-title";
    how.appendChild(h);
    var steps = el("ol", "pt-steps");
    [["Pick a ticker", "Choose one of the fictional practice companies."],
     ["Preview and confirm", "See the estimated cost first. Nothing happens until you confirm."],
     ["Advance a day", "Your order fills at the next day's opening price. Then see how it went."]].forEach(function (s) {
      var li = el("li");
      li.appendChild(el("strong", null, s[0]));
      li.appendChild(el("span", "pt-small muted", s[1]));
      steps.appendChild(li);
    });
    how.appendChild(steps);
    wrap.appendChild(how);
    wrap.appendChild(el("p", "pt-small muted", "Prices are generated by a computer program and are not real. Fees, "
      + "spreads and slippage are not modelled. Your practice is saved in this browser only; clearing site data removes it."));
    root.appendChild(wrap);
  }

  function show() {
    if (!root || started) return;
    started = true;
    dock();
    var saved = readSession();
    if (saved === null) {
      renderStart();
    } else if (saved.damaged) {
      showDamaged("The saved session in this browser could not be read.");
    } else {
      root.textContent = "";
      root.appendChild(el("p", "muted", "Loading your practice session…"));
      call("view", { state: saved }, load);
    }
  }

  PHONE.addEventListener("change", function () {
    if (!PHONE.matches) closeSheet(true);
    dock();
  });
  window.addEventListener("resize", dock);
  document.addEventListener("keydown", function (e) {  // Esc leaves a drawing mode
    if (e.key === "Escape" && ui.drawMode && regions) setDrawMode(null);
  });
  document.addEventListener("click", function (e) {  // the Indicators popover closes on a click elsewhere
    if (ui.indMenuOpen && regions && !e.target.closest(".pt-tools")) setMenu(false, false);
  });
  // the chart draws on a canvas with colours read from the theme tokens, so it is redrawn when the theme changes
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { refresh(["chart"]); });
  new MutationObserver(function () { refresh(["chart"]); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  window.Paper = {
    init: function () { root = document.getElementById("paper-root"); },
    show: show,
  };
})();
