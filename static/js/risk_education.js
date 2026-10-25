// Owner: Integrator. Static risk-tolerance education panel in #risk-education. Prewritten text only: no AI, no fetch.
(function () {
  "use strict";

  var LEVELS = [
    ["low", "Low — Conservative", "Focuses on financial stability, limiting potential losses, and understanding uncertainty."],
    ["medium", "Medium — Moderate", "Balances potential growth with financial stability and the possibility of losses."],
    ["high", "High — Aggressive", "Considers growth opportunities alongside greater volatility and the possibility of larger losses."],
  ];
  var ATTRIBUTION = [
    "Based on Goldman Sachs Private Wealth Management educational materials (2025).",
    "Static educational content — not AI-generated.",
    "Not affiliated with or endorsed by Goldman Sachs.",
    "These are general portfolio concepts, not risk ratings for any particular company or personalized investment advice.",
  ];
  var SOURCES = [
    ["https://privatewealth.goldmansachs.com/semester-with-goldman-sachs-2025-session-5-slides.pdf",
      "Semester with Goldman Sachs 2025, Session 5 slides (PDF)"],
    ["https://privatewealth.goldmansachs.com/semester-with-goldman-sachs-2025-session-5-one-pager.pdf",
      "Session 5 one-pager (PDF)"],
  ];

  var root = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render() {
    var profile = window.Profile && window.Profile.get();
    var risk = profile && profile.risk;
    root.textContent = "";

    var title = el("h2", "risk-title", "Understanding risk tolerance");
    title.id = "risk-education-title";
    root.appendChild(title);

    var list = el("ul", "risk-levels");
    LEVELS.forEach(function (level) {
      var current = level[0] === risk;
      var li = el("li", "risk-level" + (current ? " is-current" : ""));
      li.dataset.risk = level[0];
      var name = el("p", "risk-name", level[1]);
      if (current) {
        li.setAttribute("aria-current", "true");
        name.appendChild(el("span", "risk-yours", "Your selection"));
      }
      li.appendChild(name);
      li.appendChild(el("p", "risk-text", level[2]));
      list.appendChild(li);
    });
    root.appendChild(list);

    var sources = el("p", "risk-sources");
    sources.appendChild(document.createTextNode("Source: "));
    SOURCES.forEach(function (src, i) {
      if (i) sources.appendChild(document.createTextNode(" · "));
      var a = el("a", null, src[1]);
      a.href = src[0];
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.appendChild(el("span", "visually-hidden", " (opens in a new tab)"));
      sources.appendChild(a);
    });
    root.appendChild(sources);

    ATTRIBUTION.forEach(function (line) { root.appendChild(el("p", "risk-note", line)); });
  }

  window.RiskEducation = {
    init: function () {
      root = document.getElementById("risk-education");
      if (!root) return;
      render();
      document.addEventListener("app:profile-changed", render);
    },
  };
})();
