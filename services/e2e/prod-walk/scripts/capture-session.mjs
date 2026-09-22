// Capture a signed-in palateful.app session for the prod walk.
//
// A PERSON signs in, in a real Chrome window this script opens. The script
// never sees, asks for, or stores a password; it saves only the browser's
// resulting session state (cookies + localStorage) to a file OUTSIDE the repo,
// readable by the owner only.
//
//   npx nx run e2e:prod-capture-session
//
import { chmodSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { chromium } from "@playwright/test";

const SESSION_PATH =
  process.env.PALATEFUL_E2E_STATE ??
  `${process.env.HOME}/.config/palateful-e2e/prod-session.json`;
const BASE_URL = process.env.PALATEFUL_E2E_BASE_URL ?? "https://palateful.app";
const onLogin = (u) => /#\/login(\b|$|\?)/.test(u);

// Real Chrome, not Playwright's bundled Chromium: Google sign-in commonly
// refuses automation-built browsers. If Chrome is not installed, fall back.
let browser;
try {
  browser = await chromium.launch({ headless: false, channel: "chrome" });
} catch {
  browser = await chromium.launch({ headless: false });
}
const context = await browser.newContext();
const page = await context.newPage();

// Diagnostics for the auth track (2026-09-22): the web session does not
// survive a reload. Record, in THIS browser, at sign-in time: the live
// token's lifetime (exp - iat, claim NAMES only) and every silent-auth
// outcome. Nothing secret is printed.
let apiAuth;
context.on("request", (r) => {
  if (r.url().startsWith("https://api.palateful.app")) apiAuth = r.headers()["authorization"] ?? apiAuth;
});
const silentAuth = [];
context.on("response", async (r) => {
  const u = new URL(r.url());
  if (u.hostname !== "auth.palateful.app" || u.pathname !== "/authorize" || u.searchParams.get("prompt") !== "none") return;
  const body = await r.text().catch(() => "");
  const err = /"error"\s*:\s*"([^"]+)"/.exec(body)?.[1];
  silentAuth.push(err ? `error=${err}` : /"code"\s*:/.test(body) ? "ok (code returned, not shown)" : `HTTP ${r.status()}`);
});
const tokenLifetime = () => {
  if (!apiAuth) return "no API call observed";
  const parts = apiAuth.replace(/^Bearer\s+/i, "").split(".");
  if (parts.length !== 3) return "opaque (non-JWT) token";
  const c = JSON.parse(Buffer.from(parts[1], "base64url").toString());
  return `exp - iat = ${c.exp - c.iat} s (${((c.exp - c.iat) / 3600).toFixed(2)} h); claim names: ${Object.keys(c).sort().join(", ")}`;
};
const appCookies = async () =>
  (await context.cookies("https://palateful.app")).map(
    (c) => `  ${c.domain}  ${c.name}  expires ${c.expires > 0 ? new Date(c.expires * 1000).toISOString() : "session-only"}`,
  );
await page.goto(BASE_URL, { waitUntil: "load", timeout: 60_000 });

console.log(`\nA browser window is open at ${BASE_URL}.`);
console.log("Sign in exactly as you normally would. This script waits (up to 10 min)");
console.log("until the app leaves the login screen, then saves the session and closes.\n");

const deadline = Date.now() + 10 * 60_000;
let signedIn = false;
while (Date.now() < deadline) {
  if (page.isClosed()) break;
  const url = page.url();
  if (url.startsWith(BASE_URL) && !onLogin(url)) {
    await page.waitForTimeout(3_000); // must STAY signed in, not flash through
    if (!onLogin(page.url())) { signedIn = true; break; }
  }
  await page.waitForTimeout(1_000);
}

if (!signedIn) {
  console.error("Did not observe a signed-in app. Nothing was saved.");
  await browser.close();
  process.exit(1);
}

console.log("\n--- diagnostics at sign-in (for the auth track) ---");
console.log("palateful.app cookies right after sign-in (is the spa-js hint `auth0.<clientId>.is.authenticated` set?):");
console.log((await appCookies()).join("\n") || "  (none)");
console.log(`live token: ${tokenLifetime()}`);

mkdirSync(dirname(SESSION_PATH), { recursive: true, mode: 0o700 });
await context.storageState({ path: SESSION_PATH, indexedDB: true });
chmodSync(SESSION_PATH, 0o600);

// Session-lifetime data for the auth track. Cookie NAMES, domains and expiry
// only — never values.
const cookies = await context.cookies();
console.log(`Saved session to ${SESSION_PATH} (mode 600).`);
console.log("Auth-relevant cookies (values not shown):");
for (const c of cookies.filter((c) => /auth|session|did|palateful/i.test(`${c.domain}${c.name}`))) {
  const exp = c.expires > 0 ? new Date(c.expires * 1000).toISOString() : "session-only";
  console.log(`  ${c.domain}  ${c.name}  expires ${exp}`);
}

// Same window, same minute: does a reload keep the session? This removes
// "the session died later" and "cookies replayed in another browser" as
// explanations for the reload failure measured by tests/00-session.spec.ts.
silentAuth.length = 0;
await page.reload({ waitUntil: "load" });
let survived = false;
for (let i = 0; i < 20; i++) {
  await page.waitForTimeout(1_000);
  if (!onLogin(page.url()) && i > 3) { survived = true; break; }
}
console.log(`immediate reload in the same window: ${survived ? "STILL SIGNED IN" : "back on /login"}`);
console.log(`silent-auth attempts during that reload: ${silentAuth.join(", ") || "none (spa-js skipped the check)"}`);
console.log("(The saved session above was written BEFORE this reload, so it is unaffected.)");
await browser.close();
