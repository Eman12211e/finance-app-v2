// Owner: Integrator. "Brokerage & Investing Accounts 101" modal in #accounts-root.
// Prewritten education only: no AI, no fetch, no tax limits or other figures, no recommendations.
(function () {
  "use strict";

  var SOURCES = {
    inv_cash: ["Investor.gov: Cash account", "https://www.investor.gov/introduction-investing/investing-basics/glossary/cash-account"],
    inv_margin: ["Investor.gov: Margin account", "https://www.investor.gov/introduction-investing/investing-basics/glossary/margin-account"],
    inv_brokers: ["Investor.gov: Brokers", "https://www.investor.gov/introduction-investing/getting-started/working-investment-professional/brokers"],
    inv_529: ["Investor.gov: 529 plans", "https://www.investor.gov/introduction-investing/investing-basics/glossary/529-plans"],
    finra_brokerage: ["FINRA: Brokerage accounts", "https://www.finra.org/investors/investing/investment-accounts/brokerage-accounts"],
    finra_cash: ["FINRA: Cash accounts", "https://www.finra.org/investors/investing/investment-accounts/brokerage-accounts/cash-accounts"],
    finra_margin: ["FINRA: Margin accounts", "https://www.finra.org/investors/investing/investment-accounts/brokerage-accounts/margin-accounts"],
    finra_accounts: ["FINRA: Investment accounts", "https://www.finra.org/investors/investing/investment-accounts"],
    irs_iras: ["IRS: IRAs", "https://www.irs.gov/retirement-plans/individual-retirement-arrangements-iras"],
    irs_traditional: ["IRS: Traditional IRAs", "https://www.irs.gov/retirement-plans/traditional-iras"],
    irs_roth: ["IRS: Roth IRAs", "https://www.irs.gov/retirement-plans/roth-iras"],
    irs_sep: ["IRS: SEP plans", "https://www.irs.gov/retirement-plans/plan-sponsor/simplified-employee-pension-plan-sep"],
    irs_simple: ["IRS: SIMPLE IRA plans", "https://www.irs.gov/retirement-plans/plan-sponsor/simple-ira-plan"],
    irs_kiddie: ["IRS: Kiddie tax (Topic 553)", "https://www.irs.gov/taxtopics/tc553"],
    irs_p970: ["IRS: Tax benefits for education (Publication 970)", "https://www.irs.gov/publications/p970"],
    irs_529qa: ["IRS: 529 plans questions and answers", "https://www.irs.gov/newsroom/529-plans-questions-and-answers"],
    irs_p969: ["IRS: Health savings accounts (Publication 969)", "https://www.irs.gov/publications/p969"],
  };

  // [name, how it works, typical use, watch out for, source keys]
  var CATEGORIES = [
    ["Everyday brokerage", [
      ["Individual taxable brokerage",
        "One person owns the account and decides what to buy and sell. It has no special tax treatment.",
        "General investing for goals without a set date. Money can usually be added or taken out at any time.",
        "Dividends, interest and gains from selling are generally taxable in the year they happen. Investments can lose value.",
        ["finra_brokerage", "inv_brokers"]],
      ["Joint taxable brokerage",
        "Two or more people own the account together. Depending on the account agreement, each owner may be able to trade or withdraw.",
        "Couples or family members who invest shared money.",
        "The type of joint ownership affects what happens to the account if an owner dies. Taxes work like an individual taxable account.",
        ["finra_brokerage"]],
      ["Cash brokerage",
        "You pay the full price of each purchase with money in the account. You do not borrow from the firm.",
        "Investors who want to invest only money they already have, so losses cannot exceed what they put in.",
        "Purchases must be paid for by the settlement date. Selling a security before paying for it can lead to trading restrictions.",
        ["inv_cash", "finra_cash"]],
      ["Margin brokerage",
        "The firm lends you money to buy investments. The securities in the account are collateral for the loan.",
        "Experienced investors who understand borrowing and its costs.",
        "You pay interest and can lose more than you put in. If the account value falls, the firm can demand more money or sell your securities without asking first.",
        ["inv_margin", "finra_margin"]],
    ]],
    ["Family and estate", [
      ["Custodial UGMA/UTMA",
        "An adult manages the account for a minor under state UGMA or UTMA law. The assets legally belong to the child.",
        "Gifts or savings for a child.",
        "Gifts cannot be taken back. The child takes control at an age set by state law. Part of a child's investment income may be taxed at the parent's rate (the kiddie tax).",
        ["finra_brokerage", "irs_kiddie"]],
      ["Trust brokerage",
        "A trust owns the account. A trustee manages it under the rules in the trust document, for the trust's beneficiaries.",
        "Estate planning, such as passing assets to heirs or managing money for someone else.",
        "Opening one usually requires the trust document. Tax and legal rules depend on the type of trust, so people often get help from an attorney.",
        ["finra_accounts"]],
    ]],
    ["Retirement", [
      ["Traditional IRA",
        "An individual retirement account where investments grow tax-deferred. Contributions may be tax-deductible, depending on income and workplace plan coverage.",
        "Saving for retirement, often alongside a workplace plan.",
        "Withdrawals are generally taxed as income. Early withdrawals can owe an additional tax unless an exception applies, and withdrawals are required later in life.",
        ["irs_traditional", "irs_iras"]],
      ["Roth IRA",
        "Contributions are made with money that was already taxed. Qualified withdrawals, including earnings, are tax-free.",
        "Retirement savers who prefer to pay tax now instead of later.",
        "Whether you can contribute depends on your income. Taking out earnings early, or before a holding-period rule is met, can mean tax and an additional tax.",
        ["irs_roth", "irs_iras"]],
      ["SEP IRA",
        "An employer, including a self-employed person, contributes to IRAs set up for each eligible employee.",
        "Self-employed people and small businesses that want a simple retirement plan.",
        "Contributions come from the employer, not from employee paychecks. The employer generally must contribute the same percentage of pay for every eligible employee.",
        ["irs_sep"]],
      ["SIMPLE IRA",
        "A retirement plan for small employers. Employees can save from their paychecks, and the employer must add a matching or fixed contribution.",
        "Small businesses that want a workplace plan with less paperwork.",
        "Withdrawals during the first years of participation can owe a larger additional tax than other IRAs.",
        ["irs_simple"]],
    ]],
    ["Education and healthcare", [
      ["529 education savings plan",
        "A state-sponsored plan for education costs. Investments grow tax-deferred, and withdrawals for qualified education expenses are free of federal income tax.",
        "Saving for a child's or your own future education.",
        "Earnings taken out for other purposes are taxed and can owe an additional tax. Plans differ by state, and the investments can lose value.",
        ["inv_529", "irs_529qa", "irs_p970"]],
      ["Coverdell Education Savings Account",
        "A trust or custodial account for a beneficiary's education. Qualified withdrawals are tax-free, including some elementary and secondary school costs.",
        "Families saving for school costs before college as well as after.",
        "Contributions are limited each year, and higher earners may not be able to contribute. The money generally must be used by the time the beneficiary reaches a set age.",
        ["irs_p970"]],
      ["Health Savings Account (HSA)",
        "A tax-advantaged account for people covered by a qualifying high-deductible health plan. Contributions can lower taxable income, and qualified medical withdrawals are tax-free.",
        "Paying medical costs now or saving for them later. Some providers let the balance be invested.",
        "You can contribute only while covered by a qualifying plan. Money taken out for non-medical costs is taxed and can owe an additional tax.",
        ["irs_p969"]],
    ]],
  ];

  var INTRO = "These are 13 commonly encountered account types or arrangements, not 13 exclusive official categories. " +
    "Some overlap: an individual or joint account is also either a cash or a margin account, and an IRA or a custodial account is often held at a brokerage.";
  var NOTICE = "Static educational content — not AI-generated. Not tax, legal or investment advice. " +
    "Tax rules, limits and eligibility change, so check the official sources.";

  var backdrop = null;
  var dialog = null;
  var opener = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function detail(label, text) {
    var p = el("p", "acct-detail");
    p.appendChild(el("strong", null, label + ": "));
    p.appendChild(document.createTextNode(text));
    return p;
  }

  function sourceLinks(keys) {
    var p = el("p", "acct-sources");
    p.appendChild(document.createTextNode("Official sources: "));
    keys.forEach(function (key, i) {
      if (i) p.appendChild(document.createTextNode(" · "));
      var a = el("a", null, SOURCES[key][0]);
      a.href = SOURCES[key][1];
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.appendChild(el("span", "visually-hidden", " (opens in a new tab)"));
      p.appendChild(a);
    });
    return p;
  }

  function toggle(button, panel) {
    var open = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    panel.hidden = !open;
  }

  function build(root) {
    backdrop = el("div", "acct-backdrop");
    backdrop.hidden = true;
    dialog = el("div", "acct-dialog");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "acct-title");
    dialog.tabIndex = -1;

    var title = el("h2", "acct-title", "Brokerage & Investing Accounts 101");
    title.id = "acct-title";
    dialog.appendChild(title);
    dialog.appendChild(el("p", "acct-intro", INTRO));
    dialog.appendChild(el("p", "acct-notice", NOTICE));

    var n = 0;
    CATEGORIES.forEach(function (cat) {
      dialog.appendChild(el("h3", "acct-category", cat[0]));
      var list = el("ul", "acct-list");
      cat[1].forEach(function (a) {
        n += 1;
        var li = el("li", "acct-item");
        var button = el("button", "acct-toggle", a[0]);
        button.type = "button";
        button.id = "acct-btn-" + n;
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", "acct-panel-" + n);
        var panel = el("div", "acct-panel");
        panel.id = "acct-panel-" + n;
        panel.setAttribute("role", "region");
        panel.setAttribute("aria-labelledby", button.id);
        panel.hidden = true;
        panel.appendChild(detail("How it works", a[1]));
        panel.appendChild(detail("Typical use", a[2]));
        panel.appendChild(detail("Watch out for", a[3]));
        panel.appendChild(sourceLinks(a[4]));
        button.addEventListener("click", function () { toggle(button, panel); });
        li.appendChild(button);
        li.appendChild(panel);
        list.appendChild(li);
      });
      dialog.appendChild(list);
    });

    var closeBtn = el("button", "acct-close button-secondary", "Close");
    closeBtn.type = "button";
    closeBtn.addEventListener("click", close);
    dialog.appendChild(closeBtn);

    backdrop.appendChild(dialog);
    backdrop.addEventListener("click", function (e) { if (e.target === backdrop) close(); });
    document.addEventListener("keydown", onKey);
    root.appendChild(backdrop);
  }

  function onKey(e) {
    if (!backdrop || backdrop.hidden) return;
    if (e.key === "Escape") {
      close();
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
    var root = document.getElementById("accounts-root");
    if (!root) return;
    if (!backdrop) build(root);
    if (!backdrop.hidden) return;
    opener = document.activeElement;
    backdrop.hidden = false;
    dialog.focus();
  }

  function close() {
    if (!backdrop || backdrop.hidden) return;
    backdrop.hidden = true;
    if (opener && opener.focus && document.contains(opener)) opener.focus();
  }

  window.Accounts = {
    init: function () {
      var button = document.getElementById("accounts-open");
      if (button) button.addEventListener("click", open);
    },
    open: open,
  };
})();
