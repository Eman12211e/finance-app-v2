// Understand Before You Sign tab in #sign-root. Static, human-written guides from /api/documents.
// No AI and no personal data: the only inputs are filter buttons and checklist checkboxes, kept in memory only.
(function () {
  "use strict";

  var root = null;
  var list = null;
  var view = null;
  var checklistBox = null;
  var cache = {};
  var currentId = null;
  var filter = "all";
  var picked = {};  // question text -> document title; lives only in this page, never saved or sent

  var ORIGINS = {
    official: ["Official text", "Exact wording from a government source."],
    firm: ["Firm disclosure", "A real firm's own words, quoted briefly. Not a requirement for every firm."],
    summary: ["Summary", "Our plain summary of an official source. Read the original for exact wording."],
    example: ["Fictional example", "Written for this app. Not from any real firm or agreement."],
  };
  var TAGS = [["all", "All"], ["fees", "Fees"], ["risks", "Risks"], ["rights", "Your rights"],
    ["disclosures", "Disclosures"], ["personal_information", "Personal information"]];

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function link(href, text) {
    var a = el("a", null, text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.appendChild(el("span", "visually-hidden", " (opens in a new tab)"));
    return a;
  }

  function bullets(items) {
    var ul = el("ul", "sign-list");
    items.forEach(function (t) { ul.appendChild(el("li", null, t)); });
    return ul;
  }

  function block(title, body) {
    var div = el("div", "sign-block");
    div.appendChild(el("h4", null, title));
    div.appendChild(typeof body === "string" ? el("p", null, body) : body);
    return div;
  }

  // ---- checklist (in memory only) ----

  function renderChecklist() {
    checklistBox.textContent = "";
    var title = el("h3", null, "Questions to bring");
    title.id = "sign-checklist-title";
    checklistBox.appendChild(title);
    checklistBox.appendChild(el("p", "sign-small muted", "Tick questions in any guide to add them here. "
      + "Nothing you select is saved or sent. It disappears when you leave or reload the page."));
    var questions = Object.keys(picked);
    if (!questions.length) {
      checklistBox.appendChild(el("p", "muted", "No questions selected yet."));
      return;
    }
    var byDoc = {};
    questions.forEach(function (q) { (byDoc[picked[q]] = byDoc[picked[q]] || []).push(q); });
    Object.keys(byDoc).forEach(function (docTitle) {
      checklistBox.appendChild(el("h4", null, docTitle));
      var ol = el("ul", "sign-checklist-items");
      byDoc[docTitle].forEach(function (q) { ol.appendChild(el("li", null, q)); });
      checklistBox.appendChild(ol);
    });
    var actions = el("div", "sign-checklist-actions");
    var print = el("button", "button-primary", "Print checklist");
    print.type = "button";
    print.addEventListener("click", function () {
      document.body.classList.add("print-checklist");
      window.print();
    });
    var clear = el("button", "button-secondary", "Clear");
    clear.type = "button";
    clear.addEventListener("click", function () {
      picked = {};
      document.querySelectorAll(".sign-question input").forEach(function (box) { box.checked = false; });
      renderChecklist();
    });
    actions.appendChild(print);
    actions.appendChild(clear);
    checklistBox.appendChild(actions);
    checklistBox.appendChild(el("p", "sign-print-note", "From Money Basics, an education app. Not legal, tax or "
      + "investment advice."));
  }

  function questionItem(q, docTitle) {
    var li = el("li", "sign-question");
    var label = el("label");
    var box = el("input");
    box.type = "checkbox";
    box.checked = Object.prototype.hasOwnProperty.call(picked, q);
    box.addEventListener("change", function () {
      if (box.checked) picked[q] = docTitle; else delete picked[q];
      renderChecklist();
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(" " + q));
    li.appendChild(label);
    return li;
  }

  // ---- one document ----

  function renderSection(doc, s) {
    var row = el("article", "sign-row card");
    row.dataset.tags = s.tags.join(" ");
    row.setAttribute("aria-label", s.heading);
    row.appendChild(el("h3", "sign-heading", s.heading));

    var original = el("div", "sign-original sign-origin-" + s.origin);
    var badge = el("p", "sign-origin-badge", ORIGINS[s.origin][0]);
    original.appendChild(badge);
    original.appendChild(el("p", "sign-small muted", ORIGINS[s.origin][1]));
    original.appendChild(el("blockquote", "sign-passage", s.passage));
    var src = doc.sources[s.source];
    var cite = el("p", "sign-small sign-cite", s.location + " · " + src.publisher + ", " + src.version + " · retrieved "
      + src.retrieved_on + " ");
    if (src.url) cite.appendChild(link(src.url, "Open source"));
    original.appendChild(cite);
    row.appendChild(original);

    var explain = el("div", "sign-explain");
    explain.appendChild(block("In plain English", s.plain_english));
    explain.appendChild(block("Why it matters", s.why_it_matters));
    explain.appendChild(block("What to look for", bullets(s.look_for)));
    var qs = el("ul", "sign-questions");
    s.questions.forEach(function (q) { qs.appendChild(questionItem(q, doc.title)); });
    explain.appendChild(block("Questions to ask the firm", qs));
    var tags = el("p", "sign-tags");
    s.tags.forEach(function (t) {
      var name = TAGS.filter(function (x) { return x[0] === t; })[0];
      tags.appendChild(el("span", "sign-tag", name ? name[1] : t));
    });
    explain.appendChild(tags);
    if (s.accounts_101 && window.Accounts && window.Accounts.open) {
      var more = el("button", "button-secondary sign-accounts", "Learn about " + s.accounts_101 + " in Accounts 101");
      more.type = "button";
      more.addEventListener("click", function () { window.Accounts.open(s.accounts_101); });
      explain.appendChild(more);
    }
    row.appendChild(explain);
    return row;
  }

  function applyFilter() {
    view.querySelectorAll(".sign-row").forEach(function (row) {
      row.hidden = filter !== "all" && row.dataset.tags.split(" ").indexOf(filter) < 0;
    });
    view.querySelectorAll(".sign-filter").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.tag === filter));
    });
  }

  function renderDocument(doc) {
    view.textContent = "";
    var head = el("div", "card sign-doc-head");
    head.appendChild(el("h3", null, doc.title));
    head.appendChild(el("p", null, doc.summary));
    head.appendChild(el("p", "muted", "When you usually see it: " + doc.when_you_see_it));
    var sources = el("ul", "sign-sources");
    Object.keys(doc.sources).forEach(function (key) {
      var src = doc.sources[key];
      var li = el("li", null, src.publisher + ": " + src.title + " (" + src.version + ", retrieved " + src.retrieved_on + ") ");
      if (src.url) li.appendChild(link(src.url, "Open"));
      sources.appendChild(li);
    });
    head.appendChild(block("Sources", sources));

    var filters = el("div", "sign-filters");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "Show passages about");
    TAGS.forEach(function (t) {
      var b = el("button", "sign-filter", t[1]);
      b.type = "button";
      b.dataset.tag = t[0];
      b.addEventListener("click", function () { filter = t[0]; applyFilter(); });
      filters.appendChild(b);
    });
    head.appendChild(filters);
    view.appendChild(head);

    doc.sections.forEach(function (s) { view.appendChild(renderSection(doc, s)); });
    applyFilter();
  }

  function openDocument(id) {
    currentId = id;
    filter = "all";
    list.querySelectorAll("button").forEach(function (b) {
      b.setAttribute("aria-current", b.dataset.id === id ? "true" : "false");
    });
    if (cache[id]) {
      renderDocument(cache[id]);
      return;
    }
    view.textContent = "";
    view.appendChild(el("p", "muted", "Loading…"));
    window.Api.getDocument(id).then(function (env) {
      if (currentId !== id) return;
      view.textContent = "";
      if (!env.ok) {
        view.appendChild(el("p", "error-text", env.error.message));
        return;
      }
      cache[id] = env.data;
      renderDocument(env.data);
    });
  }

  // ---- layout ----

  function renderShell(docs) {
    root.textContent = "";
    var top = el("div", "sign-top");
    var intro = el("div", "card sign-intro");
    var title = el("h2", null, "Understand Before You Sign");
    title.id = "sign-title";
    intro.appendChild(title);
    intro.appendChild(el("p", "sign-lead", "Before opening an investment account, understand the documents you're "
      + "agreeing to, the risks involved, and the rights you may be giving up."));
    intro.appendChild(el("p", null, "New to investing? Start with any document below. Each one shows what it says, "
      + "what it means in plain English, and questions you can tick to build a list to bring to a firm."));
    var legend = el("ul", "sign-legend");
    Object.keys(ORIGINS).forEach(function (key) {
      var li = el("li", "sign-origin-" + key);
      li.appendChild(el("strong", null, ORIGINS[key][0] + ": "));
      li.appendChild(document.createTextNode(ORIGINS[key][1]));
      legend.appendChild(li);
    });
    intro.appendChild(legend);
    top.appendChild(intro);

    var safety = el("aside", "card sign-safety");
    safety.setAttribute("aria-labelledby", "sign-safety-title");
    var safetyTitle = el("h3", null, "Your Safety Comes First");
    safetyTitle.id = "sign-safety-title";
    safety.appendChild(safetyTitle);
    safety.appendChild(el("p", null, "Before signing any financial document, take time to understand its terms, fees, "
      + "potential risks, and your rights. Always verify that you're dealing with a legitimate financial institution "
      + "and review any agreement carefully before providing personal information or signing."));
    safety.appendChild(el("p", "sign-privacy",
      "Never enter your Social Security number, identification documents, or account passwords into this educational guide."));
    safety.appendChild(el("p", "sign-small sign-disclaimer", "Educational information only. Not legal, tax, or investment advice."));
    top.appendChild(safety);
    root.appendChild(top);

    var layout = el("div", "sign-layout");
    var nav = el("nav", "sign-nav card");
    nav.setAttribute("aria-label", "Documents");
    list = el("ul", "sign-doc-list");
    docs.forEach(function (d) {
      var li = el("li");
      var b = el("button", "sign-doc-button");
      b.type = "button";
      b.dataset.id = d.id;
      b.appendChild(el("span", "sign-doc-title", d.title));
      b.appendChild(el("span", "sign-doc-blurb", d.card_blurb));
      b.appendChild(el("span", "sign-small muted", d.origins.map(function (o) { return ORIGINS[o][0]; }).join(" · ")));
      b.addEventListener("click", function () { openDocument(d.id); });
      li.appendChild(b);
      list.appendChild(li);
    });
    nav.appendChild(list);
    layout.appendChild(nav);
    view = el("div", "sign-view");
    layout.appendChild(view);
    checklistBox = el("aside", "sign-checklist card");
    checklistBox.id = "sign-checklist";
    checklistBox.setAttribute("aria-labelledby", "sign-checklist-title");
    layout.appendChild(checklistBox);
    root.appendChild(layout);
    renderChecklist();
    openDocument(docs[0].id);
  }

  function show() {
    if (!root || list) return;
    root.textContent = "";
    root.appendChild(el("p", "muted", "Loading the guides…"));
    window.Api.getDocuments().then(function (env) {
      if (!env.ok) {
        root.textContent = "";
        root.appendChild(el("p", "error-text", env.error.message));
        return;
      }
      renderShell(env.data.documents);
    });
  }

  window.Sign = {
    init: function () {
      root = document.getElementById("sign-root");
      window.addEventListener("afterprint", function () { document.body.classList.remove("print-checklist"); });
    },
    show: show,
  };
})();
