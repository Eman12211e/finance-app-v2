// Finance App V2 QA suite: panes. P4 step 5: RSI and MACD panes against the analysis API, Not enough data, weekly rules.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/panes.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const errors = [], hosts = new Set();
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pend[m.id]) return pend[m.id](m.result || m);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.args.map(a => a.value).join(" "));
  if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) hosts.add(new URL(m.params.request.url).host);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => results.push([ok ? "PASS" : "FAIL", name, String(detail).slice(0, 240)]);

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  for (const d of ["Runtime", "Network", "Page"]) await send(d + ".enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(e.slice(0, 80) + " -> " + JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const key = async (k, code, vk, shift) => { for (const t of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type: t, key: k, code, windowsVirtualKeyCode: vk, modifiers: shift ? 8 : 0 }, s); await sleep(60); };
  const waitFor = async (expr, ms = 6000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(80); } return false; };
  const shotEl = async (name, sel) => { const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "start" }); const b = e.getBoundingClientRect(); return { x: b.left + scrollX, y: Math.max(0, b.top + scrollY - 8), w: b.width, h: b.height + 16 }; })()`); await sleep(300); const sh = await send("Page.captureScreenshot", { format: "png", clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(sh.data, "base64")); };
  const shot = async name => { const r = await send("Page.captureScreenshot", { format: "png" }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64")); };
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
    await ev(`(() => { const b = document.querySelector('.pt-watch-item[data-symbol="SYN-TEC1"]'); b.click(); const c = document.querySelector(".pt-ticket.pt-open .pt-sheet-close"); if (c) c.click(); return true; })()`);
    await waitFor(`document.getElementById("pt-chart-title").textContent.startsWith("SYN-TEC1") && !!document.querySelector(".pt-chart-canvas canvas")`);
    await sleep(200);
  };
  const shown = () => ev(`[...document.querySelectorAll(".pt-line-legend li")].map(li => li.textContent)`);
  // the API's own values for the same request, formatted the way the page should show them
  const expected = timeframe => ev(`(async () => {
    const indicators = JSON.parse(localStorage.getItem("paper-indicators-v1"));
    const r = await fetch("/api/analysis/indicators", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: JSON.parse(localStorage.getItem("paper-session-v1")), symbol: "SYN-TEC1", timeframe: "${timeframe}", indicators }) }).then(r => r.json());
    const bars = r.data.bars, at = bars[bars.length - 1].status === "partial" ? bars.length - 2 : bars.length - 1;
    const f = (v, d, pre) => v === null || at < 0 ? "Not enough data" : pre + v.toFixed(d);
    return r.data.indicators.map(i => {
      const name = i.type.toUpperCase() + " " + [].concat(i.period).join("-");
      if (i.type === "rsi") return name + " " + f(i.series.rsi[at], 1, "");
      if (i.type === "macd") return name + " MACD " + f(i.series.macd[at], 2, "") + ", signal " + f(i.series.signal[at], 2, "") + ", histogram " + f(i.series.histogram[at], 2, "");
      return name + " " + f(i.series[i.type][at], 2, "$");
    });
  })()`);
  const ALL = [{ type: "sma", period: 20 }, { type: "ema", period: 12 }, { type: "rsi", period: 14 }, { type: "macd", period: [12, 26, 9] }];

  await send("Page.navigate", { url: base + "/" }, s); await sleep(800);

  // ---------- day 41, desktop light: the menu and each pane ----------
  await seed(40, []);
  await open(1280, "light");
  const h0 = await ev(`document.querySelector(".pt-chart-canvas").getBoundingClientRect().height`);
  await ev(`document.querySelector('[data-key="ind-button"]').click(); true`); await sleep(150);
  check("menu: four lines and two panes, in two groups", JSON.stringify(await ev(`[...document.querySelectorAll(".pt-ind-row")].map(r => r.textContent.trim())`)) === JSON.stringify(["SMA 20", "SMA 50", "EMA 12", "EMA 26", "RSI 14", "MACD 12-26-9"]) && (await ev(`[...document.querySelectorAll(".pt-ind-group legend")].map(l => l.textContent).join(" | ")`)) === "On the price (2 at most) | Below the chart (2 at most)");
  await ev(`document.querySelector('[data-key="ind-rsi-14"]').click(); true`);
  await waitFor(`document.querySelectorAll(".pt-line-legend li").length === 1 && !!document.querySelector(".pt-chart-canvas.pt-panes-1 canvas")`);
  const h1 = await ev(`document.querySelector(".pt-chart-canvas").getBoundingClientRect().height`);
  check("RSI on: one pane, chart grows", h1 > h0 * 1.25, `${h0} -> ${h1}`);
  check("RSI value equals API (1 decimal)", JSON.stringify(await shown()) === JSON.stringify(await expected("daily")), (await shown()).join(" / "));
  await ev(`document.querySelector('[data-key="ind-macd-12-26-9"]').click(); true`);
  await waitFor(`document.querySelectorAll(".pt-line-legend li").length === 2 && !!document.querySelector(".pt-chart-canvas.pt-panes-2 canvas")`);
  const h2 = await ev(`document.querySelector(".pt-chart-canvas").getBoundingClientRect().height`);
  check("MACD on too: two panes, chart grows again", h2 > h1 * 1.1, `${h1} -> ${h2}`);
  check("RSI and MACD values equal API", JSON.stringify(await shown()) === JSON.stringify(await expected("daily")), (await shown()).join(" / "));
  for (const k of ["sma-20", "ema-12"]) { await ev(`document.querySelector('[data-key="ind-${k}"]').click(); true`); await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`); await sleep(150); }
  await waitFor(`document.querySelectorAll(".pt-line-legend li").length === 4`);
  check("two lines and two panes together", (await ev(`document.querySelector(".pt-tool-note").textContent`)) === "2 of 2 lines on the price, 2 of 2 panes" && (await ev(`document.querySelector('[data-key="ind-button"]').textContent`)) === "Indicators (4)");
  check("all four values equal API", JSON.stringify(await shown()) === JSON.stringify(await expected("daily")), (await shown()).join(" / "));
  check("line limit still enforced", await ev(`document.querySelector('[data-key="ind-sma-50"]').disabled && document.querySelector('[data-key="ind-ema-26"]').disabled && !document.querySelector('[data-key="ind-rsi-14"]').disabled`));
  check("readout carries pane values", await ev(`(() => { const t = document.querySelector(".pt-chart-legend").textContent; return /RSI 14 \\d+\\.\\d\\./.test(t) && /MACD 12-26-9 MACD -?\\d+\\.\\d\\d, signal -?\\d+\\.\\d\\d, histogram -?\\d+\\.\\d\\d\\./.test(t); })()`), await ev(`document.querySelector(".pt-chart-legend").textContent`));
  check("summary describes the panes", await ev(`document.querySelector(".pt-chart-summary").textContent.includes("Panes below the price: RSI 14 (0 to 100, guides at 30 and 70)")`));
  check("saved in this browser", (await ev(`localStorage.getItem("paper-indicators-v1")`)) === JSON.stringify([{ type: "sma", period: 20 }, { type: "ema", period: 12 }, { type: "rsi", period: 14 }, { type: "macd", period: [12, 26, 9] }]));
  await key("Escape", "Escape", 27);
  // the crosshair is shared: hovering low in the chart (the MACD pane) moves the readout's date
  const r = await ev(`(() => { const c = document.querySelector(".pt-chart-canvas"); c.scrollIntoView({ block: "center" }); const b = c.getBoundingClientRect(); return { l: b.left, w: b.width, y: b.top + b.height * 0.9 }; })()`);
  const before = await ev(`document.querySelector(".pt-chart-legend").textContent`);
  let moved = false;
  for (let f = 0.05; f < 0.9 && !moved; f += 0.03) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: r.l + r.w * f, y: r.y }, s); await sleep(50); moved = (await ev(`document.querySelector(".pt-chart-legend").textContent`)) !== before; }
  check("crosshair in the MACD pane drives the readout", moved, await ev(`document.querySelector(".pt-chart-legend").textContent`));
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 2, y: 2 }, s);
  check("no horizontal overflow (1280)", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await shotEl("chart-4-indicators-1280-light", ".pt-chart");
  await ev(`document.querySelector('[data-key="ind-button"]').click(); true`); await sleep(150);
  await shot("menu-1280-light");
  await key("Escape", "Escape", 27);
  // theme toggle repaints and keeps the panes; reload keeps them
  const px = `(() => { const c = document.querySelector(".pt-chart-canvas canvas"); const d = c.getContext("2d").getImageData(4, 4, 1, 1).data; return [d[0], d[1], d[2]].join(","); })()`;
  const p0 = await ev(px);
  await ev(`document.documentElement.setAttribute("data-theme", "dark"); true`); await sleep(400);
  check("theme toggle repaints, panes kept", (await ev(px)) !== p0 && (await ev(`!!document.querySelector(".pt-chart-canvas.pt-panes-2 canvas")`)));
  await ev(`document.documentElement.removeAttribute("data-theme"); true`);
  await send("Page.reload", {}, s); await waitFor(`document.querySelectorAll(".pt-line-legend li").length === 4`, 8000);
  check("reload keeps both panes", await ev(`!!document.querySelector(".pt-chart-canvas.pt-panes-2")`));

  // ---------- insufficient history ----------
  await seed(10, ALL); await open(1280, "light");
  check("day 11: RSI and MACD say Not enough data", JSON.stringify((await shown()).slice(2)) === JSON.stringify(["RSI 14 Not enough data", "MACD 12-26-9 MACD Not enough data, signal Not enough data, histogram Not enough data"]), (await shown()).join(" / "));
  await seed(20, ALL); await open(1280, "light");
  const d21 = await shown();
  check("day 21: RSI has a value, MACD still Not enough data", /^RSI 14 \d+\.\d$/.test(d21[2]) && d21[3] === "MACD 12-26-9 MACD Not enough data, signal Not enough data, histogram Not enough data" && JSON.stringify(d21) === JSON.stringify(await expected("daily")), d21.join(" / "));

  // ---------- weekly, day 161: completed weeks only ----------
  await seed(160, ALL); await open(1280, "dark");
  await shotEl("chart-4-indicators-1280-dark", ".pt-chart");
  await ev(`document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`document.querySelector(".pt-chart-legend").textContent.startsWith("Partial Week") && document.querySelectorAll(".pt-line-legend li").length === 4`);
  const wk = await shown();
  check("weekly values equal the API's last completed week", JSON.stringify(wk) === JSON.stringify(await expected("weekly")), wk.join(" / "));
  check("weekly MACD signal: Not enough data (7 of 9)", /MACD 12-26-9 MACD \d+\.\d\d, signal Not enough data, histogram Not enough data/.test(wk[3]), wk[3]);
  check("Partial Week readout: panes not calculated", await ev(`document.querySelector(".pt-chart-legend").textContent.includes("RSI 14 not calculated for a Partial Week") && document.querySelector(".pt-chart-legend").textContent.includes("MACD 12-26-9 not calculated for a Partial Week")`));
  await shotEl("chart-weekly-1280-dark", ".pt-chart");
  await ev(`document.querySelector('[data-key="tf-daily"]').click(); true`);
  await waitFor(`!document.querySelector(".pt-chart-legend").textContent.startsWith("Partial") && document.querySelectorAll(".pt-line-legend li").length === 4`);
  check("back to Daily keeps the panes", await ev(`!!document.querySelector(".pt-chart-canvas.pt-panes-2 canvas")`));

  // ---------- phone ----------
  await open(390, "light");
  check("phone: no horizontal overflow with two panes", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await shotEl("chart-4-indicators-390-light", ".pt-chart");
  await ev(`(() => { const b = document.querySelector('[data-key="ind-button"]'); b.scrollIntoView({ block: "center" }); b.click(); return true; })()`); await sleep(200);
  check("phone: sheet lists all six presets", (await ev(`document.getElementById("pt-ind-menu").getAttribute("aria-modal") === "true" && document.querySelectorAll("#pt-ind-menu .pt-ind-row").length === 6`)));
  await shot("menu-sheet-390-light");
  await ev(`document.querySelector('[data-key="ind-done"]').click(); true`);
  await open(390, "dark"); await shotEl("chart-4-indicators-390-dark", ".pt-chart");

  // ---------- Reset clears everything ----------
  await open(1280, "light");
  await ev(`document.querySelector('[data-key="more"]').click(); document.querySelector('[data-key="reset"]').click(); true`); await sleep(100);
  await ev(`[...document.querySelectorAll(".pt-confirm-reset button")].find(b => b.textContent === "Yes, reset").click(); true`);
  await waitFor(`document.querySelector(".pt-day-line").textContent.startsWith("Day 1 of") && !!document.querySelector(".pt-chart-canvas canvas")`);
  check("Reset turns every indicator off", (await ev(`localStorage.getItem("paper-indicators-v1")`)) === null && (await ev(`!!document.querySelector(".pt-chart-canvas.pt-panes-0")`)));
  check("only the local server was contacted", [...hosts].every(h => h.startsWith("127.0.0.1")), [...hosts].join(","));
  check("no console errors or warnings", errors.length === 0, errors.join(" | "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
