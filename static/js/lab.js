// AI Strategy Comparison Lab tab in #lab-root. Renders the server's checked output only; never scores or ranks models.
(function () {
  "use strict";

  var root = null;
  var config = null;
  var results = null;

  var ISSUE_TEXT = {
    unsupported: "No valid citation",
    unknown_citation: "Cites missing evidence",
    number_not_in_evidence: "Number not in evidence",
    advice_language: "Advice withheld",
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function list(items, render, emptyText) {
    if (!items || !items.length) return el("p", "muted", emptyText || "None.");
    var ul = el("ul", "lab-list");
    items.forEach(function (item) { ul.appendChild(render(item)); });
    return ul;
  }

  function section(title, body) {
    var s = el("section", "lab-section");
    s.appendChild(el("h4", null, title));
    s.appendChild(body);
    return s;
  }

  function simulatedBadge(label) {
    return el("p", "lab-simulated-badge", label);
  }

  function citedItem(item) {
    var li = el("li", item.issues && item.issues.length ? "has-issue" : null);
    li.appendChild(el("span", null, item.text + " "));
    (item.evidence_ids || []).forEach(function (id) { li.appendChild(el("span", "lab-chip", id)); });
    if (item.stance) li.appendChild(el("span", "lab-stance", item.stance));
    (item.issues || []).forEach(function (issue) {
      li.appendChild(el("span", "lab-issue", ISSUE_TEXT[issue] || issue));
    });
    return li;
  }

  function ratio(check) {
    return check ? check.passed + " of " + check.total : "Not checked";
  }

  function checksList(panel) {
    var c = panel.checks;
    var rows = [
      ["Output format", c.schema_valid ? "Valid" : "Invalid"],
      ["Citations point to real evidence", ratio(c.citations_valid)],
      ["Numbers found in cited evidence", ratio(c.numbers_traceable)],
      ["Advice or prediction language", String(c.advice_violations)],
      ["Claims without a citation", String(c.unsupported_claims)],
      ["Names what the evidence does not show", c.states_uncertainty ? "Yes" : "No"],
      ["Latency", panel.simulated ? "Not measured (simulated)" : panel.latency_ms + " ms"],
      ["Cost", panel.simulated ? "$0 (simulated)" : "$" + panel.cost_usd],
    ];
    var dl = el("dl", "lab-checks");
    rows.forEach(function (r) {
      dl.appendChild(el("dt", null, r[0]));
      dl.appendChild(el("dd", null, r[1]));
    });
    var wrap = el("div");
    wrap.appendChild(dl);
    wrap.appendChild(el("p", "lab-small muted", panel.simulated
      ? "These checks ran on simulated text. They test the app's validators, not the model. Not a score."
      : "Automatic checks from one run. Not a benchmark or a ranking."));
    return wrap;
  }

  function renderPanel(p) {
    var card = el("article", "lab-panel card");
    card.setAttribute("aria-label", p.model.label + (p.simulated ? " (simulated)" : ""));
    if (p.simulated) card.appendChild(simulatedBadge(p.simulated_label));
    card.appendChild(el("h3", "lab-model", p.model.label));
    card.appendChild(el("p", "lab-small muted", p.model.model_id + " · " + p.model.provider + " · " + p.model.status));
    if (p.test_case) card.appendChild(el("p", "lab-small", "Simulated test case: " + p.test_case));
    if (p.status !== "ok") {
      card.appendChild(el("p", "error-text", p.status === "unavailable"
        ? (p.error || "This model is unavailable.") : "The output could not be read, so nothing from it is shown."));
    }
    if (p.truncated) card.appendChild(el("p", "error-text", "The output was cut off at the token limit."));

    card.appendChild(section("Analysis and reasoning", el("p", null, p.analysis || "No analysis.")));
    card.appendChild(section("Evidence and citations", list(p.claims, citedItem)));
    card.appendChild(section("Risk factors", list(p.risks, citedItem)));
    card.appendChild(section("Assumptions and uncertainty",
      list((p.assumptions || []).map(function (t) { return "Assumption: " + t; })
        .concat((p.uncertainties || []).map(function (t) { return "Uncertainty: " + t; })),
      function (t) { return el("li", null, t); })));
    card.appendChild(section("Unsupported claims", list(p.unsupported_claims, function (t) { return el("li", null, t); })));
    card.appendChild(section("Rule violations", list(p.violations, function (v) { return el("li", null, v.detail); })));
    card.appendChild(section("Model disagreements", list(p.disagreements, function (d) {
      return el("li", null, d.evidence_id + " " + d.label + ": supports — " + d.supports.join(", ")
        + "; weakens — " + d.weakens.join(", "));
    }, "No opposite stances on shared evidence.")));
    card.appendChild(section("Evaluation criteria", checksList(p)));
    return card;
  }

  function renderResults(data) {
    results.textContent = "";
    if (data.mode === "simulated") {
      var banner = el("div", "lab-simulated-banner");
      banner.setAttribute("role", "note");
      banner.appendChild(el("p", "lab-simulated-title", data.simulated_label));
      banner.appendChild(el("p", null, data.notice));
      results.appendChild(banner);
    }

    var ev = data.evidence;
    var evCard = el("section", "card lab-evidence");
    evCard.appendChild(el("h3", null, "Evidence given to every model: " + (ev.name || ev.ticker)));
    evCard.appendChild(el("p", "lab-small muted", "Scenario: " + data.scenario.label + " — " + data.scenario.focus));
    evCard.appendChild(el("p", "lab-small muted", "Source: " + ev.source + " data · as of " + ev.as_of
      + (ev.period_label ? " · " + ev.period_label : "")));
    var ol = el("ul", "lab-evidence-list");
    ev.items.forEach(function (e) { ol.appendChild(el("li", null, e.id + "  " + e.label + ": " + e.value)); });
    evCard.appendChild(ol);
    if (ev.not_available.length) {
      evCard.appendChild(el("p", "lab-small muted", "Not in the evidence: " + ev.not_available.join(", ") + "."));
    }
    evCard.appendChild(el("p", "lab-small muted", "Identical prompt for all " + data.panels.length
      + " models · SHA-256 " + data.prompt_sha256.slice(0, 16) + "…"));
    results.appendChild(evCard);

    var grid = el("div", "lab-grid");
    data.panels.forEach(function (p) { grid.appendChild(renderPanel(p)); });
    results.appendChild(grid);

    var summary = el("section", "card lab-summary");
    summary.appendChild(el("h3", null, "Across models"));
    var unused = data.coverage.filter(function (c) { return !c.cited_by.length; });
    summary.appendChild(el("p", null, "Opposite stances on shared evidence: " + data.disagreements.length + "."));
    summary.appendChild(el("p", null, "Evidence no model cited: "
      + (unused.length ? unused.map(function (c) { return c.evidence_id + " " + c.label; }).join(", ") : "none") + "."));
    var notScored = data.criteria.filter(function (c) { return c.how.indexOf("auto") !== 0; });
    summary.appendChild(el("p", "muted", "Not scored here: "
      + notScored.map(function (c) { return c.name.toLowerCase(); }).join(", ")
      + ". These need a reproducible benchmark with human raters."));
    summary.appendChild(el("p", "lab-small muted", "If live inference is activated later, this comparison would cost at most $"
      + data.estimated_live_max_cost_usd + " at the listed prices. No live call was made."));
    results.appendChild(summary);
  }

  function run(form, button) {
    var scenario = form.querySelector('input[name="lab-scenario"]:checked');
    button.disabled = true;
    results.textContent = "";
    results.appendChild(el("p", "muted", "Running the simulated comparison…"));
    window.Api.postLabCompare({ ticker: form.querySelector("select").value, scenario: scenario.value })
      .then(function (env) {
        button.disabled = false;
        if (!env.ok) {
          results.textContent = "";
          results.appendChild(el("p", "error-text", env.error.message));
          return;
        }
        renderResults(env.data);
      });
  }

  function renderControls() {
    root.textContent = "";
    var head = el("div", "card lab-intro");
    var title = el("h2", null, "AI Strategy Comparison Lab");
    title.id = "lab-title";
    head.appendChild(title);
    head.appendChild(el("p", null, "Compare how six AI models read the same financial evidence under the same "
      + "scenario. Check their citations, numbers and reasoning yourself. Model output is opinion, not verified fact, "
      + "and nothing here is advice."));
    head.appendChild(el("p", "lab-status", config.live_available
      ? "Live inference is available."
      : "Simulated only: live AI inference is off (zero-cost development mode). Panels use deterministic stand-ins."));

    var form = el("form", "lab-form");
    var tickerLabel = el("label", "field", "Company or fund ");
    var select = el("select");
    config.tickers.forEach(function (t) { var o = el("option", null, t); o.value = t; select.appendChild(o); });
    tickerLabel.appendChild(select);
    form.appendChild(tickerLabel);

    var fs = el("fieldset", "lab-scenarios");
    fs.appendChild(el("legend", null, "Scenario"));
    config.scenarios.forEach(function (s, i) {
      var label = el("label", "lab-scenario");
      var input = el("input");
      input.type = "radio";
      input.name = "lab-scenario";
      input.value = s.key;
      input.checked = i === 1;
      label.appendChild(input);
      label.appendChild(el("strong", null, " " + s.label + " "));
      label.appendChild(el("span", "muted", s.focus));
      fs.appendChild(label);
    });
    form.appendChild(fs);

    var button = el("button", "button-primary", "Run simulated comparison");
    button.type = "submit";
    form.appendChild(button);
    form.addEventListener("submit", function (e) { e.preventDefault(); run(form, button); });
    head.appendChild(form);
    head.appendChild(el("p", "lab-small muted", "Model list verified " + config.registry_verified_on
      + ". " + config.registry_verification));
    root.appendChild(head);

    results = el("div", "lab-results");
    results.setAttribute("aria-live", "polite");
    root.appendChild(results);
  }

  function show(tab) {
    var explore = document.getElementById("explore-view");
    explore.hidden = tab !== "explore";
    root.hidden = tab !== "lab";
    document.querySelectorAll(".tab").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.tab === tab));
    });
    if (tab === "lab" && !config) {
      root.textContent = "";
      root.appendChild(el("p", "muted", "Loading the Lab…"));
      window.Api.getLabConfig().then(function (env) {
        if (!env.ok) {
          root.textContent = "";
          root.appendChild(el("p", "error-text", env.error.message));
          return;
        }
        config = env.data;
        renderControls();
      });
    }
  }

  window.Lab = {
    init: function () {
      root = document.getElementById("lab-root");
      if (!root) return;
      document.querySelectorAll(".tab").forEach(function (b) {
        b.addEventListener("click", function () { show(b.dataset.tab); });
      });
    },
  };
})();
