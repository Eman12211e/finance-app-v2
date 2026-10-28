// Finance App V2 QA suite: workflows. P2.5/P3 Practice Trading workflows at 1280 and 390 px on both markets: ordering, fills, chart, scenario switching, phone sheet, keyboard paths, saved sessions, journal privacy.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/workflows.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
const [wsUrl, outDir] = process.argv.slice(2);
const BASE = process.argv[4] || "http://127.0.0.1:5055";
import { writeFileSync } from "node:fs";
const ws = new WebSocket(wsUrl); let id = 0; const pending = {}; const listeners = [];
const send = (method, params = {}, sessionId) => new Promise(r => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending[m.id]) pending[m.id](m.result || m); else listeners.forEach(f => f(m)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => { results.push([ok ? "PASS" : "FAIL", name, detail]); };

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  const posts = [], errors = [], hosts = new Set();
  listeners.push(m => {
    if (m.sessionId !== s) return;
    if (m.method === "Network.requestWillBeSent") { if (/^https?:/.test(m.params.request.url)) hosts.add(new URL(m.params.request.url).host); if (m.params.request.postData) posts.push(m.params.request.postData); }
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map(a => a.value).join(" "));
  });
  await send("Network.enable", {}, s); await send("Runtime.enable", {}, s); await send("Page.enable", {}, s);
  const ev = async expr => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(expr + " -> " + JSON.stringify(r.exceptionDetails.exception?.description)); return r.result.value; };
  const key = async (k, code, vk, shift) => {
    const mods = shift ? 8 : 0;
    await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, code, windowsVirtualKeyCode: vk, modifiers: mods, text: k === "Enter" ? "\r" : undefined }, s);
    await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code, windowsVirtualKeyCode: vk, modifiers: mods }, s);
  };
  const typeText = t => send("Input.insertText", { text: t }, s);
  const focused = () => ev(`(() => { const a = document.activeElement; return a ? (a.id || a.getAttribute("data-key") || a.textContent.trim().slice(0, 30) || a.tagName) : null; })()`);
  const waitFor = async (expr, ms = 5000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(100); } return false; };
  const overflow = () => ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  const shot = async name => { const r = await send("Page.captureScreenshot", { format: "png" }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64")); };

  for (const [width, scenario] of [[1280, "synthetic-b"], [1280, "synthetic-a"], [390, "synthetic-b"], [390, "synthetic-a"]]) {
    const tag = `${width}/${scenario}`; const phone = width < 500;
    await send("Emulation.setDeviceMetricsOverride", { width, height: phone ? 844 : 900, deviceScaleFactor: 1, mobile: phone }, s);
    await send("Page.navigate", { url: BASE + "/" }, s); await sleep(800);
    await ev(`localStorage.clear(); localStorage.setItem("fe_profile", JSON.stringify({age_range:"25-34", risk:"medium"})); true`);
    await send("Page.navigate", { url: BASE + "/#practice" }, s);
    await waitFor(`!!document.querySelector(".pt-start-button")`);
    await ev(`(document.querySelector("form.modal button") || {click(){}}).click(); true`);
    await waitFor(`document.querySelectorAll('input[name="pt-market"]').length === 2`);
    check(`${tag} empty state: picker + how-it-works`, await ev(`!!document.querySelector(".pt-steps") && document.querySelectorAll(".pt-steps li").length === 3`));
    check(`${tag} empty state no overflow`, (await overflow()) === 0, String(await overflow()));
    if (scenario === "synthetic-b") await shot(`empty-${width}`);
    await ev(`document.querySelector('input[name="pt-market"][value="${scenario}"]').click(); document.querySelector(".pt-start-button").click(); true`);
    const loaded = await waitFor(`document.querySelectorAll(".pt-watch-item").length > 0 && !!document.querySelector(".pt-spark-box")`);
    const n = scenario === "synthetic-b" ? 12 : 2;
    check(`${tag} workspace loads with sparklines`, loaded);
    check(`${tag} watchlist has ${n} tickers`, (await ev(`document.querySelectorAll(".pt-watch-item").length`)) === n);
    check(`${tag} sectors shown`, (await ev(`document.querySelectorAll(".pt-sector").length`)) === (n === 12 ? 6 : 0));
    check(`${tag} day counter`, await ev(`document.querySelector(".pt-day-line").textContent.startsWith("Day 1 of ${n === 12 ? 250 : 120}")`));
    check(`${tag} progressbar`, await ev(`document.querySelector('[role="progressbar"]').getAttribute("aria-valuenow") === "1"`));
    check(`${tag} chart canvas ${phone ? "4:3" : "16:9"}`, await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`) && await ev(`(() => { const r = document.querySelector(".pt-chart-canvas").getBoundingClientRect(); return Math.abs(r.width / r.height - ${phone ? 4 / 3 : 16 / 9}) < 0.05; })()`));
    check(`${tag} chart summary and legend`, await ev(`document.querySelector(".pt-chart-summary").textContent.startsWith("Daily simulated prices from Jan 2, 2025 to Jan 2, 2025") && document.querySelector(".pt-chart-legend").textContent.startsWith("Jan 2, 2025: open $")`));
    check(`${tag} TradingView credit link`, await ev(`(() => { const a = document.querySelector('.pt-chart a[href="https://www.tradingview.com/"]'); return !!a && a.rel === "noopener noreferrer"; })()`));
    check(`${tag} Simulated labels`, (await ev(`document.querySelectorAll(".pt-sim").length`)) >= 4, String(await ev(`document.querySelectorAll(".pt-sim").length`)));
    const layout = await ev(`(() => { const w = document.querySelector(".pt-watch").getBoundingClientRect(), c = document.querySelector(".pt-centre").getBoundingClientRect(), t = document.querySelector(".pt-ticket").getBoundingClientRect(); return { w: [w.left, w.width], c: [c.left, c.width], t: [t.left, t.width], tDisplay: getComputedStyle(document.querySelector(".pt-ticket")).display, sticky: getComputedStyle(document.querySelector(".pt-ticket")).position, bar: getComputedStyle(document.querySelector(".pt-trade-bar")).display }; })()`);
    if (!phone) {
      check(`${tag} three regions left to right`, layout.w[0] < layout.c[0] && layout.c[0] < layout.t[0], JSON.stringify(layout));
      check(`${tag} ticket sticky, no Trade bar`, layout.sticky === "sticky" && layout.bar === "none");
    } else {
      check(`${tag} phone: ticket hidden, Trade bar shown`, layout.tDisplay === "none" && layout.bar === "block", JSON.stringify(layout));
      const bar = await ev(`(() => { const b = document.querySelector(".pt-trade-bar").getBoundingClientRect(), f = document.getElementById("disclaimer-footer").getBoundingClientRect(), t = document.querySelector(".tabs").getBoundingClientRect(); return { b: b.bottom, f: f.top, t: t.top }; })()`);
      check(`${tag} Trade bar sits above footer and tabs`, bar.b <= bar.f + 1 && bar.b <= bar.t + 1, JSON.stringify(bar));
      await ev(`document.querySelector(".pt-trade-bar").focus(); true`); await key("Enter", "Enter", 13);
      await sleep(200);
      check(`${tag} sheet opens as modal dialog`, await ev(`(() => { const t = document.querySelector(".pt-ticket"); return t.getAttribute("role") === "dialog" && t.getAttribute("aria-modal") === "true" && t.contains(document.activeElement); })()`));
      await shot(`sheet-${scenario}-390`);
      // Tab cycles inside the sheet
      let escaped = false;
      for (let i = 0; i < 15; i++) { await key("Tab", "Tab", 9); if (!(await ev(`document.querySelector(".pt-ticket").contains(document.activeElement)`))) escaped = true; }
      check(`${tag} Tab stays inside the sheet`, !escaped);
      await key("Escape", "Escape", 27); await sleep(100);
      check(`${tag} Escape closes sheet, focus back on Trade`, await ev(`!document.querySelector(".pt-ticket").classList.contains("pt-open") && document.activeElement === document.querySelector(".pt-trade-bar")`));
      await ev(`document.querySelector(".pt-trade-bar").click(); true`); await sleep(200);
    }
    // keyboard: search the picker
    const want = scenario === "synthetic-b" ? "SYN-TEC2" : "SAMPLE-B";
    await ev(`document.getElementById("pt-ticker").focus(); document.getElementById("pt-ticker").select(); true`);
    await typeText(scenario === "synthetic-b" ? "chip" : "company b");
    check(`${tag} picker filters`, (await ev(`document.querySelectorAll("#pt-ticker-list [role=option]").length`)) === 1 && (await ev(`document.getElementById("pt-ticker").getAttribute("aria-expanded")`)) === "true");
    await key("Enter", "Enter", 13); await sleep(100);
    check(`${tag} Enter chooses ${want}`, await ev(`document.getElementById("pt-ticker").value === "${want}" && document.getElementById("pt-ticker").getAttribute("aria-expanded") === "false"`), await ev(`document.getElementById("pt-ticker").value`));
    check(`${tag} chart follows ticker`, await ev(`document.getElementById("pt-chart-title").textContent.startsWith("${want}")`));
    // Sell side with no holdings: Max disabled
    await ev(`document.querySelector('.pt-segmented [data-side="sell"]').click(); true`);
    check(`${tag} Sell: Max disabled with no shares`, await ev(`document.querySelector(".pt-max").disabled && document.querySelector('[data-side="sell"]').getAttribute("aria-pressed") === "true"`));
    await ev(`document.querySelector('.pt-segmented [data-side="buy"]').click(); document.querySelector(".pt-max").click(); true`);
    const maxShares = await ev(`Number(document.getElementById("pt-shares").value)`);
    const close = await ev(`(() => { const v = JSON.parse(localStorage.getItem("paper-session-v1")); return null; })()`);
    check(`${tag} Max fills affordable shares`, maxShares > 0 && (await ev(`document.getElementById("pt-ticket-problem").hidden`)), String(maxShares));
    await ev(`document.querySelector('[aria-label="One share more"]').click(); true`);
    check(`${tag} over Max shows a cash problem`, await ev(`!document.getElementById("pt-ticket-problem").hidden && document.getElementById("pt-ticket-problem").textContent.includes("available after pending buys")`));
    // type 3 shares and press Enter to preview
    await ev(`document.getElementById("pt-shares").focus(); document.getElementById("pt-shares").select(); true`);
    await typeText("3");
    const est = await ev(`document.querySelector(".pt-estimate strong").textContent`);
    await key("Enter", "Enter", 13);
    const reviewed = await waitFor(`document.getElementById("pt-ticket-title").textContent === "Check your practice order"`);
    check(`${tag} Enter previews in place`, reviewed && (await ev(`document.activeElement.id`)) === "pt-ticket-title");
    check(`${tag} review shows estimate`, await ev(`document.querySelector(".pt-review").textContent.includes(${JSON.stringify(est)})`), est);
    const watchBefore = await ev(`document.querySelector(".pt-watch-item")`) ;
    // Back keeps fields
    await ev(`[...document.querySelectorAll(".pt-actions button")].find(b => b.textContent === "Back").click(); true`);
    check(`${tag} Back keeps ticker and shares`, await ev(`document.getElementById("pt-ticker").value === "${want}" && document.getElementById("pt-shares").value === "3" && document.activeElement.id === "pt-shares"`));
    await key("Enter", "Enter", 13);
    await waitFor(`!!document.getElementById("pt-why")`);
    await ev(`document.getElementById("pt-why").focus(); true`); await typeText("SECRET-JOURNAL-why");
    await ev(`document.getElementById("pt-risks").focus(); true`); await typeText("SECRET-JOURNAL-risk");
    await ev(`document.querySelector(".pt-confirm").click(); true`);
    check(`${tag} confirm -> queued, one pending`, await waitFor(`document.getElementById("pt-ticket-title").textContent === "Order queued" && document.querySelectorAll(".pt-pending .pt-item").length === 1`));
    if (phone) { await key("Escape", "Escape", 27); await sleep(100); }
    // next day: fill toast + flash + history note
    await ev(`document.querySelector('[data-key="next-1"]').focus(); true`);
    await key("Enter", "Enter", 13);
    const toasted = await waitFor(`!!document.querySelector(".pt-toast") && document.querySelector(".pt-toast").textContent.startsWith("Bought 3 ${want}")`);
    check(`${tag} fill toast in role=status region`, toasted && (await ev(`document.querySelector(".pt-toasts").getAttribute("role")`)) === "status", await ev(`(document.querySelector(".pt-toast")||{}).textContent`));
    check(`${tag} positions row flashes`, await ev(`!!document.querySelector('tr.pt-flash[data-symbol="${want}"]')`));
    check(`${tag} focus kept on Next day`, (await focused()) === "next-1", await focused());
    check(`${tag} history shows journal note locally`, await ev(`document.querySelector(".pt-history").textContent.includes("SECRET-JOURNAL-why")`));
    await sleep(300);
    if (!phone || scenario === "synthetic-b") await shot(`workspace-${scenario}-${width}`);
    check(`${tag} toast dismisses within ~5s`, await waitFor(`!document.querySelector(".pt-toast")`, 6000));
    // next 5 days
    await ev(`document.querySelector('[data-key="next-5"]').click(); true`);
    check(`${tag} Next 5 days`, await waitFor(`document.querySelector(".pt-day-line").textContent.startsWith("Day 7 of")`, 8000));
    check(`${tag} chart ends on today, trade marked`, await waitFor(`(() => { const t = document.querySelector(".pt-chart-summary").textContent, d = document.querySelector(".pt-day-line").textContent.split(" ").slice(4).join(" "); return t.includes("to " + d + ":") && t.includes("1 of your trades is marked"); })()`), await ev(`document.querySelector(".pt-chart-summary").textContent + " | " + document.querySelector(".pt-day-line").textContent`));
    await ev(`(() => { const b = document.querySelector('[data-key="tf-weekly"]'); b.focus(); b.click(); return true; })()`); await sleep(300);
    check(`${tag} weekly view`, await ev(`document.querySelector('[data-key="tf-weekly"]').getAttribute("aria-pressed") === "true" && document.querySelector(".pt-chart-summary").textContent.startsWith("Weekly") && document.querySelector(".pt-chart-legend").textContent.startsWith("Week of Jan 6, 2025") && document.activeElement.getAttribute("data-key") === "tf-weekly"`), await ev(`document.querySelector(".pt-chart-legend").textContent`));
    await ev(`document.querySelector('[data-key="tf-daily"]').click(); true`); await sleep(300);
    const box = await ev(`(() => { document.querySelector(".pt-chart-canvas").scrollIntoView({ block: "center" }); const r = document.querySelector(".pt-chart-canvas").getBoundingClientRect(); return { l: r.left, w: r.width, y: r.top + r.height * 0.4 }; })()`);
    const before = await ev(`document.querySelector(".pt-chart-legend").textContent`);
    let moved = false;
    for (let f = 0.02; f < 0.98 && !moved; f += 0.02) {
      await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.l + box.w * f, y: box.y }, s); await sleep(60);
      moved = (await ev(`document.querySelector(".pt-chart-legend").textContent`)) !== before;
    }
    check(`${tag} crosshair readout follows the mouse`, moved, await ev(`document.querySelector(".pt-chart-legend").textContent`));
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 2, y: 2 }, s);
    check(`${tag} day change shown after advance`, await waitFor(`[...document.querySelectorAll(".pt-watch-item")].every(b => /[+-]?\\d+\\.\\d%/.test(b.textContent))`));
    // row click selects ticker
    await ev(`document.querySelector('tr[data-symbol="${want}"] td:nth-child(3)').click(); true`); await sleep(150);
    check(`${tag} row click selects ticker`, await ev(`document.getElementById("pt-ticker").value === "${want}"`));
    if (phone) { await key("Escape", "Escape", 27); await sleep(100); }
    // history filter keeps focus
    await ev(`(() => { const sel = document.querySelector('[data-key="history-filter"]'); sel.focus(); sel.value = "${want}"; sel.dispatchEvent(new Event("change")); return true; })()`);
    check(`${tag} history filter keeps focus`, (await focused()) === "history-filter");
    // reset menu keyboard
    await ev(`document.querySelector('[data-key="more"]').click(); true`);
    check(`${tag} More menu opens to Reset`, (await focused()) === "reset");
    await key("Escape", "Escape", 27);
    check(`${tag} Escape closes menu`, (await focused()) === "more" && (await ev(`document.getElementById("pt-session-menu").hidden`)));
    check(`${tag} no overflow in workspace`, (await overflow()) === 0, String(await overflow()));
    // sell part of the position: proceeds, realized P/L in history
    if (phone) { await ev(`document.querySelector(".pt-trade-bar").click(); true`); await sleep(150); }
    await ev(`document.querySelector('.pt-segmented [data-side="sell"]').click(); true`);
    check(`${tag} Sell: Max equals shares held`, await ev(`(document.querySelector(".pt-max").click(), document.getElementById("pt-shares").value === "3")`));
    check(`${tag} Sell: estimate says proceeds`, await ev(`document.querySelector(".pt-estimate span").textContent === "Estimated proceeds"`));
    await ev(`document.getElementById("pt-shares").focus(); document.getElementById("pt-shares").select(); true`); await typeText("2");
    await key("Enter", "Enter", 13);
    await waitFor(`document.getElementById("pt-ticket-title").textContent === "Check your practice order"`);
    await ev(`document.querySelector(".pt-confirm").click(); true`);
    await waitFor(`document.getElementById("pt-ticket-title").textContent === "Order queued"`);
    if (phone) { await key("Escape", "Escape", 27); await sleep(100); }
    await ev(`document.querySelector('[data-key="next-1"]').click(); true`);
    check(`${tag} Sell fills with a toast`, await waitFor(`!!document.querySelector(".pt-toast") && document.querySelector(".pt-toast").textContent.startsWith("Sold 2 ${want}")`));
    check(`${tag} position drops to 1 share`, await waitFor(`(document.querySelector('tr[data-symbol="${want}"] td:nth-child(2)') || {}).textContent === "1"`));
    check(`${tag} realized P/L in history`, await ev(`[...document.querySelectorAll(".pt-history-list li")].some(li => li.textContent.includes("Sold 2 ${want}") && li.textContent.includes("Realized"))`));
    check(`${tag} scenario notice shows market label`, await ev(`document.querySelector(".pt-notice").textContent.includes("Synthetic practice market ${scenario === "synthetic-b" ? "B" : "A"}")`));
    // reload keeps the session (saved-session compatibility)
    await send("Page.reload", {}, s);
    check(`${tag} reload restores session`, await waitFor(`!!document.querySelector(".pt-day-line") && document.querySelector(".pt-day-line").textContent.startsWith("Day 8 of")`));
    // switch markets from the More menu, after confirming
    await waitFor(`document.getElementById("paper-root").getAttribute("aria-busy") === "false" && !!document.querySelector(".pt-chart-canvas canvas")`);
    await ev(`document.querySelector('[data-key="more"]').click(); document.querySelector('[data-key="change"]').click(); true`);
    check(`${tag} change-market asks first`, await ev(`document.querySelector(".pt-confirm-reset").textContent.startsWith("Change the practice market?") && document.activeElement.textContent === "Keep my session"`));
    await ev(`[...document.querySelectorAll(".pt-confirm-reset button")].find(b => b.textContent === "Yes, change market").click(); true`);
    check(`${tag} change-market returns to start, session cleared`, await waitFor(`!!document.querySelector(".pt-start-button") && localStorage.getItem("paper-session-v1") === null && document.activeElement.id === "paper-title"`));
  }
  check("journal text never sent", !posts.some(p => p.includes("SECRET-JOURNAL")), `${posts.length} POST bodies`);
  check("only the local server contacted", [...hosts].every(h => h === new URL(BASE).host), [...hosts].join(","));
  check("no console errors", errors.length === 0, errors.join(" | "));
  // desktop keyboard tab order reaches every ticket control
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false }, s);
  await send("Page.reload", {}, s); await waitFor(`!!document.querySelector(".pt-start-button")`); await ev(`document.querySelector(".pt-start-button").click(); true`); await waitFor(`!!document.querySelector(".pt-day-line") && !!document.querySelector(".pt-spark-box")`); await sleep(500);
  await ev(`document.querySelector(".pt-watch summary").focus(); true`);
  const seen = [];
  for (let i = 0; i < 80; i++) { await key("Tab", "Tab", 9); seen.push(await focused()); }
  check("Tab reaches ticker, shares, Max, Preview", ["pt-ticker", "pt-shares", "Max", "preview", "more"].every(k => seen.includes(k)), seen.slice(0, 80).join(" > "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
