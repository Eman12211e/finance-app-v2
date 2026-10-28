// Finance App V2 QA suite: explanations. P4 step 6: explanation cards, Learn more, What is this?, Not enough data, Partial Week and Final Short Week sentences.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/explanations.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const errors = [], hosts = new Set(), posts = [];
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pend[m.id]) return pend[m.id](m.result || m);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.args.map(a => a.value).join(" "));
  if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) { hosts.add(new URL(m.params.request.url).host); if (m.params.request.url.includes("/api/analysis/indicators")) posts.push(m.params.request.postData); }
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => results.push([ok ? "PASS" : "FAIL", name, String(detail).slice(0, 260)]);

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  for (const d of ["Runtime", "Network", "Page"]) await send(d + ".enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(e.slice(0, 80) + " -> " + JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const key = async (k, code, vk) => { const text = k === "Enter" ? String.fromCharCode(13) : k === " " ? " " : undefined; for (const t of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type: t, key: k, code, windowsVirtualKeyCode: vk, text: t === "keyDown" ? text : undefined }, s); await sleep(80); };
  const waitFor = async (expr, ms = 7000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(80); } return false; };
  const shotEl = async (name, sel) => { const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "start" }); const b = e.getBoundingClientRect(); return { x: b.left + scrollX, y: Math.max(0, b.top + scrollY - 8), w: b.width, h: b.height + 16 }; })()`); await sleep(300); const sh = await send("Page.captureScreenshot", { format: "png", clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(sh.data, "base64")); };
  const shot = async name => { const r = await send("Page.captureScreenshot", { format: "png" }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64")); };
  const ALL = [{ type: "sma", period: 20 }, { type: "ema", period: 12 }, { type: "rsi", period: 14 }, { type: "macd", period: [12, 26, 9] }];
  const seed = async (days, indicators) => ev(`(async () => {
    const post = (a, b) => fetch("/api/paper/" + a, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()).then(j => j.data);
    let st = (await post("new", { scenario: "synthetic-b" })).state;
    for (let d = 0; d < ${days}; d++) st = (await post("advance", { state: st, expected_day: d })).state;
    localStorage.clear(); localStorage.setItem("fe_profile", JSON.stringify({ age_range: "25-34", risk: "medium" }));
    localStorage.setItem("paper-session-v1", JSON.stringify(st));
    localStorage.setItem("paper-indicators-v1", ${JSON.stringify(JSON.stringify(indicators))}); return true; })()`);
  const open = async (width, theme) => {
    await send("Emulation.setDeviceMetricsOverride", { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 }, s);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, s);
    await send("Page.navigate", { url: "about:blank" }, s); await sleep(100);
    await send("Page.navigate", { url: base + "/#practice" }, s);
    await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`, 8000);
    await ev(`(() => { document.querySelector('.pt-watch-item[data-symbol="SYN-TEC1"]').click(); const c = document.querySelector(".pt-ticket.pt-open .pt-sheet-close"); if (c) c.click(); return true; })()`);
    await waitFor(`document.getElementById("pt-chart-title").textContent.startsWith("SYN-TEC1") && !!document.querySelector(".pt-chart-canvas canvas") && !!document.querySelector(".pt-learn-more .pt-explain dl")`);
    await sleep(150);
  };
  const cards = () => ev(`[...document.querySelectorAll(".pt-card")].map(c => ({ head: c.querySelector("h4").textContent.trim(), now: c.querySelector(".pt-card-now").textContent, foot: c.querySelector(":scope > .pt-edu-note").textContent, labelled: !!document.getElementById(c.getAttribute("aria-labelledby")) }))`);
  const apiReadings = timeframe => ev(`(async () => {
    const r = await fetch("/api/analysis/indicators", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: JSON.parse(localStorage.getItem("paper-session-v1")), symbol: "SYN-TEC1", timeframe: "${timeframe}", indicators: JSON.parse(localStorage.getItem("paper-indicators-v1")) }) }).then(r => r.json());
    return r.data.indicators.map(i => i.reading); })()`);

  await send("Page.navigate", { url: base + "/" }, s); await sleep(800);

  // ---------- day 161, all four, desktop light ----------
  await seed(160, ALL); await open(1280, "light");
  const c = await cards();
  check("one card per active indicator, in order", c.length === 4);
  check("headings: name, period and line style", JSON.stringify(c.map(x => x.head)) === JSON.stringify(["SMA 20 (solid line) Simulated", "EMA 12 (dashed line) Simulated", "RSI 14 (line in the RSI pane, guides at 30 and 70) Simulated", "MACD 12-26-9 (MACD solid line, signal dashed line, histogram bars) Simulated"]), c.map(x => x.head).join(" | "));
  const api = await apiReadings("daily");
  check("readings equal the API's", JSON.stringify(c.map(x => x.now)) === JSON.stringify(api), c.map(x => x.now).join(" | "));
  check("approved day-161 sentences", c[0].now === "The latest close, $199.96, is above its 20-day average of $189.99." && c[3].now.endsWith("The gap between them widened since the previous day."));
  check("every card: footer and a labelled region", c.every(x => x.foot === "Education only. An indicator describes past simulated prices; it is not a recommendation to buy or sell." && x.labelled));
  check("Learn more closed by default", await ev(`[...document.querySelectorAll(".pt-learn-more")].every(d => !d.open)`));
  await ev(`document.querySelector('[data-key="learn-sma-20"]').focus(); true`); await key("Enter", "Enter", 13); await sleep(150);
  check("Learn more opens from the keyboard with the approved text", await ev(`(() => { const d = document.querySelector('[data-key="learn-sma-20"]').parentElement; const t = d.textContent; return d.open && t.includes("Our plain summary") && t.includes("The average of the last 20 closing prices: the last 20 simulated days") && t.includes("How people read it") && t.includes("Watch out"); })()`));
  check("Learn more has a specific accessible name", (await ev(`document.querySelector('[data-key="learn-sma-20"]').getAttribute("aria-label")`)) === "Learn more about SMA 20");
  await ev(`document.documentElement.setAttribute("data-theme", "dark"); true`); await sleep(500);
  check("Learn more stays open across a redraw (theme change)", await ev(`document.querySelector('[data-key="learn-sma-20"]').parentElement.open && document.activeElement.dataset.key === "learn-sma-20"`));
  await ev(`document.documentElement.removeAttribute("data-theme"); true`); await sleep(400);
  await shotEl("cards-1280-light", ".pt-cards");

  // What is this? on a preset that is off: SMA 50
  const postsBefore = posts.length, stored = await ev(`localStorage.getItem("paper-indicators-v1")`);
  await ev(`document.querySelector('[data-key="ind-button"]').click(); true`); await sleep(150);
  await ev(`document.querySelector('[data-key="what-sma-50"]').focus(); true`); await key("Enter", "Enter", 13); await sleep(200);
  check("What is this? opens the full explanation for an indicator that is off", await ev(`(() => { const b = document.querySelector('[data-key="what-sma-50"]'); const p = document.getElementById(b.getAttribute("aria-controls")); return b.getAttribute("aria-expanded") === "true" && !p.hidden && p.textContent.includes("The average of the last 50 closing prices") && p.textContent.includes("Watch out") && p.textContent.includes("not a recommendation"); })()`));
  check("…without switching it on", await ev(`!document.querySelector('[data-key="ind-sma-50"]').checked && document.querySelectorAll(".pt-card").length === 4`) && (await ev(`localStorage.getItem("paper-indicators-v1")`)) === stored && posts.length === postsBefore);
  check("What is this? has a specific accessible name", (await ev(`document.querySelector('[data-key="what-sma-50"]').getAttribute("aria-label")`)) === "What is SMA 50?");
  await shot("menu-what-1280-light");
  await ev(`document.querySelector('[data-key="what-macd-12-26-9"]').click(); true`); await sleep(150);
  check("opening another explanation closes the first", await ev(`document.querySelector('[data-key="what-sma-50"]').getAttribute("aria-expanded") === "false" && document.getElementById("pt-what-sma-50").hidden && !document.getElementById("pt-what-macd-12-26-9").hidden`));
  await ev(`document.querySelector('[data-key="what-macd-12-26-9"]').click(); true`); await sleep(100);
  check("…and pressing it again closes it", await ev(`document.getElementById("pt-what-macd-12-26-9").hidden`));
  await key("Escape", "Escape", 27);

  // weekly: prefix and Partial Week sentence, equal to the API
  await ev(`document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`[...document.querySelectorAll(".pt-card-now")].length === 4 && document.querySelector(".pt-card-now").textContent.startsWith("On the weekly view")`);
  const wk = (await cards()).map(x => x.now);
  check("weekly readings equal the API's, with the prefix and the Partial Week sentence", JSON.stringify(wk) === JSON.stringify(await apiReadings("weekly")) && wk.every(t => t.startsWith("On the weekly view (completed weeks only):") && t.endsWith("This week is a Partial Week: it is shown on the chart but not used in any weekly value until it completes.")), wk[3]);
  await shotEl("cards-weekly-1280-light", ".pt-cards");

  // ---------- dark, desktop ----------
  await open(1280, "dark");
  await ev(`document.querySelector('[data-key="learn-rsi-14"]').click(); true`); await sleep(150);
  await shotEl("cards-1280-dark", ".pt-cards");

  // ---------- Not enough data (day 11) ----------
  await seed(10, ALL); await open(1280, "light");
  const early = (await cards()).map(x => x.now);
  check("day 11: Not enough data sentences equal the API's", JSON.stringify(early) === JSON.stringify(await apiReadings("daily")) && early[0] === "SMA 20 needs 20 daily closes. This view has 11 so far, so it is not drawn yet." && early[3] === "MACD 12-26-9 needs 26 daily closes. This view has 11 so far, so it is not drawn yet.", early.join(" | "));

  // ---------- Final Short Week (day 250) ----------
  await seed(249, [{ type: "rsi", period: 14 }]); await open(1280, "light");
  await ev(`document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`!!document.querySelector(".pt-card-now") && document.querySelector(".pt-card-now").textContent.startsWith("On the weekly view")`);
  const fin = (await cards())[0].now;
  check("final day: Final Short Week sentence", fin.endsWith("The last week is the scenario's Final Short Week (3 trading days); it is complete and included.") && fin === (await apiReadings("weekly"))[0], fin);

  // ---------- phone ----------
  await seed(160, ALL); await open(390, "light");
  check("phone: cards stack in one column", await ev(`(() => { const c = [...document.querySelectorAll(".pt-card")].map(x => x.getBoundingClientRect().left); return c.length === 4 && new Set(c.map(Math.round)).size === 1; })()`));
  check("phone: no horizontal overflow", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await ev(`document.querySelector('[data-key="learn-macd-12-26-9"]').click(); true`); await sleep(150);
  await shotEl("cards-390-light", ".pt-cards");
  await ev(`(() => { const b = document.querySelector('[data-key="ind-button"]'); b.scrollIntoView({ block: "center" }); b.click(); return true; })()`); await sleep(200);
  await ev(`document.querySelector('[data-key="what-rsi-14"]').click(); true`); await sleep(200);
  check("phone: What is this? opens inside the sheet", await ev(`!document.getElementById("pt-what-rsi-14").hidden && document.getElementById("pt-ind-menu").contains(document.getElementById("pt-what-rsi-14"))`));
  await shot("menu-what-390-light");
  await ev(`document.querySelector('[data-key="ind-done"]').click(); true`);
  await open(390, "dark"); await shotEl("cards-390-dark", ".pt-cards");

  check("only the local server was contacted", [...hosts].every(h => h.startsWith("127.0.0.1")), [...hosts].join(","));
  check("no console errors or warnings", errors.length === 0, errors.join(" | "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
