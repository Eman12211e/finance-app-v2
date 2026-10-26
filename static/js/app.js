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

  // Tabs: each view is a section; a module's show() loads its content the first time it is opened.
  var VIEWS = { explore: ["explore-view", null], lab: ["lab-root", window.Lab], sign: ["sign-root", window.Sign],
    brokers: ["brokers-root", window.Brokers], paper: ["paper-root", window.Paper] };
  function showTab(tab) {
    document.body.dataset.tab = tab;  // CSS keys tab-specific visibility (e.g. the alert toast) off this
    Object.keys(VIEWS).forEach(function (key) {
      var view = document.getElementById(VIEWS[key][0]);
      if (view) view.hidden = key !== tab;
    });
    document.querySelectorAll(".tab").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.tab === tab));
    });
    var module = VIEWS[tab] && VIEWS[tab][1];
    if (module && module.show) module.show();
  }
  document.querySelectorAll(".tab").forEach(function (b) {
    b.addEventListener("click", function () { showTab(b.dataset.tab); });
  });

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
