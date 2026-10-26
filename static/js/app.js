// Owner: Agent B. Boot. Modules built by other agents are optional until they exist.
(function () {
  "use strict";

  window.Profile.init();
  window.Watchlist.init();
  window.Company.init();
  if (window.Chat) window.Chat.init();
  if (window.Alerts) window.Alerts.init();
  if (window.Checklist) window.Checklist.init();
  if (window.RiskEducation) window.RiskEducation.init();
  if (window.Accounts) window.Accounts.init();
  if (window.Sentiment) window.Sentiment.init();
  if (window.Lab) window.Lab.init();
  if (window.Sign) window.Sign.init();
  if (window.Brokers) window.Brokers.init();
  if (window.Paper) window.Paper.init();

  // Tabs: a real tablist. Each tab has a URL hash, so links, reloads and Back/Forward land on the same section.
  // A module's show() loads its content the first time its tab is opened.
  var VIEWS = { explore: ["explore-view", null], lab: ["lab-root", window.Lab], sign: ["sign-root", window.Sign],
    brokers: ["brokers-root", window.Brokers], paper: ["paper-root", window.Paper] };
  var HASHES = { explore: "explore", lab: "lab", sign: "sign", brokers: "brokers", paper: "practice" };
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  function tabFromHash() {
    var hash = window.location.hash.replace("#", "");
    return Object.keys(HASHES).filter(function (k) { return HASHES[k] === hash; })[0] || "explore";
  }
  function showTab(tab) {
    document.body.dataset.tab = tab;  // CSS keys tab-specific visibility (e.g. the alert toast) off this
    Object.keys(VIEWS).forEach(function (key) {
      var view = document.getElementById(VIEWS[key][0]);
      if (view) view.hidden = key !== tab;
    });
    tabs.forEach(function (b) {
      var selected = b.dataset.tab === tab;
      b.setAttribute("aria-selected", String(selected));
      b.tabIndex = selected ? 0 : -1;
    });
    var module = VIEWS[tab] && VIEWS[tab][1];
    if (module && module.show) module.show();
  }
  function choose(tab) {
    showTab(tab);
    if (tabFromHash() !== tab || !window.location.hash) history.pushState(null, "", "#" + HASHES[tab]);
  }
  tabs.forEach(function (b, i) {
    b.addEventListener("click", function () { choose(b.dataset.tab); });
    b.addEventListener("keydown", function (e) {
      var next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      var target = tabs[(next + tabs.length) % tabs.length];
      target.focus();
      choose(target.dataset.tab);
    });
  });
  window.addEventListener("popstate", function () { showTab(tabFromHash()); });
  window.addEventListener("hashchange", function () { showTab(tabFromHash()); });
  showTab(tabFromHash());

  // Learn menu: Before you buy, Learn about accounts, Sentiment. Arrow keys move, Escape closes.
  var learnButton = document.getElementById("learn-button");
  var learnMenu = document.getElementById("learn-menu");
  if (learnButton && learnMenu) {
    var items = function () {
      return Array.prototype.filter.call(learnMenu.querySelectorAll('[role="menuitem"]'), function (b) { return !b.hidden; });
    };
    var setOpen = function (open) {
      learnMenu.hidden = !open;
      learnButton.setAttribute("aria-expanded", String(open));
      if (open && items()[0]) items()[0].focus();
    };
    learnButton.addEventListener("click", function () { setOpen(learnMenu.hidden); });
    learnMenu.addEventListener("click", function (e) { if (e.target.closest('[role="menuitem"]')) setOpen(false); });
    learnMenu.addEventListener("keydown", function (e) {
      var list = items();
      var i = list.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        list[(i + (e.key === "ArrowDown" ? 1 : -1) + list.length) % list.length].focus();
      } else if (e.key === "Home" || e.key === "End") {
        e.preventDefault();
        list[e.key === "Home" ? 0 : list.length - 1].focus();
      } else if (e.key === "Escape") {
        setOpen(false);
        learnButton.focus();
      } else if (e.key === "Tab") {
        setOpen(false);
      }
    });
    document.addEventListener("click", function (e) {
      if (!learnMenu.hidden && !e.target.closest(".learn")) setOpen(false);
    });
  }

  var checklistButton = document.getElementById("checklist-open");
  if (checklistButton) {
    checklistButton.addEventListener("click", function () {
      document.dispatchEvent(new CustomEvent("app:open-checklist", { detail: {} }));
    });
  }
})();
