// Finance App V2 QA suite: visual_audit. Screenshots and an in-page audit of all five tabs at 1280 and 390 px in light and dark: overflow, clipped text, contrast, unnamed controls, broken references, small targets.
// Optional; not part of pytest. Driven over the DevTools protocol with Node's built-in WebSocket (no packages).
// Usage: node scripts/qa/visual_audit.mjs <devtools-websocket-url> <screenshot-dir> <app-base-url>
// Normally run through scripts/qa/run.mjs, which starts the app (zero-cost demo mode) and a headless browser.
import { writeFileSync } from "node:fs";
const [wsUrl, outDir, base] = process.argv.slice(2);
const ws = new WebSocket(wsUrl); let id = 0; const pend = {}; const listeners = [];
const send = (m, params = {}, sessionId) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params, sessionId })); });
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) pend[m.id](m.result || m); else listeners.forEach(f => f(m)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

// runs in the page: layout and accessibility problems a script can see
const AUDIT = `(() => {
  const out = { overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth, offscreen: [], clipped: [], lowContrast: [], unnamed: [], badRefs: [], dupIds: [], smallTargets: [] };
  const vis = n => { const s = getComputedStyle(n); const r = n.getBoundingClientRect(); return s.visibility !== "hidden" && s.display !== "none" && r.width > 1 && r.height > 1 && !/^rect\\(0(px)?,? 0/.test(s.clip) && !n.closest("[hidden],[aria-hidden=true],.visually-hidden"); };
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
  const bgOf = n => { const layers = []; for (let e = n; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } } let base = { r: 255, g: 255, b: 255 }; const html = parse(getComputedStyle(document.documentElement).backgroundColor); if (html && html.a) base = html; for (let i = layers.length - 1; i >= 0; i--) { const c = layers[i]; base = { r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a) }; } return base; };
  const vw = document.documentElement.clientWidth;
  document.querySelectorAll("body *").forEach(n => {
    if (!vis(n) || n.closest("svg")) return;
    const r = n.getBoundingClientRect(), s = getComputedStyle(n);
    if (s.position !== "fixed" && (r.right > vw + 1 || r.left < -1) && !n.closest(".skip-link")) out.offscreen.push(n.tagName + "." + n.className + " " + Math.round(r.left) + ".." + Math.round(r.right));
    const own = [...n.childNodes].filter(c => c.nodeType === 3 && c.textContent.trim()).map(c => c.textContent.trim()).join(" ");
    if (own) {
      if ((s.overflow.includes("hidden") || s.textOverflow === "ellipsis") && n.scrollWidth > n.clientWidth + 1) out.clipped.push(own.slice(0, 40));
      const fg = parse(s.color); const bg = bgOf(n);
      if (fg) { const f = { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a) }; const L1 = lum(f), L2 = lum(bg); const ratio = (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05); const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700; const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5; if (ratio < need && !n.disabled && !n.closest(":disabled")) out.lowContrast.push(ratio.toFixed(2) + " " + own.slice(0, 30)); }
    }
    if (n.matches("button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=tab], [role=combobox], [role=option]")) {
      const lab = n.getAttribute("aria-label") || (n.getAttribute("aria-labelledby") || "").split(" ").map(i => (document.getElementById(i) || {}).textContent || "").join("") || (n.labels && [...n.labels].map(l => l.textContent).join("")) || n.textContent || n.title || n.placeholder || n.value;
      if (!String(lab).trim()) out.unnamed.push(n.tagName + "#" + n.id + "." + n.className);
      if ((r.width < 24 || r.height < 24) && !n.matches("input[type=radio], input[type=checkbox]") && s.display !== "inline") out.smallTargets.push(n.tagName + " " + (n.getAttribute("aria-label") || n.textContent.trim()).slice(0, 20) + " " + Math.round(r.width) + "x" + Math.round(r.height));
    }
  });
  document.querySelectorAll("[aria-controls],[aria-labelledby],[aria-describedby],[aria-activedescendant],label[for]").forEach(n => {
    ["aria-controls", "aria-labelledby", "aria-describedby", "aria-activedescendant", "for"].forEach(a => { const v = n.getAttribute(a); if (v) v.split(" ").forEach(i => { if (i && !document.getElementById(i)) out.badRefs.push(a + "=" + i); }); });
  });
  const seen = {}; document.querySelectorAll("[id]").forEach(n => { seen[n.id] = (seen[n.id] || 0) + 1; }); out.dupIds = Object.keys(seen).filter(k => seen[k] > 1);
  return out;
})()`;

ws.onopen = async () => {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId: s } = await send("Target.attachToTarget", { targetId, flatten: true });
  const errors = [], hosts = new Set();
  listeners.push(m => {
    if (m.sessionId !== s) return;
    if (m.method === "Network.requestWillBeSent" && /^https?:/.test(m.params.request.url)) hosts.add(new URL(m.params.request.url).host);
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) errors.push(m.params.type + ": " + m.params.args.map(a => a.value).join(" "));
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") errors.push("log: " + m.params.entry.text + " " + (m.params.entry.url || ""));
  });
  await send("Network.enable", {}, s); await send("Runtime.enable", {}, s); await send("Page.enable", {}, s); await send("Log.enable", {}, s);
  const ev = async e => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }, s); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 300)); return r.result.value; };
  const shot = async (name, full) => { const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: !!full }, s); writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.data, "base64")); };

  // a populated practice session on synthetic-b: two fills, one pending, one cancelled
  await send("Page.navigate", { url: base + "/" }, s); await sleep(1000);
  await ev(`(async () => {
    const post = (a, b) => fetch("/api/paper/" + a, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()).then(j => j.data);
    let st = (await post("new", { scenario: "synthetic-b" })).state;
    st = (await post("confirm", { state: st, order: { id: "order-qa-0001", symbol: "SYN-TEC2", side: "buy", shares: 20 } })).state;
    st = (await post("confirm", { state: st, order: { id: "order-qa-0002", symbol: "SYN-FIN1", side: "buy", shares: 15 } })).state;
    st = (await post("advance", { state: st, expected_day: 0 })).state;
    st = (await post("confirm", { state: st, order: { id: "order-qa-0003", symbol: "SYN-TEC2", side: "sell", shares: 5 } })).state;
    st = (await post("advance", { state: st, expected_day: 1 })).state;
    st = (await post("confirm", { state: st, order: { id: "order-qa-0004", symbol: "SYN-ENR2", side: "buy", shares: 10 } })).state;
    st = (await post("confirm", { state: st, order: { id: "order-qa-0005", symbol: "SYN-CON1", side: "buy", shares: 4 } })).state;
    st = (await post("cancel", { state: st, order_id: "order-qa-0005" })).state;
    localStorage.clear();
    localStorage.setItem("fe_profile", JSON.stringify({ age_range: "25-34", risk: "medium" }));
    localStorage.setItem("paper-session-v1", JSON.stringify(st));
    localStorage.setItem("paper-indicators-v1", JSON.stringify([{ type: "sma", period: 20 }, { type: "ema", period: 12 }, { type: "rsi", period: 14 }, { type: "macd", period: [12, 26, 9] }]));
    localStorage.setItem("paper-journal-v1", JSON.stringify({ "order-qa-0001": { why: "Testing a buy in a volatile chip stock.", risks: "It could gap down at the open." } }));
    return true; })()`);

  const report = {};
  for (const width of [1280, 390]) for (const theme of ["light", "dark"]) {
    await send("Emulation.setDeviceMetricsOverride", { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 }, s);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, s);
    for (const hash of ["explore", "lab", "sign", "brokers", "practice"]) {
      await send("Page.navigate", { url: "about:blank" }, s); await sleep(150);
      await send("Page.navigate", { url: `${base}/#${hash}` }, s); await sleep(2200);
      const name = `${hash}-${width}-${theme}`;
      await shot(name); if (theme === "light" || hash === "practice") await shot(name + "-full", true);
      report[name] = await ev(AUDIT);
    }
  }
  // header theme toggle (data-theme) must redraw the canvas chart in the new colours
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false }, s);
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] }, s);
  await send("Page.navigate", { url: "about:blank" }, s); await sleep(150);
  await send("Page.navigate", { url: `${base}/#practice` }, s); await sleep(2500);
  const px = `(() => { const c = document.querySelector(".pt-chart-canvas canvas"); const d = c.getContext("2d").getImageData(4, 4, 1, 1).data; return [d[0], d[1], d[2]].join(","); })()`;
  const lightPx = await ev(px);
  await ev(`document.documentElement.setAttribute("data-theme", "dark"); true`); await sleep(500);
  const darkPx = await ev(px);
  console.log("theme toggle redraw:", lightPx, "->", darkPx, lightPx !== darkPx ? "PASS" : "FAIL");
  await shot("practice-chart-toggled-dark");
  writeFileSync(`${outDir}/qa.json`, JSON.stringify({ report, errors, hosts: [...hosts] }, null, 1));
  let clean = 0, screens = 0;
  for (const [k, v] of Object.entries(report)) {
    const issues = Object.entries(v).filter(([key, val]) => key === "overflowX" ? val > 0 : val.length).map(([key, val]) => key + "=" + (Array.isArray(val) ? val.length + " [" + [...new Set(val)].slice(0, 4).join(" | ") + "]" : val));
    console.log((issues.length ? "FAIL  " : "PASS  ") + k.padEnd(26), issues.length ? issues.join("  ") : "clean");
    clean += issues.length ? 0 : 1; screens += 1;
  }
  console.log(`${clean}/${screens} passed`);
  console.log("hosts:", [...hosts].join(", "));
  console.log("console errors/warnings:", errors.length ? errors.join(" || ") : "none");
  process.exit(0);
};
