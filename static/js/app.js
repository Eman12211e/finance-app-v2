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

  var checklistButton = document.getElementById("checklist-open");
  if (checklistButton) {
    checklistButton.addEventListener("click", function () {
      document.dispatchEvent(new CustomEvent("app:open-checklist", { detail: {} }));
    });
  }
})();
