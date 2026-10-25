// Owner: Agent D. Simulated alerts: bell + dropdown in #alerts-root, one toast per page load.
(function () {
  "use strict";

  var READ_KEY = "fe_alerts_read";
  var SVG = "http://www.w3.org/2000/svg";
  var alerts = [];
  var loaded = false;
  var failed = false;
  var toastShown = false;
  var els = {};

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function loadRead() {
    try {
      var stored = JSON.parse(localStorage.getItem(READ_KEY));
      return Array.isArray(stored) ? stored : [];
    } catch (e) {
      return [];
    }
  }

  var read = loadRead();

  function saveRead() {
    try {
      localStorage.setItem(READ_KEY, JSON.stringify(read));
    } catch (e) { /* storage unavailable: read state lasts for this page only */ }
  }

  function unread() {
    return alerts.filter(function (a) { return read.indexOf(a.id) === -1; });
  }

  function bellIcon() {
    var svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "20");
    svg.setAttribute("height", "20");
    svg.setAttribute("aria-hidden", "true");
    var path = document.createElementNS(SVG, "path");
    path.setAttribute("d", "M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6V11a6 6 0 0 0-5-5.9V4a1 1 0 0 0-2 0v1.1A6 6 0 0 0 6 11v5l-2 2v1h16v-1z");
    path.setAttribute("fill", "currentColor");
    svg.appendChild(path);
    return svg;
  }

  function tag(text) {
    return el("span", "fe-label", text);
  }

  function renderBadge() {
    var count = unread().length;
    els.badge.textContent = String(count);
    els.badge.hidden = count === 0;
    els.bell.setAttribute("aria-label", count ? "Alerts, " + count + " unread" : "Alerts");
  }

  function renderPanel() {
    els.list.textContent = "";
    if (failed) {
      els.list.appendChild(el("p", "fe-empty", "Alerts are not available right now."));
      return;
    }
    if (!alerts.length) {
      els.list.appendChild(el("p", "fe-empty", "No alerts for your watchlist."));
      return;
    }
    alerts.forEach(function (a) {
      var item = el("article", "fe-alert");
      item.appendChild(tag(a.label));
      item.appendChild(el("h3", "fe-alert-title", a.title));
      item.appendChild(el("p", "fe-alert-body", a.body));
      els.list.appendChild(item);
    });
  }

  function placePanel() {
    // Fixed position from the bell's rect so the panel never overflows a narrow screen.
    var r = els.bell.getBoundingClientRect();
    var width = Math.min(360, window.innerWidth - 24);
    var left = Math.min(Math.max(12, r.right - width), window.innerWidth - width - 12);
    els.panel.style.top = r.bottom + 8 + "px";
    els.panel.style.left = left + "px";
    els.panel.style.width = width + "px";
  }

  function isOpen() {
    return !els.panel.hidden;
  }

  function openPanel() {
    renderPanel();
    els.panel.hidden = false;
    els.bell.setAttribute("aria-expanded", "true");
    placePanel();
    alerts.forEach(function (a) { if (read.indexOf(a.id) === -1) read.push(a.id); });
    saveRead();
    renderBadge();
  }

  function closePanel() {
    els.panel.hidden = true;
    els.bell.setAttribute("aria-expanded", "false");
  }

  function showToast() {
    var fresh = unread();
    if (toastShown || !fresh.length) return;
    toastShown = true;
    var a = fresh[0]; // alerts arrive newest first
    var toast = el("div", "fe-toast");
    toast.setAttribute("role", "status");
    toast.appendChild(tag(a.label));
    toast.appendChild(el("p", "fe-toast-title", a.title));
    toast.appendChild(el("p", "fe-toast-body", a.body));
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 6000);
  }

  function fetchAlerts(tickers) {
    if (!tickers || !tickers.length) {
      alerts = [];
      failed = false;
      renderBadge();
      if (isOpen()) renderPanel();
      return;
    }
    window.Api.getAlerts(tickers).then(function (env) {
      failed = !env || !env.ok;
      alerts = failed ? [] : env.data.alerts || [];
      renderBadge();
      if (isOpen()) renderPanel();
      if (!loaded) {
        loaded = true;
        showToast();
      }
    });
  }

  function build(root) {
    els.bell = el("button", "fe-bell");
    els.bell.type = "button";
    els.bell.setAttribute("aria-expanded", "false");
    els.bell.setAttribute("aria-controls", "fe-alerts-panel");
    els.bell.appendChild(bellIcon());
    els.badge = el("span", "fe-badge");
    els.badge.hidden = true;
    els.bell.appendChild(els.badge);

    els.panel = el("div", "fe-panel");
    els.panel.id = "fe-alerts-panel";
    els.panel.hidden = true;
    els.panel.setAttribute("role", "region");
    els.panel.setAttribute("aria-label", "Alerts");
    els.panel.appendChild(el("h2", "fe-panel-title", "Alerts"));
    els.list = el("div", "fe-list");
    els.panel.appendChild(els.list);

    root.appendChild(els.bell);
    root.appendChild(els.panel);

    els.bell.addEventListener("click", function () { if (isOpen()) closePanel(); else openPanel(); });
    document.addEventListener("click", function (e) {
      if (isOpen() && !root.contains(e.target)) closePanel();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen()) {
        closePanel();
        els.bell.focus();
      }
    });
    window.addEventListener("resize", function () { if (isOpen()) placePanel(); });
  }

  window.Alerts = {
    init: function () {
      var root = document.getElementById("alerts-root");
      if (!root) return;
      build(root);
      renderBadge();
      document.addEventListener("app:watchlist-changed", function (e) {
        fetchAlerts(e.detail && e.detail.tickers);
      });
      fetchAlerts(window.Watchlist ? window.Watchlist.get() : []);
    },
  };
})();
