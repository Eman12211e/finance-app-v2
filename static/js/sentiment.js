// Owner: Integrator. Optional "Financial Sentiment Explorer" modal in #sentiment-root.
// Labels and scores come only from the server's FinBERT result; this file never invents a classification.
(function () {
  "use strict";

  var DISCLAIMER = "Sentiment describes the tone of a sentence. It is not a prediction of stock returns and not investment advice.";
  var MODEL_NOTE = "Result from the FinBERT model (ProsusAI/finbert), run on this computer.";
  var NAMES = { positive: "Positive", negative: "Negative", neutral: "Neutral" };
  var LINKS = [
    ["FinBERT model card (ProsusAI)", "https://huggingface.co/ProsusAI/finbert"],
    ["CC BY-NC-SA 4.0 license", "https://creativecommons.org/licenses/by-nc-sa/4.0/"],
  ];

  var backdrop = null;
  var dialog = null;
  var resultBox = null;
  var opener = null;
  var data = null;
  var busy = false;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function showResult(env) {
    resultBox.textContent = "";
    if (!env || !env.ok) {
      resultBox.appendChild(el("p", "sent-unavailable", env && env.error ? env.error.message : "Something went wrong. Please try again."));
      return;
    }
    var r = env.data;
    resultBox.appendChild(el("p", "sent-statement", "“" + r.text + "”"));
    if (r.inference !== "model" || !r.label) {
      resultBox.dataset.inference = "unavailable";
      resultBox.appendChild(el("p", "sent-unavailable", "Model unavailable: " + (r.reason || "no result.") + " No sentiment is shown."));
      return;
    }
    resultBox.dataset.inference = "model";
    resultBox.appendChild(el("p", "sent-label sent-" + r.label, "Sentiment: " + NAMES[r.label]));
    var list = el("ul", "sent-scores");
    ["positive", "negative", "neutral"].forEach(function (k) {
      list.appendChild(el("li", null, NAMES[k] + ": " + r.scores[k].display));
    });
    resultBox.appendChild(list);
    resultBox.appendChild(el("p", "sent-source", MODEL_NOTE));
  }

  function analyze(id, button) {
    if (busy) return;
    busy = true;
    [].forEach.call(dialog.querySelectorAll(".sent-choice"), function (b) { b.setAttribute("aria-pressed", b === button ? "true" : "false"); });
    resultBox.textContent = "";
    resultBox.appendChild(el("p", "muted", "Analyzing..."));
    window.Api.postSentiment(id).then(function (env) {
      showResult(env);
      busy = false;
    });
  }

  function build(root) {
    backdrop = el("div", "sent-backdrop");
    backdrop.hidden = true;
    dialog = el("div", "sent-dialog");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "sent-title");
    dialog.tabIndex = -1;

    var title = el("h2", "sent-title", "Financial Sentiment Explorer");
    title.id = "sent-title";
    dialog.appendChild(title);
    dialog.appendChild(el("p", null, "Pick an example statement. The FinBERT model labels its tone as positive, negative or neutral."));
    dialog.appendChild(el("p", "sent-disclaimer", DISCLAIMER));
    dialog.appendChild(el("p", "muted", data.note));

    var list = el("ul", "sent-list");
    data.statements.forEach(function (s) {
      var li = el("li");
      var b = el("button", "sent-choice", s.text);
      b.type = "button";
      b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", function () { analyze(s.id, b); });
      li.appendChild(b);
      list.appendChild(li);
    });
    dialog.appendChild(list);

    resultBox = el("div", "sent-result");
    resultBox.setAttribute("aria-live", "polite");
    dialog.appendChild(resultBox);

    var credit = el("p", "sent-credit");
    credit.appendChild(document.createTextNode("Model: FinBERT by ProsusAI (Araci, 2019). Weights licensed for non-commercial use. "));
    LINKS.forEach(function (link, i) {
      if (i) credit.appendChild(document.createTextNode(" · "));
      var a = el("a", null, link[0]);
      a.href = link[1];
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.appendChild(el("span", "visually-hidden", " (opens in a new tab)"));
      credit.appendChild(a);
    });
    dialog.appendChild(credit);

    var close = el("button", "sent-close button-secondary", "Close");
    close.type = "button";
    close.addEventListener("click", closeModal);
    dialog.appendChild(close);

    backdrop.appendChild(dialog);
    backdrop.addEventListener("click", function (e) { if (e.target === backdrop) closeModal(); });
    document.addEventListener("keydown", onKey);
    root.appendChild(backdrop);
  }

  function onKey(e) {
    if (!backdrop || backdrop.hidden) return;
    if (e.key === "Escape") {
      closeModal();
    } else if (e.key === "Tab") {
      // Keep keyboard focus inside the open dialog.
      var items = dialog.querySelectorAll("button, a[href]");
      var first = items[0];
      var last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function open() {
    var root = document.getElementById("sentiment-root");
    if (!root || !data) return;
    if (!backdrop) build(root);
    if (!backdrop.hidden) return;
    opener = document.activeElement;
    backdrop.hidden = false;
    dialog.focus();
  }

  function closeModal() {
    if (!backdrop || backdrop.hidden) return;
    backdrop.hidden = true;
    if (opener && opener.focus && document.contains(opener)) opener.focus();
  }

  window.Sentiment = {
    init: function () {
      var button = document.getElementById("sentiment-open");
      if (!button) return;
      // The button stays hidden unless the server reports the optional feature is enabled.
      window.Api.getSentimentStatements().then(function (env) {
        if (!env || !env.ok || !env.data.enabled) return;
        data = env.data;
        button.hidden = false;
        button.addEventListener("click", open);
      });
    },
    open: open,
  };
})();
