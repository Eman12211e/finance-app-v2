// Practice Trading tab in #paper-root: a simulated, synthetic-price trading practice built on /api/paper.
// The signed session lives in localStorage; journal notes live in localStorage too and are never sent to the server.
// Nothing here is a real price, order, account or recommendation.
// The workspace is built once per loaded session; each action then redraws only the regions it changed.
(function () {
  "use strict";

  var SESSION_KEY = "paper-session-v1";
  var JOURNAL_KEY = "paper-journal-v1";
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
    return { symbol: null, side: "buy", shares: "1", mode: "edit", queuedId: null, queuedText: "", problem: "",
             historyOpen: true, historyFilter: "", watchOpen: !PHONE.matches, sheetOpen: false, timeframe: "daily" };
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
      refresh(["watch", "chart"]);
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
  }

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function withAlpha(color, alpha) {  // tokens are #rrggbb; the canvas needs a plain colour string
    return /^#[0-9a-f]{6}$/i.test(color) ? color + alpha : color;
  }

  // Weekly bars come from the server (/api/analysis/indicators), which owns the completed-week rules. They are fetched
  // once per market, ticker and day; a reply for an earlier ticker or day is ignored.
  var weeklyData = null;
  var WEEK_LABELS = { partial: "Partial Week", final_short: "Final Short Week" };

  function weeklyKey() {
    return view.scenario.id + "|" + ui.symbol + "|" + view.day.index;
  }

  function loadWeekly(key) {
    if (weeklyData && weeklyData.key === key) return;
    weeklyData = { key: key, loading: true };
    window.Api.postAnalysis({ state: view.state, symbol: ui.symbol, timeframe: "weekly", indicators: [] })
      .then(function (env) {
        if (!regions || !view || weeklyKey() !== key) return;
        weeklyData = env.ok ? { key: key, bars: env.data.bars } : { key: key, error: env.error.message };
        refresh(["chart"]);
      });
  }

  function timeKey(t) {  // crosshair times come back as strings or {year, month, day}
    if (typeof t === "string" || !t) return t;
    return t.year + "-" + String(t.month).padStart(2, "0") + "-" + String(t.day).padStart(2, "0");
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
    var legend = el("p", "pt-chart-legend pt-tiny");
    var canvas = el("div", "pt-chart-canvas");
    canvas.setAttribute("aria-hidden", "true");  // the summary below is the text version of the chart
    var summary = el("p", "pt-small pt-chart-summary");
    box.appendChild(legend);
    box.appendChild(canvas);
    box.appendChild(summary);
    var credit = el("p", "pt-tiny muted", "Chart by ");
    var link = el("a", null, "TradingView Lightweight Charts™");
    link.href = "https://www.tradingview.com/";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    credit.appendChild(link);
    credit.appendChild(document.createTextNode(", © 2026 TradingView, Inc. Prices shown are simulated."));
    box.appendChild(credit);
    var LC = window.LightweightCharts;
    if (!LC || !marketIsCurrent()) {
      summary.textContent = LC ? "Loading simulated prices…"
        : "The chart could not load. Your prices and trades are still in the positions table and history.";
      return;
    }

    if (weeklyView && (!weeklyData || weeklyData.key !== weeklyKey() || !weeklyData.bars)) {
      var failed = weeklyData && weeklyData.key === weeklyKey() && weeklyData.error;
      summary.textContent = failed ? "Weekly prices could not load: " + weeklyData.error : "Loading weekly prices…";
      if (!failed) loadWeekly(weeklyKey());
      return;
    }
    var bars = weeklyView ? weeklyData.bars : market.bars[symbol].map(function (b, k) {
      return { time: market.dates[k], o: b.o, h: b.h, l: b.l, c: b.c, v: b.v };
    });
    var up = token("--up"), down = token("--down"), surface = token("--surface");
    chart = LC.createChart(canvas, {
      autoSize: true,
      layout: { background: { type: "solid", color: token("--surface") }, textColor: token("--muted"),
                fontFamily: token("--font-text"), attributionLogo: false },  // the credit line below links instead
      grid: { vertLines: { color: token("--surface-2") }, horzLines: { color: token("--surface-2") } },
      rightPriceScale: { borderColor: token("--border"), scaleMargins: { top: 0.08, bottom: 0.25 } },
      timeScale: { borderColor: token("--border"), rightOffset: 2, fixLeftEdge: true, maxBarSpacing: 28 },
      handleScroll: { vertTouchDrag: false },  // a vertical swipe on a phone still scrolls the page
      localization: { priceFormatter: function (p) { return "$" + p.toFixed(2); } },
    });
    var candles = chart.addSeries(LC.CandlestickSeries, { upColor: up, downColor: down, borderUpColor: up,
      borderDownColor: down, wickUpColor: up, wickDownColor: down });
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
    var lastLabel = WEEK_LABELS[bars[bars.length - 1].status];
    if (lastLabel) {
      marks.push({ time: bars[bars.length - 1].time, position: "aboveBar", shape: "circle", color: token("--muted"),
                   text: lastLabel });
    }
    marks.sort(function (a, b) { return a.time < b.time ? -1 : a.time > b.time ? 1 : 0; });
    LC.createSeriesMarkers(candles, marks);
    // a few bars fill the width from the left; a long history opens on the latest 90 bars (zoom out for the rest)
    if (bars.length > 90) chart.timeScale().setVisibleLogicalRange({ from: bars.length - 90, to: bars.length + 1 });
    else chart.timeScale().fitContent();

    var byTime = {};
    bars.forEach(function (b) { byTime[b.time] = b; });
    var last = bars[bars.length - 1];
    function readout(b) {
      legend.textContent = (weeklyView ? (WEEK_LABELS[b.status] || "Week") + " of " : "") + niceDate(b.time) + ": open " + money(b.o) + ", high "
        + money(b.h) + ", low " + money(b.l) + ", close " + money(b.c) + ", volume " + b.v.toLocaleString("en-US") + ".";
    }
    readout(last);
    chart.subscribeCrosshairMove(function (p) { readout(byTime[timeKey(p.time)] || last); });

    var high = Math.max.apply(null, bars.map(function (b) { return b.h; }));
    var low = Math.min.apply(null, bars.map(function (b) { return b.l; }));
    summary.textContent = (weeklyView ? "Weekly" : "Daily") + " simulated prices from " + niceDate(market.dates[0])
      + " to " + niceDate(view.day.date) + ": last close " + money(last.c) + ", highest " + money(high) + ", lowest "
      + money(low) + ". " + (trades ? trades + (trades === 1 ? " of your trades is" : " of your trades are")
      + " marked: B for a buy, S for a sell." : "Your trades in " + symbol + " will be marked on the chart.")
      + (lastLabel === "Partial Week" ? " The last bar is a Partial Week: this week so far, which can still change."
        : lastLabel ? " The last bar is the Final Short Week: the scenario's final " + last.days + " trading days." : "")
      + " Scroll or pinch to zoom and drag to move through time.";
  };

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
  // the chart draws on a canvas with colours read from the theme tokens, so it is redrawn when the theme changes
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { refresh(["chart"]); });
  new MutationObserver(function () { refresh(["chart"]); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  window.Paper = {
    init: function () { root = document.getElementById("paper-root"); },
    show: show,
  };
})();
