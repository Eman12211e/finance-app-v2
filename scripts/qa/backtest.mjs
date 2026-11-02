// Finance App V2 QA suite: backtest. P5 step 6: the Trade / Test a strategy switch, the setup form, Run test, the
// results (outcome, metrics, fills, halves, notes) against the API, every state, account isolation, keyboard, phone.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/backtest.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const errors = [], hosts = new Set(), requests = [], paused = [];
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pend[m.id]) return pend[m.id](m.result || m);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.args.map(a => a.value).join(" "));
  if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) {
    hosts.add(new URL(m.params.request.url).host);
    requests.push({ method: m.params.request.method, path: new URL(m.params.request.url).pathname, body: m.params.request.postData });
  }
  if (m.method === "Fetch.requestPaused") paused.push(m.params.requestId);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => results.push([ok ? "PASS" : "FAIL", name, String(detail).slice(0, 260)]);
const MINUS = "−";

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  for (const d of ["Runtime", "Network", "Page"]) await send(d + ".enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(e.slice(0, 80) + " -> " + JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const key = async (k, code, vk, shift) => { const text = k === "Enter" ? String.fromCharCode(13) : k === " " ? " " : undefined; for (const t of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type: t, key: k, code, windowsVirtualKeyCode: vk, modifiers: shift ? 8 : 0, text: t === "keyDown" ? text : undefined }, s); await sleep(80); };
  const waitFor = async (expr, ms = 8000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(80); } return false; };
  const shot = async name => {  // the whole page, not just the viewport (the sticky footer and the phone tab bar are laid flat for the capture)
    await ev(`(() => { document.querySelectorAll("#disclaimer-footer, .tabs").forEach(n => { n.style.position = "static"; }); return true; })()`);
    const m = await send("Page.getLayoutMetrics", {}, s);
    const size = m.cssContentSize || m.contentSize;
    const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: size.width, height: size.height, scale: 1 } }, s);
    writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64"));
    await ev(`(() => { document.querySelectorAll("#disclaimer-footer, .tabs").forEach(n => { n.style.position = ""; }); return true; })()`);
  };
  const seed = async days => ev(`(async () => {
    const post = (a, b) => fetch("/api/paper/" + a, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()).then(j => j.data);
    let st = (await post("new", { scenario: "synthetic-b" })).state;
    for (let d = 0; d < ${days}; d++) st = (await post("advance", { state: st, expected_day: d })).state;
    localStorage.clear(); localStorage.setItem("fe_profile", JSON.stringify({ age_range: "25-34", risk: "medium" }));
    localStorage.setItem("paper-session-v1", JSON.stringify(st));
    localStorage.setItem("paper-indicators-v1", JSON.stringify([{ type: "sma", period: 20 }])); return true; })()`);
  const open = async (width, theme) => {
    await send("Emulation.setDeviceMetricsOverride", { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 }, s);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, s);
    await send("Page.navigate", { url: "about:blank" }, s); await sleep(100);
    await send("Page.navigate", { url: base + "/#practice" }, s);
    await waitFor(`!!document.querySelector(".pt-view-switch") && !!document.querySelector(".pt-chart-canvas canvas")`, 10000);
    await sleep(150);
  };
  const toStrategy = async () => { await ev(`document.querySelector('[data-key="view-strategy"]').click(); true`); await sleep(120); };
  // choose, press Run test, and wait for the new result (the heading node is replaced on every result)
  const runTest = async (symbol, preset, costs) => {
    await ev(`(() => { window.__old = document.getElementById("pt-bt-title"); const sel = document.getElementById("pt-bt-symbol"); sel.value = ${JSON.stringify(symbol)}; sel.dispatchEvent(new Event("change"));
      document.querySelector('[data-key="pt-bt-rule-${preset}"]').click(); document.querySelector('[data-key="pt-bt-costs-${costs}"]').click();
      document.querySelector('[data-key="bt-run"]').click(); return true; })()`);
    return waitFor(`!!document.getElementById("pt-bt-title") && document.getElementById("pt-bt-title") !== window.__old && document.querySelector('[data-key="bt-run"]').getAttribute("aria-disabled") === "false"`);
  };
  const api = (symbol, preset, costs) => ev(`fetch("/api/backtest/run", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: JSON.parse(localStorage.getItem("paper-session-v1")), symbol: ${JSON.stringify(symbol)}, preset: "${preset}", costs: "${costs}" }) }).then(r => r.json()).then(j => j.data)`);
  const money = c => (c < 0 ? MINUS : "") + "$" + Math.floor(Math.abs(c) / 100).toLocaleString("en-US") + "." + String(Math.abs(c) % 100).padStart(2, "0");
  const pct = (v, signed) => (v < 0 ? MINUS : signed && v > 0 ? "+" : "") + Math.abs(v).toFixed(2) + "%";
  const table = sel => ev(`[...document.querySelectorAll(${JSON.stringify(sel + " tbody tr")})].map(tr => [...tr.children].map(c => c.textContent))`);
  const text = sel => ev(`(document.querySelector(${JSON.stringify(sel)}) || {}).textContent || ""`);
  const all = () => ev(`document.querySelector(".pt-bt-results-box").textContent`);

  await send("Page.navigate", { url: base + "/" }, s); await sleep(800);

  // ---------- Day 161, desktop light: the switch, the setup and the mockup example ----------
  await seed(160); await open(1280, "light");
  check("the switch starts on Trade", await ev(`document.querySelector('[data-key="view-trade"]').getAttribute("aria-pressed") === "true" && document.querySelector('[data-key="view-strategy"]').getAttribute("aria-pressed") === "false" && document.querySelector(".pt-view-switch").getAttribute("role") === "group"`));
  check("Trade shows the workspace and hides the test", await ev(`!document.querySelector(".pt-bt-setup").offsetParent && !document.querySelector(".pt-bt-results-box").offsetParent && !!document.querySelector(".pt-ticket").offsetParent`));
  const accountBefore = await ev(`localStorage.getItem("paper-session-v1")`), stripBefore = await text(".pt-strip");
  await ev(`document.querySelector('[data-key="view-strategy"]').focus(); true`); await key("Enter", "Enter", 13); await sleep(150);
  check("Enter on the switch opens Test a strategy", await ev(`document.querySelector('[data-key="view-strategy"]').getAttribute("aria-pressed") === "true"`));
  check("the trade regions are hidden; the setup sits in the ticket's column", await ev(`(() => { const hid = [".pt-chart", ".pt-positions", ".pt-pending", ".pt-ticket", ".pt-learn"].every(q => !document.querySelector(q).offsetParent);
    const setup = document.querySelector(".pt-bt-setup").getBoundingClientRect(), centre = document.querySelector(".pt-bt-results-box").getBoundingClientRect();
    return hid && setup.left > centre.right && !!document.querySelector(".pt-strip").offsetParent && !!document.querySelector(".pt-watch").offsetParent; })()`));
  check("setup: approved heading, intro, ticker list, two rules, two cost settings and footnote", await ev(`(() => { const f = document.querySelector(".pt-bt-setup-form"), t = f.textContent;
    return t.includes("Test a strategy") && t.includes("Replay a fixed rule on the days you have reached, next to buying and holding the same ticker.")
      && document.getElementById("pt-bt-symbol").options.length === 12 && document.querySelector('label[for="pt-bt-symbol"]').textContent === "Ticker"
      && t.includes("Buys when the 20-day average crosses above the 50-day average; sells when it crosses back below.") && t.includes("Buys when RSI 14 closes below 30; sells when it closes above 70.")
      && f.querySelectorAll('input[name="pt-bt-rule"]').length === 2 && f.querySelectorAll('input[name="pt-bt-costs"]').length === 2
      && document.querySelector('[data-key="pt-bt-rule-sma_cross"]').checked && document.querySelector('[data-key="pt-bt-costs-example"]').checked
      && t.includes("Uses Days 1–161. Your practice account is not changed."); })()`));
  check("before a run: How this test works and the standing note, nothing estimated", (await all()).includes("How this test works") && (await all()).includes("Past results, real or simulated, do not tell you what will happen next.") && !(await ev(`!!document.getElementById("pt-bt-title")`)));
  const tradeTicker = await ev(`document.querySelector('.pt-watch-item[aria-current="true"]').dataset.symbol`);
  check("the ticker list starts on the trade ticker", (await ev(`document.getElementById("pt-bt-symbol").value`)) === tradeTicker, tradeTicker);
  await shot("setup-1280-light");

  requests.length = 0;
  check("Run test shows a result", await runTest("SYN-HLT1", "sma_cross", "example"));
  check("focus moves to the results heading", await ev(`document.activeElement === document.getElementById("pt-bt-title") && document.activeElement.textContent === "SMA crossover 20 / 50 on SYN-HLT1"`));
  const sent = requests.filter(r => r.method === "POST");
  check("one POST, to /api/backtest/run only", sent.length === 1 && sent[0].path === "/api/backtest/run", sent.map(r => r.path).join(","));
  check("the request carries only state, symbol, preset and costs", sent.length === 1 && JSON.stringify(Object.keys(JSON.parse(sent[0].body)).sort()) === JSON.stringify(["costs", "preset", "state", "symbol"]) && JSON.parse(sent[0].body).symbol === "SYN-HLT1");
  check("the account is unchanged: saved session and strip", (await ev(`localStorage.getItem("paper-session-v1")`)) === accountBefore && (await text(".pt-strip")) === stripBefore);
  check("approved outcome sentence (mockup 09 numbers)", (await text(".pt-bt-outcome")) === "This rule ended at $10,442.81 (+4.43%). Buying and holding SYN-HLT1 over the same days ended at $11,029.60 (+10.30%), so the rule ended 5.87 points lower.", await text(".pt-bt-outcome"));
  check("window line", (await all()).includes("Results are measured from the Day 50 close (Mar 12), when both start with $10,000.00 in cash, to the Day 161 close (Aug 14, 2025): 111 trading days.") && (await all()).includes("Example costs."));
  const hlt = await api("SYN-HLT1", "sma_cross", "example"), sm = hlt.result.strategy.metrics, bm = hlt.result.benchmark.metrics;
  const metrics = await table(".pt-bt-metrics");
  const expected = [["Value at the end", money(sm.final_value_cents), money(bm.final_value_cents)], ["Total return", pct(sm.total_return_pct, true), pct(bm.total_return_pct, true)],
    ["Largest drop from a high", MINUS + pct(sm.max_drawdown_pct) + "May 12 to Jun 9", MINUS + pct(bm.max_drawdown_pct) + "May 12 to Jul 3"], ["Daily volatility", pct(sm.daily_volatility_pct), pct(bm.daily_volatility_pct)],
    ["Trades", "2 buys, 1 sell", "1 buy, 0 sells"], ["Days invested", `${sm.days_invested} of 111`, "111 of 111"], ["Costs paid", money(sm.costs_paid_cents), money(bm.costs_paid_cents)]];
  check("metrics table equals the API, rule and buy and hold side by side", JSON.stringify(metrics) === JSON.stringify(expected), JSON.stringify(metrics));
  check("mockup numbers in the table", JSON.stringify(metrics.map(r => r[1])) === JSON.stringify(["$10,442.81", "+4.43%", MINUS + "10.51%May 12 to Jun 9", "0.96%", "2 buys, 1 sell", "49 of 111", "$30.91"]));
  check("Daily volatility, not Typical daily move", !(await all()).includes("Typical daily move"));
  check("comparison row and table headers", (await text(".pt-bt-metrics tfoot")) === "Compared with buy and hold5.87 points lower total return" && (await ev(`[...document.querySelectorAll(".pt-bt-metrics thead th")].map(t => t.textContent).join("|")`)) === "Measure|This rule|Buy and hold" && (await ev(`[...document.querySelectorAll(".pt-bt-metrics th[scope=row]")].length`)) === 8);
  const fills = await table(".pt-bt-fills");
  check("fills table: every fill from the API, approved columns and In / Out words", fills.length === hlt.result.strategy.fills.length && JSON.stringify(fills[0]) === JSON.stringify(["Day 79Apr 22", "Day 80Apr 23", "In: bought", "94", "$105.58", "$105.69", "$10.34", "$65.14"]) && fills[1][2] === "Out: sold", JSON.stringify(fills));
  check("still holding, and buy and hold's line", (await all()).includes("Still holding 93 shares at the end, valued at the Day 161 close of $111.34. They were not sold, so no further cost was charged.") && (await all()).includes("Buy and hold bought 99 shares at the Day 51 open ($100.83, fill price $100.94) and kept them."));
  const halves = await table(".pt-bt-halves");
  check("halves: both rows, from a fresh $10,000, with the descriptive note", JSON.stringify(halves) === JSON.stringify([["Earlier halfDay 50 close to Day 105 close (Mar 12 – May 28)", MINUS + "1.75%", "+2.86%"], ["Later halfDay 105 close to Day 161 close (May 28 – Aug 14)", "+9.14%", "+7.18%"]]) && (await all()).includes("The same rule, tested again on each half from a fresh $10,000.") && (await all()).includes("It is not evidence that the rule works"), JSON.stringify(halves));
  check("How this test works: the five points, the rule's start and Why this is not a forecast", await ev(`(() => { const t = document.querySelector(".pt-bt-how").textContent; return document.querySelectorAll(".pt-bt-how li").length === 6 && t.includes("rounded to the cent against the trader") && t.includes("The first crossing the test can see is on Day 51") && t.includes("Why this is not a forecast") && t.includes("A backtest replays a fixed rule"); })()`));
  check("the standing note ends the result", (await ev(`document.querySelector(".pt-bt-results-box").lastElementChild.textContent`)).startsWith("This is a hypothetical test on computer-generated prices."));
  check("no banned wording in the results", !/\b(expect|predict|best|winning|outperform|guaranteed|you should|buy now|sell now|in-sample|out-of-sample)\b/i.test(await all()));
  check("gains and losses carry a sign and an arrow, not colour alone", await ev(`[...document.querySelectorAll(".pt-bt-results-box .pt-up, .pt-bt-results-box .pt-down")].every(n => /^[+−]/.test(n.textContent) && /[▲▼]/.test(getComputedStyle(n, "::before").content))`));
  check("no price or percentage wraps inside a table cell", await ev(`[...document.querySelectorAll(".pt-bt-table tbody td")].every(td => { const n = td.firstChild; if (!n || n.nodeType !== 3) return true; const r = document.createRange(); r.selectNodeContents(n); return r.getClientRects().length <= 1; })`));
  await shot("result-1280-light");

  // ---------- RSI rule, no costs ----------
  check("RSI rule, no costs", await runTest("SYN-ENR1", "rsi_threshold", "none"));
  const enr = await api("SYN-ENR1", "rsi_threshold", "none");
  const pts = enr.result.difference_pp;
  check("RSI outcome equals the API", (await text(".pt-bt-outcome")) === `This rule ended at ${money(enr.result.strategy.metrics.final_value_cents)} (${pct(enr.result.strategy.metrics.total_return_pct, true)}). Buying and holding SYN-ENR1 over the same days ended at ${money(enr.result.benchmark.metrics.final_value_cents)} (${pct(enr.result.benchmark.metrics.total_return_pct, true)}), so the rule ended ${Math.abs(pts).toFixed(2)} points ${pts > 0 ? "higher" : "lower"}.`, await text(".pt-bt-outcome"));
  check("no-costs wording and RSI start note", (await all()).includes("No costs.") && (await all()).includes("No costs: every fill is at the opening price exactly.") && (await all()).includes("RSI 14 already has values on Day 50.") && (await table(".pt-bt-metrics"))[6][1] === "$0.00");

  // ---------- no trades: SYN-TEC1 crossover (the corrected sentence) ----------
  check("no trades runs", await runTest("SYN-TEC1", "sma_cross", "example"));
  check("no trades: approved, corrected wording", (await all()).includes("No trades: the rule never triggered") && (await all()).includes("The 20-day average did not cross above the 50-day average from the Day 50 close to Day 161, so the rule stayed in cash at $10,000.00 (0.00%).") && (await all()).includes("Buying and holding SYN-TEC1 over the same days ended at $11,298.08 (+12.98%).") && (await all()).includes("It does not assume a trade happened before the Day 50 close."));
  check("no trades: no fills list, the table still compares", !(await ev(`!!document.querySelector(".pt-bt-fills")`)) && (await table(".pt-bt-metrics"))[4][1] === "0 buys, 0 sells" && (await table(".pt-bt-metrics"))[2][1] === "No drop");
  await shot("no-trades-1280-light");

  // ---------- running state and a failed request (the network is paused, then failed) ----------
  await send("Fetch.enable", { patterns: [{ urlPattern: "*/api/backtest/run*" }] }, s);
  await ev(`(() => { document.querySelector('[data-key="bt-run"]').click(); return true; })()`);
  await waitFor(`document.querySelector('[data-key="bt-run"]').getAttribute("aria-disabled") === "true"`, 3000);
  check("running: busy button stays focusable, status names the run, the previous result stays", await ev(`(() => { const b = document.querySelector('[data-key="bt-run"]'); return b.textContent === "Running test…" && !b.disabled && document.querySelector(".pt-bt-status").textContent === "Running SMA crossover 20 / 50 on SYN-TEC1." && document.querySelector(".pt-bt-results-box").textContent.includes("No trades"); })()`));
  await ev(`document.querySelector('[data-key="bt-run"]').click(); true`); await sleep(200);
  check("a second press while running sends nothing more", paused.length === 1, paused.length);
  await shot("running-1280-light");
  for (const r of paused.splice(0)) await send("Fetch.failRequest", { requestId: r, errorReason: "ConnectionRefused" }, s);
  await waitFor(`!!document.getElementById("pt-bt-title") && document.getElementById("pt-bt-title").textContent === "The test could not run"`);
  check("request failed: approved wording and Try again", (await all()).includes("The server did not answer. Your practice session is unchanged.") && await ev(`!!document.querySelector('[data-key="bt-retry"]') && document.activeElement === document.getElementById("pt-bt-title")`));
  check("…and the account is still unchanged", (await ev(`localStorage.getItem("paper-session-v1")`)) === accountBefore);
  await shot("error-1280-light");
  await send("Fetch.disable", {}, s);
  await ev(`window.__old = document.getElementById("pt-bt-title"); document.querySelector('[data-key="bt-retry"]').click(); true`);
  check("Try again runs the same test", await waitFor(`document.getElementById("pt-bt-title") !== window.__old && document.getElementById("pt-bt-title").textContent === "SMA crossover 20 / 50 on SYN-TEC1"`));

  // ---------- keyboard only: change the rule with the arrow keys and submit with Enter ----------
  await ev(`document.querySelector('[data-key="pt-bt-rule-sma_cross"]').focus(); window.__old = document.getElementById("pt-bt-title"); true`);
  await key("ArrowDown", "ArrowDown", 40);
  check("arrow keys move between the rules", await ev(`document.querySelector('[data-key="pt-bt-rule-rsi_threshold"]').checked && document.activeElement.dataset.key === "pt-bt-rule-rsi_threshold"`));
  await key("Enter", "Enter", 13);
  check("Enter in the form runs the test", await waitFor(`document.getElementById("pt-bt-title") !== window.__old && document.getElementById("pt-bt-title").textContent === "RSI 14 below 30 / above 70 on SYN-TEC1"`));
  check("every control in the setup form is reachable with Tab (none removed from the order)", await ev(`[...document.querySelectorAll(".pt-bt-setup-form select, .pt-bt-setup-form input, .pt-bt-setup-form button")].every(n => n.tabIndex >= 0)`));

  // ---------- a ticker picked in the list, and a new practice day ----------
  await ev(`document.querySelector('.pt-watch-item[data-symbol="SYN-FIN1"]').click(); true`); await sleep(150);
  check("a ticker clicked in the list becomes the test's ticker; the view stays", (await ev(`document.getElementById("pt-bt-symbol").value`)) === "SYN-FIN1" && await ev(`document.querySelector('[data-key="view-strategy"]').getAttribute("aria-pressed") === "true"`));
  await ev(`document.querySelector('[data-key="next-1"]').click(); true`);
  await waitFor(`document.querySelector(".pt-bt-setup-form").textContent.includes("Uses Days 1–162.")`);
  check("Next day clears the old result and updates the footnote", (await all()).includes("The practice day changed, so the previous result was cleared.") && !(await ev(`!!document.getElementById("pt-bt-title")`)));
  const accountAfterDay = await ev(`localStorage.getItem("paper-session-v1")`);
  check("Run test after the new day uses Day 162", await runTest("SYN-HLT1", "sma_cross", "example") && (await all()).includes("to the Day 162 close"));
  check("…and leaves that session unchanged too", (await ev(`localStorage.getItem("paper-session-v1")`)) === accountAfterDay);

  // ---------- back to Trade: P4 and the workspace are intact ----------
  await ev(`document.querySelector('[data-key="view-trade"]').click(); true`);
  await waitFor(`!!document.querySelector(".pt-chart-canvas canvas") && document.querySelector(".pt-chart-canvas").getBoundingClientRect().width > 300`);
  check("Trade again: chart drawn at full size with the saved indicator, ticket back, test hidden", await ev(`(() => { const c = document.querySelector(".pt-chart-canvas").getBoundingClientRect(); return c.width > 300 && c.height > 150 && !!document.querySelector(".pt-ticket").offsetParent && !document.querySelector(".pt-bt-setup").offsetParent && document.querySelectorAll(".pt-card").length === 1; })()`));
  await toStrategy();
  check("the result is still there when the view is opened again", (await text("#pt-bt-title")) === "SMA crossover 20 / 50 on SYN-HLT1");

  // ---------- dark, desktop ----------
  await seed(160); await open(1280, "dark"); await toStrategy(); await runTest("SYN-HLT1", "sma_cross", "example");
  await shot("result-1280-dark");

  // ---------- Not enough data (Day 41) ----------
  await seed(40); await open(1280, "light"); await toStrategy(); await runTest("SYN-HLT1", "sma_cross", "example");
  check("not enough data: approved wording, nothing estimated", (await text("#pt-bt-title")) === "Not enough data yet" && (await all()).includes("This test needs 70 trading days of history: 50 to build the 50-day average and at least 20 to test on. You have reached 41 so far.") && (await all()).includes("Advance 29 more days in Practice Trading to run it. Nothing is estimated in the meantime.") && !(await ev(`!!document.querySelector(".pt-bt-metrics")`)));
  await shot("not-enough-data-1280-light");

  // ---------- too short to split (Day 100) ----------
  await seed(99); await open(1280, "light"); await toStrategy(); await runTest("SYN-HLT1", "sma_cross", "example");
  check("too short to split: approved wording", (await all()).includes("Too short to split: each half needs at least 40 test days, and there are 50 so far. Available from Day 130.") && !(await ev(`!!document.querySelector(".pt-bt-halves table")`)));

  // ---------- a signal on the last day (Day 165) ----------
  await seed(164); await open(1280, "light"); await toStrategy(); await runTest("SYN-CON1", "sma_cross", "example");
  check("signal on the last day: approved wording, not filled", (await all()).includes("Signal on Day 165, the last day so far: sell. Not acted on, because there is no next open yet.") && (await all()).includes("Still holding 188 shares at the end, valued at the Day 165 close of $45.75."));
  await shot("last-day-signal-1280-light");

  // ---------- phone, light and dark ----------
  await seed(160); await open(390, "light");
  await ev(`(() => { const b = document.querySelector('[data-key="view-strategy"]'); b.scrollIntoView({ block: "center" }); b.click(); return true; })()`); await sleep(150);
  check("phone: switch, then setup, then results; no trade sheet or Trade button", await ev(`(() => { const y = q => document.querySelector(q).getBoundingClientRect().top;
    return y(".pt-view-switch") < y(".pt-bt-setup") && y(".pt-bt-setup") < y(".pt-bt-results-box") && !document.querySelector(".pt-trade-bar").offsetParent && !document.querySelector(".pt-ticket").offsetParent; })()`));
  check("phone: 44 px controls", await ev(`[...document.querySelectorAll(".pt-bt-select, .pt-bt-option, [data-key='bt-run'], .pt-view-switch button")].every(n => n.getBoundingClientRect().height >= 40)`));
  await ev(`document.querySelector('.pt-watch-item[data-symbol="SYN-HLT1"]') && document.querySelector('.pt-watch-item[data-symbol="SYN-HLT1"]').click(); true`); await sleep(150);
  check("phone: a ticker picked in the list never opens the trade sheet", !(await ev(`!!document.querySelector(".pt-ticket.pt-open")`)) && (await ev(`document.getElementById("pt-bt-symbol").value`)) === "SYN-HLT1");
  await shot("setup-390-light");
  await runTest("SYN-HLT1", "sma_cross", "example");
  check("phone: no horizontal overflow with a full result", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  check("phone: each fill is a card with its labels", await ev(`(() => { const td = document.querySelector(".pt-bt-fills tbody td"); return getComputedStyle(document.querySelector(".pt-bt-fills tr")).display === "grid" && getComputedStyle(td, "::before").content.includes("Signal at the close of"); })()`));
  check("phone: no price or percentage wraps inside a table cell", await ev(`[...document.querySelectorAll(".pt-bt-table tbody td")].every(td => { const n = td.firstChild; if (!n || n.nodeType !== 3) return true; const r = document.createRange(); r.selectNodeContents(n); return r.getClientRects().length <= 1; })`));
  await shot("result-390-light");
  await open(390, "dark");
  await ev(`(() => { const b = document.querySelector('[data-key="view-strategy"]'); b.scrollIntoView({ block: "center" }); b.click(); return true; })()`); await sleep(150);
  await runTest("SYN-HLT1", "sma_cross", "example");
  check("phone dark: no horizontal overflow", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await shot("result-390-dark");

  check("only the local server was contacted", [...hosts].every(h => h.startsWith("127.0.0.1")), [...hosts].join(","));
  check("no console errors or warnings", errors.filter(e => !/ERR_CONNECTION_REFUSED|Failed to fetch|Failed to load resource/.test(e)).length === 0, errors.join(" | "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
