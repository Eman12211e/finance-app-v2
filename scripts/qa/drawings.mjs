// Finance App V2 QA suite: drawings. P4 step 7: horizontal and trend lines by mouse, touch and keyboard; storage, weekly mapping, Remove, Clear (with confirmation), Reset and Change market.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/drawings.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const errors = [], hosts = new Set(), bodies = [];
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pend[m.id]) return pend[m.id](m.result || m);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || "exception");
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.args.map(a => a.value).join(" "));
  if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) { hosts.add(new URL(m.params.request.url).host); bodies.push((m.params.request.url || "") + " " + (m.params.request.postData || "")); }
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = []; const check = (name, ok, detail = "") => results.push([ok ? "PASS" : "FAIL", name, String(detail).slice(0, 260)]);

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  for (const d of ["Runtime", "Network", "Page"]) await send(d + ".enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(e.slice(0, 90) + " -> " + JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const key = async (k, code, vk) => { const text = k === "Enter" ? String.fromCharCode(13) : undefined; for (const t of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type: t, key: k, code, windowsVirtualKeyCode: vk, text: t === "keyDown" ? text : undefined }, s); await sleep(80); };
  const typeText = t => send("Input.insertText", { text: t }, s);
  const waitFor = async (expr, ms = 7000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr)) return true; await sleep(80); } return false; };
  const shotEl = async (name, sel) => { const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "start" }); const b = e.getBoundingClientRect(); return { x: b.left + scrollX, y: Math.max(0, b.top + scrollY - 8), w: b.width, h: b.height + 16 }; })()`); await sleep(300); const sh = await send("Page.captureScreenshot", { format: "png", clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(sh.data, "base64")); };
  const seed = async (days, scenario = "synthetic-b") => ev(`(async () => {
    const post = (a, b) => fetch("/api/paper/" + a, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()).then(j => j.data);
    let st = (await post("new", { scenario: "${scenario}" })).state;
    st = (await post("confirm", { state: st, order: { id: "order-draw-001", symbol: "SYN-TEC1", side: "buy", shares: 3 } })).state;
    for (let d = 0; d < ${days}; d++) st = (await post("advance", { state: st, expected_day: d })).state;
    localStorage.clear(); localStorage.setItem("fe_profile", JSON.stringify({ age_range: "25-34", risk: "medium" }));
    localStorage.setItem("paper-session-v1", JSON.stringify(st)); return true; })()`);
  const open = async (width, theme, symbol = "SYN-TEC1") => {
    await send("Emulation.setDeviceMetricsOverride", { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 }, s);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, s);
    await send("Page.navigate", { url: "about:blank" }, s); await sleep(100);
    await send("Page.navigate", { url: base + "/#practice" }, s);
    await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`, 8000);
    await pick(symbol);
  };
  const pick = async sym => {
    await ev(`(() => { document.querySelector('.pt-watch-item[data-symbol="${sym}"]').click(); const c = document.querySelector(".pt-ticket.pt-open .pt-sheet-close"); if (c) c.click(); return true; })()`);
    await waitFor(`document.getElementById("pt-chart-title").textContent.startsWith("${sym}") && !!document.querySelector(".pt-chart-canvas canvas") && !!document.getElementById("pt-drawings")`);
    await waitFor(`!document.getElementById("pt-tline-from").disabled`);
    await sleep(200);
  };
  const items = () => ev(`[...document.querySelectorAll("#pt-draw-list li span:nth-child(2)")].map(x => x.textContent)`);
  const stored = () => ev(`JSON.parse(localStorage.getItem("paper-drawings-v1") || "{}")`);
  const canvasPoint = async (fx, fy) => { const r = await ev(`(() => { const c = document.querySelector(".pt-chart-canvas"); c.scrollIntoView({ block: "center" }); const b = c.getBoundingClientRect(); return { x: b.left + b.width * ${fx}, y: b.top + b.height * ${fy} }; })()`); return r; };
  const clickAt = async (fx, fy) => { const p = await canvasPoint(fx, fy); for (const t of ["mouseMoved", "mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type: t, x: p.x, y: p.y, button: "left", clickCount: 1 }, s); await sleep(250); };
  const tapAt = async (fx, fy) => { const p = await canvasPoint(fx, fy); await send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: p.x, y: p.y }] }, s); await sleep(60); await send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] }, s); await sleep(350); };
  const strip = () => ev(`document.querySelector(".pt-strip").textContent`);

  await send("Page.navigate", { url: base + "/" }, s); await sleep(800);
  await seed(160); await open(1280, "light");
  const stripBefore = await strip();

  check("panel starts empty, Clear disabled", await ev(`!document.getElementById("pt-draw-empty").hidden && document.querySelectorAll("#pt-draw-list li").length === 0 && [...document.querySelectorAll("[data-clear]")].every(b => b.disabled)`));

  // ---- mouse: horizontal line ----
  await ev(`document.querySelector('[data-key="draw-h"]').click(); true`);
  check("Horizontal line mode: pressed and explained", await ev(`document.querySelector('[data-key="draw-h"]').getAttribute("aria-pressed") === "true" && !document.getElementById("pt-draw-banner").hidden && document.getElementById("pt-draw-banner").textContent.startsWith("Horizontal line: click or tap the chart")`));
  await clickAt(0.5, 0.25);
  let list = await items();
  check("mouse: horizontal line added at a cents price", list.length === 1 && /^Horizontal line at \$\d+\.\d\d$/.test(list[0]), list.join(" | "));
  check("mode ends after one line", await ev(`document.querySelector('[data-key="draw-h"]').getAttribute("aria-pressed") === "false" && document.getElementById("pt-draw-banner").hidden`));
  const st1 = (await stored())["synthetic-b|SYN-TEC1"];
  check("stored as a price, not pixels", st1.length === 1 && st1[0].kind === "h" && Number.isFinite(st1[0].price) && Math.round(st1[0].price * 100) === st1[0].price * 100 && Object.keys(st1[0]).sort().join() === "id,kind,price", JSON.stringify(st1));

  // ---- mouse: trend line, same-date guard, Esc ----
  await ev(`document.querySelector('[data-key="draw-t"]').click(); true`);
  await clickAt(0.35, 0.3);
  check("trend: first point asks for the second", await ev(`document.getElementById("pt-draw-banner").textContent.includes("second point")`), await ev(`document.getElementById("pt-draw-banner").textContent + " | hidden=" + document.getElementById("pt-draw-banner").hidden + " | pressed=" + document.querySelector('[data-key="draw-t"]').getAttribute("aria-pressed") + " | menuOpen=" + !document.getElementById("pt-ind-menu").hidden`));
  await clickAt(0.35, 0.35);
  check("trend: same date refused with a reason", await ev(`document.getElementById("pt-draw-banner").textContent.includes("a different day")`) && (await items()).length === 1);
  await clickAt(0.8, 0.2);
  list = await items();
  const st2 = (await stored())["synthetic-b|SYN-TEC1"];
  check("mouse: trend line added between two dates", list.length === 2 && /^Trend line from \w{3} \d+, 2025 \(\$\d+\.\d\d\) to \w{3} \d+, 2025 \(\$\d+\.\d\d\)$/.test(list[1]) && st2[1].a.date < st2[1].b.date, list[1]);
  await ev(`document.querySelector('[data-key="draw-t"]').click(); true`);
  await clickAt(0.3, 0.3);
  await key("Escape", "Escape", 27);
  check("Esc cancels a half-drawn trend line", await ev(`document.getElementById("pt-draw-banner").hidden && document.querySelector('[data-key="draw-t"]').getAttribute("aria-pressed") === "false"`) && (await items()).length === 2);
  await ev(`document.querySelector('[data-key="draw-t"]').click(); document.querySelector('[data-key="draw-cancel"]').click(); true`);
  check("Cancel button leaves the mode", await ev(`document.getElementById("pt-draw-banner").hidden`));
  await clickAt(0.5, 0.97);
  check("clicks without a mode draw nothing", (await items()).length === 2);

  // ---- keyboard: typed price ----
  for (const [typed, ok] of [["abc", false], ["0", false], ["100001", false], ["210.555", false], ["$210.50", true]]) {
    await ev(`(() => { const i = document.getElementById("pt-hline-price"); i.value = ""; i.focus(); return true; })()`);
    await typeText(typed); await key("Enter", "Enter", 13); await sleep(150);
    const st = await ev(`({ invalid: document.getElementById("pt-hline-price").getAttribute("aria-invalid"), status: document.getElementById("pt-draw-status").textContent, n: document.querySelectorAll("#pt-draw-list li").length })`);
    check(`typed price "${typed}" ${ok ? "accepted" : "refused"}`, ok ? st.invalid === "false" && st.n === 3 && st.status === "Added: Horizontal line at $210.50." : st.invalid === "true" && st.status.startsWith("Enter a price in dollars"), JSON.stringify(st));
  }
  // ---- keyboard: trend line from two days' closes ----
  await ev(`(() => { const f = document.getElementById("pt-tline-from"), t = document.getElementById("pt-tline-to"); t.value = f.value; return true; })()`);
  await ev(`document.querySelector('[data-key="draw-add-t"]').click(); true`);
  check("keyboard trend: end must be after start", await ev(`document.getElementById("pt-draw-status").textContent === "Choose an end date after the start date." && document.getElementById("pt-tline-to").getAttribute("aria-invalid") === "true"`));
  // a Wednesday start so the weekly view must map it into its week
  const wed = await ev(`(() => { const f = document.getElementById("pt-tline-from"); const o = [...f.options].map(x => x.value).filter(d => new Date(d + "T00:00:00Z").getUTCDay() === 3); f.value = o[o.length - 6]; document.getElementById("pt-tline-to").value = [...f.options].map(x => x.value).slice(-1)[0]; return f.value; })()`);
  await ev(`document.querySelector('[data-key="draw-add-t"]').click(); true`);
  const market = await ev(`(async () => (await fetch("/api/paper/market", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: JSON.parse(localStorage.getItem("paper-session-v1")) }) }).then(r => r.json())).data)()`);
  const st3 = (await stored())["synthetic-b|SYN-TEC1"].slice(-1)[0];
  const ci = d => market.dates.indexOf(d);
  check("keyboard trend uses the two days' closing prices", st3.kind === "t" && st3.a.date === wed && Math.round(st3.a.price * 100) === market.bars["SYN-TEC1"][ci(st3.a.date)].c && Math.round(st3.b.price * 100) === market.bars["SYN-TEC1"][ci(st3.b.date)].c, JSON.stringify(st3));
  check("summary names every drawing", await ev(`(() => { const t = document.querySelector(".pt-chart-summary").textContent; return t.includes("Your drawings: horizontal line at $") && (t.match(/trend line from/g) || []).length === 2; })()`));
  check("drawings never change the portfolio", (await strip()) === stripBefore);
  await shotEl("drawings-daily-1280-light", ".pt-chart");

  // ---- persistence, weekly mapping, theme, per ticker ----
  await send("Page.reload", {}, s); await waitFor(`!!document.querySelector(".pt-chart-canvas canvas")`, 8000); await pick("SYN-TEC1");
  check("reload keeps all four drawings", (await items()).length === 4);
  await ev(`document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`document.querySelector(".pt-chart-legend").textContent.startsWith("Partial Week") && document.querySelectorAll("#pt-draw-list li").length === 4`);
  const mondayOf = d => { const t = Date.parse(d + "T00:00:00Z"); const m = new Date(t - ((new Date(t).getUTCDay() + 6) % 7) * 86400000); return m.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }); };
  const wsum = await ev(`document.querySelector(".pt-chart-summary").textContent`);
  check("weekly: a mid-week date is drawn on its week's bar", wsum.includes("trend line from the week of " + mondayOf(wed)), wsum.slice(wsum.indexOf("Your drawings")));
  await sleep(300);
  const room = Number(await ev(`document.querySelector(".pt-chart-canvas").dataset.weekLabelRoom || "0"`));
  check("weekly: room after the Partial Week label for the Your line labels", room >= 115, room + " px");
  await shotEl("drawings-weekly-1280-light", ".pt-chart");
  await ev(`document.querySelector('[data-key="tf-daily"]').click(); true`);
  await waitFor(`!document.querySelector(".pt-chart-legend").textContent.startsWith("Partial") && document.querySelectorAll("#pt-draw-list li").length === 4`);
  await ev(`document.documentElement.setAttribute("data-theme", "dark"); true`); await sleep(500);
  check("theme change keeps the drawings", (await items()).length === 4 && await ev(`document.querySelector(".pt-chart-summary").textContent.includes("Your drawings:")`));
  await shotEl("drawings-daily-1280-dark", ".pt-chart");
  await ev(`document.documentElement.removeAttribute("data-theme"); true`); await sleep(300);
  await pick("SYN-FIN1");
  check("drawings belong to their ticker", (await items()).length === 0 && await ev(`!document.getElementById("pt-draw-empty").hidden`));
  await pick("SYN-TEC1");
  check("…and come back with it", (await items()).length === 4);

  // ---- remove and clear ----
  await ev(`document.querySelector("#pt-draw-list li button").focus(); document.querySelector("#pt-draw-list li button").click(); true`); await sleep(150);
  check("Remove takes one drawing away and keeps focus in the panel", (await items()).length === 3 && await ev(`document.getElementById("pt-drawings").contains(document.activeElement) && document.getElementById("pt-draw-status").textContent.startsWith("Removed: ")`));
  check("Remove buttons name what they remove", await ev(`[...document.querySelectorAll("#pt-draw-list button")].every(b => /^Remove (horizontal|trend) line/.test(b.getAttribute("aria-label")))`));
  await ev(`document.querySelector('[data-key="draw-clear"]').click(); true`); await sleep(150);
  check("Clear drawings asks first and keeps everything until confirmed", await ev(`(() => { const b = document.querySelector(".pt-confirm-clear"); return !!b && b.getAttribute("role") === "alertdialog" && b.textContent.startsWith("Clear all 3 drawings on SYN-TEC1? This cannot be undone.") && document.activeElement.dataset.key === "draw-clear-no" && document.querySelectorAll("#pt-draw-list li").length === 3; })()`));
  await shotEl("clear-confirmation-1280-light", "#pt-drawings");
  await ev(`document.querySelector('[data-key="draw-clear-no"]').click(); true`); await sleep(100);
  check("Keep drawings keeps them and returns focus", (await items()).length === 3 && await ev(`!document.querySelector(".pt-confirm-clear") && document.activeElement.dataset.key === "draw-clear-panel"`));
  await ev(`document.querySelector('[data-key="draw-clear-panel"]').click(); true`); await sleep(100);
  await key("Escape", "Escape", 27); await sleep(100);
  check("Esc in the confirmation keeps the drawings", (await items()).length === 3 && await ev(`!document.querySelector(".pt-confirm-clear")`));
  await ev(`document.querySelector('[data-key="draw-clear"]').click(); true`); await sleep(100);
  await ev(`document.querySelector('[data-key="draw-clear-yes"]').click(); true`); await sleep(150);
  check("Clear drawings empties the ticker's list", (await items()).length === 0 && await ev(`[...document.querySelectorAll("[data-clear]")].every(b => b.disabled)`));

  // ---- Reset and Change market clear drawings ----
  await ev(`document.querySelector('[data-key="draw-add-h"]').scrollIntoView(); document.getElementById("pt-hline-price").value = "150"; document.querySelector('[data-key="draw-add-h"]').click(); true`);
  await ev(`document.querySelector('[data-key="more"]').click(); document.querySelector('[data-key="reset"]').click(); true`); await sleep(100);
  await ev(`[...document.querySelectorAll(".pt-confirm-reset button")].find(b => b.textContent === "Yes, reset").click(); true`);
  await waitFor(`document.querySelector(".pt-day-line").textContent.startsWith("Day 1 of")`);
  check("Reset clears drawings", (await ev(`localStorage.getItem("paper-drawings-v1")`)) === null);
  await waitFor(`!!document.getElementById("pt-hline-price")`);
  await ev(`document.getElementById("pt-hline-price").value = "150"; document.querySelector('[data-key="draw-add-h"]').click(); true`); await sleep(150);
  await ev(`document.querySelector('[data-key="more"]').click(); document.querySelector('[data-key="change"]').click(); true`); await sleep(100);
  await ev(`[...document.querySelectorAll(".pt-confirm-reset button")].find(b => b.textContent === "Yes, change market").click(); true`);
  await waitFor(`!!document.querySelector(".pt-start-button")`);
  check("Change market clears drawings", (await ev(`localStorage.getItem("paper-drawings-v1")`)) === null);

  // ---- phone: touch drawing and layout ----
  await seed(160);
  await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 1 }, s);
  await open(390, "light");
  await ev(`document.querySelector('[data-key="draw-h"]').click(); true`);
  await tapAt(0.5, 0.3);
  check("touch: a tap draws a horizontal line", (await items()).length === 1, (await items()).join(" | "));
  await ev(`document.querySelector('[data-key="draw-t"]').click(); true`);
  await tapAt(0.3, 0.3); await tapAt(0.75, 0.2);
  check("touch: two taps draw a trend line", (await items()).length === 2 && /^Trend line from/.test((await items())[1]), (await items()).join(" | "));
  check("phone: no horizontal overflow", (await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`)) === 0);
  await ev(`document.querySelector('[data-key="draw-t"]').click(); true`);
  await shotEl("drawings-390-light", ".pt-chart");
  await ev(`document.querySelector('[data-key="draw-cancel"]').click(); document.querySelector('[data-key="tf-weekly"]').click(); true`);
  await waitFor(`document.querySelector(".pt-chart-legend").textContent.startsWith("Partial Week") && !!document.querySelector(".pt-chart-canvas").dataset.weekLabelRoom`);
  const roomPhone = Number(await ev(`document.querySelector(".pt-chart-canvas").dataset.weekLabelRoom`));
  check("phone weekly: room after the Partial Week label", roomPhone >= 115, roomPhone + " px");
  await shotEl("drawings-weekly-390-light", ".pt-chart");
  await ev(`document.querySelector('[data-key="tf-daily"]').click(); true`);
  await waitFor(`!document.querySelector(".pt-chart-legend").textContent.startsWith("Partial")`);
  await ev(`document.querySelector('[data-key="draw-t"]').click(); true`);
  await ev(`document.querySelector('[data-key="draw-cancel"]').click(); true`);
  await send("Emulation.setTouchEmulationEnabled", { enabled: false }, s);
  await open(390, "dark"); await shotEl("drawings-390-dark", ".pt-chart");
  await shotEl("drawings-panel-390-dark", "#pt-drawings");

  check("drawings never appear in any request", !bodies.some(b => /paper-drawings|"kind"\s*:\s*"[ht]"|Horizontal line at/.test(b)));
  check("only the local server was contacted", [...hosts].every(h => h.startsWith("127.0.0.1")), [...hosts].join(","));
  check("no console errors or warnings", errors.length === 0, errors.join(" | "));
  results.forEach(r => console.log(r.join("  ")));
  console.log(`${results.filter(r => r[0] === "PASS").length}/${results.length} passed`);
  process.exit(0);
};
