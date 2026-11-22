// End-to-end check in headless Chrome: every page at desktop and phone width runs the page's own
// self-test (?selftest=1), and must have no script errors and no sideways scrolling.
//   node scripts/e2e.mjs                         # serve dist/ locally and test it
//   node scripts/e2e.mjs https://host/path/      # test a live site
//   node scripts/e2e.mjs --screens docs/screens  # also save screenshots of the key screens
// Needs Node 22+ (built-in WebSocket) and Google Chrome or Chromium.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const screensAt = args.indexOf("--screens");
const screensDir = screensAt >= 0 ? path.resolve(args[screensAt + 1]) : "";
let base = args.find((a, i) => /^https?:\/\//.test(a) && (screensAt < 0 || i !== screensAt + 1)) || "";
const CHROME = process.env.CHROME || ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
  .map((c) => { try { return execFileSync("which", [c]).toString().trim(); } catch { return ""; } }).find(Boolean)
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

let server;
if (!base) {
  const port = 8800 + Math.floor(Math.random() * 900);
  server = spawn("python3", ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", path.join(ROOT, "dist")], { stdio: "ignore" });
  base = `http://127.0.0.1:${port}/`;
  for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }
}
if (!base.endsWith("/")) base += "/";
const bust = server ? "" : `&v=${Date.now()}`;
// A new or just-deployed Pages site can answer 404 for a few minutes; wait up to 6 minutes for it.
let data = null;
for (let i = 0; i < 36 && !data; i++) {
  try {
    const r = await fetch(base + "data/channels.json" + (bust ? "?" + bust.slice(1) : ""));
    if (r.ok) data = await r.json();
  } catch { /* not up yet */ }
  if (!data) await new Promise((r) => setTimeout(r, 10000));
}
if (!data) { console.log(`FAIL: ${base}data/channels.json did not answer with JSON`); process.exit(1); }
const pages = ["", "method/", "about/", ...data.apps.map((a) => `channels/${a.slug}/`)];
// PHONE_WIDTH lets a local run stress-test narrower phones (CI fonts are wider than macOS fonts).
const widths = [[1280, false], [Number(process.env.PHONE_WIDTH || 390), true]];

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "e2e-"));
const chrome = spawn(CHROME, [...(process.env.CI ? ["--no-sandbox"] : []), "--headless=new", "--disable-gpu", "--hide-scrollbars",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
const wsUrl = await new Promise((resolve, reject) => {
  let buf = "";
  chrome.stderr.on("data", (d) => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) resolve(m[1]); });
  chrome.on("exit", () => reject(new Error("Chrome exited: " + buf.slice(-400))));
});
const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let seq = 0;
const waiting = new Map();
const listeners = new Set();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) {
    const { resolve, reject } = waiting.get(m.id);
    waiting.delete(m.id);
    m.error ? reject(new Error(m.error.message)) : resolve(m.result);
  } else for (const l of listeners) l(m);
});
const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
  const id = ++seq;
  waiting.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params, sessionId }));
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const failures = [];
try {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  await send("Page.enable", {}, sessionId);
  await send("Runtime.enable", {}, sessionId);
  await send("Log.enable", {}, sessionId);
  // Screenshots and checks use the light theme; the dark theme uses the same layout.
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] }, sessionId);
  let pageErrors = [];
  listeners.add((m) => {
    if (m.sessionId !== sessionId) return;
    if (m.method === "Runtime.exceptionThrown") pageErrors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") pageErrors.push(m.params.args.map((a) => a.value).join(" "));
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error" && !/favicon/.test(m.params.entry.url || "")) pageErrors.push(`${m.params.entry.text} ${m.params.entry.url || ""}`);
  });
  if (screensDir) fs.mkdirSync(screensDir, { recursive: true });
  for (const p of pages) {
    for (const [width, mobile] of widths) {
      pageErrors = [];
      await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile }, sessionId);
      await send("Page.navigate", { url: `${base}${p}?selftest=1${bust}` }, sessionId);
      let result = null;
      for (let i = 0; i < 60 && !result; i++) {
        await sleep(250);
        const r = await send("Runtime.evaluate", { expression: "(()=>{const s=document.getElementById('selftest');return s&&s.dataset.selftest?{status:s.dataset.selftest,text:s.textContent,width:document.documentElement.scrollWidth}:null})()", returnByValue: true }, sessionId);
        result = r.result.value;
      }
      const label = `/${p} @${width}px`;
      if (!result) failures.push(`${label}: self-test did not finish`);
      else {
        if (result.status !== "pass") failures.push(`${label}: ${result.text.replace(/\n/g, "; ")}`);
        if (result.width > width + 1) failures.push(`${label}: page is ${result.width}px wide (sideways scrolling)`);
      }
      if (pageErrors.length) failures.push(`${label}: console errors: ${pageErrors.join(" | ")}`);
      console.log(`${result && result.status === "pass" && !pageErrors.length && result.width <= width + 1 ? "ok  " : "FAIL"} ${label}`);
      const shoot = screensDir && (p === "" || p === "method/" || p === `channels/${data.apps[0].slug}/`);
      if (shoot) {
        await send("Emulation.setDeviceMetricsOverride", { width, height: mobile ? 1600 : 1400, deviceScaleFactor: 1, mobile }, sessionId);
        await sleep(400);
        const { data: png } = await send("Page.captureScreenshot", { format: "png" }, sessionId);
        const name = (p === "" ? "home" : p.replace(/\/$/, "").replace(/\//g, "-")) + (mobile ? "-phone" : "-desktop") + ".png";
        fs.writeFileSync(path.join(screensDir, name), Buffer.from(png, "base64"));
      }
    }
  }
} finally {
  ws.close();
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill();
  await exited;
  if (server) server.kill();
  // Chrome's helper processes can still be writing to the profile for a moment; cleanup is best effort.
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); } catch { /* temp dir */ }
}
if (failures.length) {
  console.log("\nFAILURES:\n  " + failures.join("\n  "));
  process.exit(1);
}
console.log(`\nall ${pages.length * widths.length} page checks passed on ${base}`);
