// Finance App V2 QA suite: overlays. P4 step 4: SMA and EMA overlays against the analysis API, two-line limit, Daily/Weekly, redraws, saved choices, phone sheet.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/overlays.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const errors = [], posts = [], hosts = new Set();
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pend[m.id]) return pend[m.id](m.result || m);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.args.map(a => a.value).join(" "));
  if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) { hosts.add(new URL(m.params.request.url).host); if (m.params.request.postData) posts.push(m.params.request.postData); }
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => results.push([ok ? "PASS" : "FAIL", name, String(detail).slice(0, 220)]);

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  for (const d of ["Runtime", "Network", "Page"]) await send(d + ".enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(e.slice(0, 80) + " -> " + JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const key = async (k, code, vk, shift) => { const text = k === "Enter" ? "\r" : k === " " ? " " : undefined; for (const t of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type: t, key: k, code, windowsVirtualKeyCode: vk, modifiers: shift ? 8 : 0, text: t === "keyDown" ? text : undefined }, s); await sleep(60); };
  const waitFor = async (expr, ms = 6000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(80); } return false; };
  const shot = async name => { const r = await send("Page.captureScreenshot", { format: "png" }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64")); };
  const shotEl = async (name, sel) => { const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "start" }); const b = e.getBoundingClientRect(); return { x: b.left + scrollX, y: Math.max(0, b.top + scrollY - 8), w: b.width, h: b.height + 16 }; })()`); await sleep(250); const sh = await send("Page.captureScreenshot", { format: "png", clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(sh.data, "base64")); };
  const seed = async (scenario, days) => ev(`(async () => {
    const post = (a, b) => fetch("/api/paper/" + a, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()).then(j => j.data);
    let st = (await post("new", { scenario: "${scenario}" })).state;
    for (let d = 0; d < ${days}; d++) {
      if (d === 30) st = (await post("confirm", { state: st, order: { id: "order-ovl-0001", symbol: "SYN-TEC1", side: "buy", shares: 5 } })).state;
      st = (await post("advance", { state: st, expected_day: d })).state;
    }
    localStorage.clear(); localStorage.setItem("fe_profile", JSON.stringify({ age_range: "25-34", risk: "medium" }));
    localStorage.setItem("paper-session-v1", JSON.stringify(st)); return true; })()`);
  const open = async (width, theme) => {
    await send("Emulation.setDeviceMetricsOverride", { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 }, s);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, s);
    await send("Page.navigate", { url: "about:blank" }, s); await sleep(100);
    await send("Page.navigate", { url: base + "/#practice" }, s);
    await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`, 8000);
  };
  const pick = async sym => { await ev(`document.querySelector('.pt-watch-item[data-symbol="${sym}"]').click(); true`); await sleep(100); if (await ev(`!!document.querySelector(".pt-ticket.pt-open")`)) await ev(`document.querySelector(".pt-sheet-close").click(); true`); await waitFor(`document.getElementById("pt-chart-title").textContent.startsWith("${sym}") && !!document.querySelector(".pt-chart-canvas canvas")`); };
  const setOverlays = async list => {  // through the UI: open the menu, untick everything, tick the list in order
    await ev(`(() => { const m = document.getElementById("pt-ind-menu"); if (m.hidden) document.querySelector('[data-key="ind-button"]').click(); return true; })()`);
    for (const k of ["sma-20", "sma-50", "ema-12", "ema-26"]) {
      if (await ev(`document.querySelector('[data-key="ind-${k}"]').checked`)) { await ev(`document.querySelector('[data-key="ind-${k}"]').click(); true`); await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`); }
    }
    for (const k of list) { await ev(`document.querySelector('[data-key="ind-${k}"]').click(); true`); await waitFor(`!!document.querySelector(".pt-chart-canvas canvas") && document.querySelectorAll(".pt-line-legend li").length === ${list.indexOf(k) + 1}`); }
  };
  // what the page shows for each line, and what the API says for the same request
  const shown = () => ev(`[...document.querySelectorAll(".pt-line-legend li")].map(li => li.textContent)`);
  const expected = (symbol, timeframe, list) => ev(`(async () => {
    const indicators = ${JSON.stringify(list)}.map(k => ({ type: k.split("-")[0], period: Number(k.split("-")[1]) }));
    const r = await fetch("/api/analysis/indicators", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: JSON.parse(localStorage.getItem("paper-session-v1")), symbol: "${symbol}", timeframe: "${timeframe}", indicators }) }).then(r => r.json());
    const bars = r.data.bars, at = bars[bars.length - 1].status === "partial" ? bars.length - 2 : bars.length - 1;
    return { items: r.data.indicators.map(i => { const v = at >= 0 ? i.series[i.type][at] : null; return i.type.toUpperCase() + " " + i.period + " " + (v === null ? "Not enough data" : "$" + v.toFixed(2)); }), last: bars[bars.length - 1].time, n: bars.length };
  })()`);

  // ---------- desktop, day 41 (enough for SMA 20 / EMA 26, not SMA 50) ----------
  await send("Page.navigate", { url: base + "/" }, s); await sleep(800);
  await seed("synthetic-b", 40);
  await open(1280, "light");
  await pick("SYN-TEC1");
  check("default: every indicator off", await ev(`!document.querySelector(".pt-line-legend") && document.querySelector('[data-key="ind-button"]').textContent === "Indicators" && !document.querySelector(".pt-chart-summary").textContent.includes("Lines on the price")`));
  check("default: preference not stored", (await ev(`localStorage.getItem("paper-indicators-v1")`)) === null);
  await ev(`document.querySelector('[data-key="ind-button"]').focus(); true`); await key("Enter", "Enter", 13); await sleep(150);
  check("menu opens by keyboard, focus on first checkbox", await ev(`document.querySelector('[data-key="ind-button"]').getAttribute("aria-expanded") === "true" && !document.getElementById("pt-ind-menu").hidden && document.activeElement.dataset.key === "ind-sma-20"`));
  check("menu lists exactly the four presets", JSON.stringify(await ev(`[...document.querySelectorAll(".pt-ind-row")].map(r => r.textContent.trim()).slice(0, 4)`)) === JSON.stringify(["SMA 20", "SMA 50", "EMA 12", "EMA 26"]));
  await key(" ", "Space", 32);
  await waitFor(`document.querySelectorAll(".pt-line-legend li").length === 1`);
  check("space ticks SMA 20; focus stays on it; menu stays open", await ev(`document.activeElement.dataset.key === "ind-sma-20" && document.activeElement.checked && !document.getElementById("pt-ind-menu").hidden`));
  for (const [list, label] of [[["sma-20"], "SMA 20"], [["sma-50"], "SMA 50"], [["ema-12"], "EMA 12"], [["ema-26"], "EMA 26"]]) {
    await setOverlays(list);
    const exp = await expected("SYN-TEC1", "daily", list), got = await shown();
    check(`daily ${label}: legend equals API`, JSON.stringify(got) === JSON.stringify(exp.items), got.join(" / ") + " vs " + exp.items.join(" / "));
  }
  await setOverlays(["sma-50"]);
  check("SMA 50 on day 41: Not enough data, nothing drawn", (await shown())[0] === "SMA 50 Not enough data" && (await ev(`document.querySelector(".pt-chart-summary").textContent.includes("SMA 50 (solid) Not enough data")`)));
  await setOverlays(["sma-20", "ema-12"]);
  check("two overlays: first solid, second dashed", await ev(`(() => { const s = document.querySelectorAll(".pt-line-legend .pt-swatch"); return s.length === 2 && !s[0].classList.contains("pt-swatch-b") && s[1].classList.contains("pt-swatch-b"); })()`));
  check("limit: the other two are disabled with the note", await ev(`document.querySelector('[data-key="ind-sma-50"]').disabled && document.querySelector('[data-key="ind-ema-26"]').disabled && document.getElementById("pt-ind-limit").textContent.startsWith("Two lines are already")`));
  check("button and note count the lines", await ev(`document.querySelector('[data-key="ind-button"]').textContent === "Indicators (2)" && document.querySelector(".pt-tool-note").textContent === "2 of 2 lines on the price, 0 of 2 panes"`));
  const exp2 = await expected("SYN-TEC1", "daily", ["sma-20", "ema-12"]);
  check("two overlays: values equal API", JSON.stringify(await shown()) === JSON.stringify(exp2.items), (await shown()).join(" / "));
  const today = await ev(`document.querySelector(".pt-day-line").textContent.split(" ").slice(4).join(" ")`);
  check("no future: the chart's last bar is today", new Date(exp2.last + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) === today && exp2.n === 41, exp2.last + " vs " + today + " n=" + exp2.n);
  check("readout ends on today with line values", await ev(`document.querySelector(".pt-chart-legend").textContent.startsWith(${JSON.stringify(new Date(exp2.last + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }))}) && document.querySelector(".pt-chart-legend").textContent.includes(" SMA 20 $") && document.querySelector(".pt-chart-legend").textContent.includes(" EMA 12 $")`), await ev(`document.querySelector(".pt-chart-legend").textContent`));
  check("preference stored in this browser", (await ev(`localStorage.getItem("paper-indicators-v1")`)) === JSON.stringify([{ type: "sma", period: 20 }, { type: "ema", period: 12 }]));
  await key("Escape", "Escape", 27); await sleep(100);
  check("Escape closes the menu and returns focus", await ev(`document.getElementById("pt-ind-menu").hidden && document.activeElement.dataset.key === "ind-button"`));
  await ev(`document.querySelector('[data-key="ind-button"]').click(); true`); await sleep(100);
  await shot("ovl-menu-1280-light");
  await ev(`document.querySelector(".pt-notice").click(); true`); await sleep(100);
  check("a click elsewhere closes the menu", await ev(`document.getElementById("pt-ind-menu").hidden`));
  // crosshair readout carries line values
  const box = await ev(`(() => { document.querySelector(".pt-chart-canvas").scrollIntoView({ block: "center" }); const r = document.querySelector(".pt-chart-canvas").getBoundingClientRect(); return { l: r.left, w: r.width, y: r.top + r.height * 0.4 }; })()`);
  const before = await ev(`document.querySelector(".pt-chart-legend").textContent`);
  let moved = false;
  for (let f = 0.05; f < 0.95 && !moved; f += 0.03) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.l + box.w * f, y: box.y }, s); await sleep(50); moved = (await ev(`document.querySelector(".pt-chart-legend").textContent`)) !== before; }
  const hovered = await ev(`document.querySelector(".pt-chart-legend").textContent`);
  check("crosshair readout shows line values or Not enough data", moved && /SMA 20 (\$[\d.]+|Not enough data)/.test(hovered) && /EMA 12 (\$[\d.]+|Not enough data)/.test(hovered), hovered);
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 2, y: 2 }, s);
  // ticker change keeps the overlays and refetches
  await pick("SYN-FIN1");
  const expFin = await expected("SYN-FIN1", "daily", ["sma-20", "ema-12"]);
  check("ticker change: overlays kept, values for the new ticker", JSON.stringify(await shown()) === JSON.stringify(expFin.items), (await shown()).join(" / "));
  // advancing a day redraws with the new day's values
  await ev(`document.querySelector('[data-key="next-1"]').click(); true`);
  await waitFor(`document.querySelector(".pt-day-line").textContent.startsWith("Day 42 of")`);
  await waitFor(`!!document.querySelector(".pt-chart-canvas canvas") && document.querySelectorAll(".pt-line-legend li").length === 2`);
  await sleep(300);
  const expNext = await expected("SYN-FIN1", "daily", ["sma-20", "ema-12"]);
  check("next day: values follow the new day", JSON.stringify(await shown()) === JSON.stringify(expNext.items) && expNext.n === 42, (await shown()).join(" / ") + " n=" + expNext.n);
  // theme toggle redraws the canvas, lines kept
  const px = `(() => { const c = document.querySelector(".pt-chart-canvas canvas"); const d = c.getContext("2d").getImageData(4, 4, 1, 1).data; return [d[0], d[1], d[2]].join(","); })()`;
  const lightPx = await ev(px);
  await ev(`document.documentElement.setAttribute("data-theme", "dark"); true`); await sleep(400);
  check("theme toggle repaints the chart and keeps the lines", (await ev(px)) !== lightPx && (await shown()).length === 2, lightPx + " -> " + await ev(px));
  await ev(`document.documentElement.removeAttribute("data-theme"); true`); await sleep(300);
  // reload keeps the preference; Reset clears it
  await send("Page.reload", {}, s); await waitFor(`!!document.querySelector(".pt-chart-canvas canvas") && document.querySelectorAll(".pt-line-legend li").length === 2`, 8000);
  check("reload keeps the chosen overlays", (await shown()).length === 2);

  // ---------- weekly, day 161 (Thursday: Partial Week) ----------
  await seed("synthetic-b", 160);
  await ev(`localStorage.setItem("paper-indicators-v1", JSON.stringify([{ type: "sma", period: 20 }, { type: "ema", period: 12 }])); true`);
  await open(1280, "dark");
  await pick("SYN-TEC1");
  await shotEl("ovl-daily-1280-dark", ".pt-chart");
  await ev(`document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`document.querySelector(".pt-chart-legend").textContent.startsWith("Partial Week") && document.querySelectorAll(".pt-line-legend li").length === 2`);
  const expW = await expected("SYN-TEC1", "weekly", ["sma-20", "ema-12"]);
  check("weekly: legend equals the API's last completed week", JSON.stringify(await shown()) === JSON.stringify(expW.items), (await shown()).join(" / ") + " vs " + expW.items.join(" / "));
  check("weekly: Partial Week readout has no line values", await ev(`document.querySelector(".pt-chart-legend").textContent.includes("SMA 20 not calculated for a Partial Week") && document.querySelector(".pt-chart-summary").textContent.includes("Weekly lines use completed weeks only.")`), await ev(`document.querySelector(".pt-chart-legend").textContent`));
  await shotEl("ovl-weekly-1280-dark", ".pt-chart");
  // SMA 50 weekly: 32 completed weeks -> Not enough data
  await setOverlays(["sma-50"]);
  check("weekly SMA 50 on day 161: Not enough data", (await shown())[0] === "SMA 50 Not enough data");
  await setOverlays(["sma-20", "ema-12"]);
  await key("Escape", "Escape", 27);
  check("no horizontal overflow (1280)", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);

  // ---------- phone 390: the menu is a bottom sheet ----------
  await ev(`document.querySelector('[data-key="tf-daily"]').click(); true`); await sleep(300);
  await open(390, "light");
  await pick("SYN-TEC1");
  await ev(`(() => { const b = document.querySelector('[data-key="ind-button"]'); b.scrollIntoView({ block: "center" }); b.focus(); b.click(); return true; })()`); await sleep(200);
  check("phone: menu is a modal sheet", await ev(`(() => { const m = document.getElementById("pt-ind-menu"); const r = m.getBoundingClientRect(); return m.getAttribute("role") === "dialog" && m.getAttribute("aria-modal") === "true" && Math.abs(r.bottom - innerHeight) < 2 && r.left === 0; })()`));
  let escaped = false;
  for (let k = 0; k < 10; k++) { await key("Tab", "Tab", 9); if (!(await ev(`document.getElementById("pt-ind-menu").contains(document.activeElement)`))) escaped = true; }
  check("phone: Tab stays in the sheet", !escaped);
  await shot("ovl-sheet-390-light");
  await ev(`document.querySelector('[data-key="ind-done"]').click(); true`); await sleep(150);
  check("phone: Done closes and returns focus", await ev(`document.getElementById("pt-ind-menu").hidden && document.activeElement.dataset.key === "ind-button"`));
  check("phone: no horizontal overflow", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await shotEl("ovl-daily-390-light", ".pt-chart");
  await open(390, "dark"); await pick("SYN-TEC1"); await shotEl("ovl-daily-390-dark", ".pt-chart");

  // ---------- Reset clears the overlays ----------
  await open(1280, "light");
  await ev(`document.querySelector('[data-key="more"]').click(); document.querySelector('[data-key="reset"]').click(); true`); await sleep(100);
  await ev(`[...document.querySelectorAll(".pt-confirm-reset button")].find(b => b.textContent === "Yes, reset").click(); true`);
  await waitFor(`document.querySelector(".pt-day-line").textContent.startsWith("Day 1 of") && !!document.querySelector(".pt-chart-canvas canvas")`);
  check("Reset clears the overlays (all off)", (await ev(`localStorage.getItem("paper-indicators-v1")`)) === null && !(await ev(`!!document.querySelector(".pt-line-legend")`)));
  check("only the local server was contacted", [...hosts].every(h => h.startsWith("127.0.0.1")), [...hosts].join(","));
  check("indicator choices only ever sent inside chart requests", posts.filter(p => p.includes('"indicators"')).every(p => p.includes('"timeframe"')));
  check("no console errors or warnings", errors.length === 0, errors.join(" | "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
