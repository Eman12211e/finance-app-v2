// Finance App V2 optional browser QA. Starts the app in zero-cost demo mode and a headless Edge or Chrome, runs the
// suites in this folder over the DevTools protocol, writes screenshots and a report, then stops only what it started.
// Node's built-in modules only (no npm packages); not part of pytest; contacts nothing but 127.0.0.1.
//
// Usage: node scripts/qa/run.mjs [output-dir] [suite ...]
//   suites: workflows overlays panes explanations drawings visual_audit (default: all)
//   env: PYTHON (a Python with the app's requirements, default "python"), BROWSER (path to msedge or chrome),
//        QA_PORT (app port, default 5055; the browser's debugging port is QA_PORT + 4000)
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const SUITES = ["workflows", "overlays", "panes", "explanations", "drawings", "visual_audit"];
const args = process.argv.slice(2);
const outDir = resolve(args[0] || join(repo, "..", "finance-app-v2-screenshots", "qa-run"));
const chosen = args.length > 1 ? args.slice(1) : SUITES;
const port = Number(process.env.QA_PORT || 5055);
const debugPort = port + 4000;
const base = `http://127.0.0.1:${port}`;
const BROWSERS = [process.env.BROWSER, "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitUp(url, ms) {
  const t = Date.now();
  while (Date.now() - t < ms) {
    try {
      const r = await fetch(url);
      if (r.ok) return r;
    } catch (e) { /* not up yet */ }
    await sleep(300);
  }
  return null;
}

function run(file, argv) {
  return new Promise(done => {
    const p = spawn(process.execPath, [file, ...argv], { cwd: repo });
    let text = "";
    p.stdout.on("data", d => { text += d; });
    p.stderr.on("data", d => { text += d; });
    p.on("close", code => done({ code, text }));
  });
}

function closeBrowser(wsUrl) {  // a clean shutdown through the DevTools protocol
  return new Promise(done => {
    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => { ws.send(JSON.stringify({ id: 1, method: "Browser.close" })); setTimeout(done, 500); };
      ws.onerror = () => done();
    } catch (e) { done(); }
  });
}

const unknown = chosen.filter(s => !SUITES.includes(s));
if (unknown.length) {
  console.error(`Unknown suite: ${unknown.join(", ")}. Choose from: ${SUITES.join(", ")}.`);
  process.exit(2);
}
if (await waitUp(base + "/api/health", 600)) {
  console.error(`Something already answers on port ${port}. Stop it or set QA_PORT.`);
  process.exit(2);
}
const browser = BROWSERS.find(p => existsSync(p));
if (!browser) {
  console.error("No Edge or Chrome found. Set BROWSER to its path.");
  process.exit(2);
}

const server = spawn(process.env.PYTHON || "python", ["-B", "-c", `from app import create_app; create_app().run(port=${port}, debug=False)`],
  { cwd: repo, env: { ...process.env, ZERO_COST_MODE: "1", DATA_MODE: "demo", WARM_CACHE: "0" }, stdio: "ignore" });
const profile = mkdtempSync(join(tmpdir(), "finance-app-v2-qa-"));
const edge = spawn(browser, ["--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
  `--user-data-dir=${profile}`, `--remote-debugging-port=${debugPort}`, "about:blank"], { stdio: "ignore" });
let exitCode = 0, wsUrl = null;
try {
  const health = await waitUp(base + "/api/health", 30000);
  if (!health) throw new Error("The app did not start. Set PYTHON to a Python with the app's requirements.");
  const h = (await health.json()).data;
  if (!h.zero_cost_mode || h.data_mode !== "demo") throw new Error("The app is not in zero-cost demo mode; stopping.");
  const version = await waitUp(`http://127.0.0.1:${debugPort}/json/version`, 20000);
  if (!version) throw new Error("The browser did not start.");
  wsUrl = (await version.json()).webSocketDebuggerUrl;
  mkdirSync(outDir, { recursive: true });
  const report = [`Finance App V2 browser QA, ${new Date().toISOString()}, ${base} (zero-cost demo mode), ${browser}`];
  for (const suite of chosen) {
    const dir = join(outDir, suite);
    mkdirSync(dir, { recursive: true });
    const out = await run(join(here, suite + ".mjs"), [wsUrl, dir, base]);
    writeFileSync(join(dir, "results.txt"), out.text);
    const fails = out.text.split("\n").filter(l => l.startsWith("FAIL"));
    const summary = (out.text.match(/(\d+\/\d+ passed)/) || [])[1] || "did not finish";
    if (out.code || fails.length || summary === "did not finish") exitCode = 1;
    const line = `${suite}: ${summary}` + (fails.length ? "\n  " + fails.join("\n  ") : "") + (out.code ? `\n  exit code ${out.code}` : "");
    report.push(line);
    console.log(line);
  }
  writeFileSync(join(outDir, "report.txt"), report.join("\n") + "\n");
  console.log(`Screenshots and results: ${outDir}`);
} catch (e) {
  console.error(e.message || String(e));
  exitCode = 1;
} finally {
  if (wsUrl) await closeBrowser(wsUrl);
  edge.kill();
  server.kill();
  await sleep(800);
  try { rmSync(profile, { recursive: true, force: true }); } catch (e) { /* the browser may still hold a file */ }
}
process.exit(exitCode);
