// Owner: Agent D. Pre-purchase checklist modal in #checklist-root. Questions only: no scoring, no advice.
(function () {
  "use strict";

  var TITLE = "Before you buy: questions to ask yourself";
  var QUESTIONS = [
    "Do I understand what this company or fund does?",
    "Did I read its latest earnings results?",
    "Do I have emergency savings first?",
    "Can I accept losing some of this money?",
    "Does this add to or reduce my diversification?",
    "How long do I plan to hold it?",
    "Did I check the fees (for ETFs)?",
  ];
  var NOTE = "These questions help you think. They are not advice.";

  var backdrop = null;
  var opener = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function close() {
    if (!backdrop || backdrop.hidden) return;
    backdrop.hidden = true;
    if (opener && opener.focus && document.contains(opener)) opener.focus();
  }

  function build(root) {
    backdrop = el("div", "fe-backdrop");
    backdrop.hidden = true;
    var dialog = el("div", "fe-dialog");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "fe-checklist-title");
    dialog.tabIndex = -1;

    var title = el("h2", "fe-dialog-title", TITLE);
    title.id = "fe-checklist-title";
    dialog.appendChild(title);

    var list = el("ul", "fe-checklist");
    QUESTIONS.forEach(function (q, i) {
      var li = el("li");
      var label = el("label");
      var box = el("input");
      box.type = "checkbox";
      box.id = "fe-check-" + i;
      label.htmlFor = box.id;
      label.textContent = q;
      li.appendChild(box);
      li.appendChild(label);
      list.appendChild(li);
    });
    dialog.appendChild(list);
    dialog.appendChild(el("p", "fe-note", NOTE));

    var closeBtn = el("button", "fe-close", "Close");
    closeBtn.type = "button";
    closeBtn.addEventListener("click", close);
    dialog.appendChild(closeBtn);

    backdrop.appendChild(dialog);
    backdrop.addEventListener("click", function (e) { if (e.target === backdrop) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
    root.appendChild(backdrop);
  }

  function open() {
    var root = document.getElementById("checklist-root");
    if (!root) return;
    if (!backdrop) build(root);
    if (!backdrop.hidden) return;
    opener = document.activeElement;
    backdrop.hidden = false;
    backdrop.querySelector(".fe-dialog").focus();
  }

  window.Checklist = {
    init: function () {
      document.addEventListener("app:open-checklist", open);
    },
    open: open,
  };
})();
