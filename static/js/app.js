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

  var checklistButton = document.getElementById("checklist-open");
  if (checklistButton) {
    checklistButton.addEventListener("click", function () {
      document.dispatchEvent(new CustomEvent("app:open-checklist", { detail: {} }));
    });
  }
})();
