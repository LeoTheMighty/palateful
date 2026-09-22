import { expect, type Page } from "@playwright/test";

/**
 * palateful.app is a Flutter web build. On Flutter 3.41 there is no HTML
 * renderer: the app paints to a canvas and exposes NO DOM for its widgets
 * until the semantics tree is turned on.
 *
 * We turn it on per page, from the outside, with the engine's own opt-in:
 * Flutter web renders a hidden `flt-semantics-placeholder` ("Enable
 * accessibility") that switches semantics on when clicked. Nothing in the
 * app changes and nothing is deployed, so ordinary users pay no cost —
 * always-on `SemanticsBinding.instance.ensureSemantics()` would tax every
 * page load for every user to serve this suite. Measured on prod
 * 2026-09-22: 0 `flt-semantics` nodes before the click, 9 after, on /login.
 */
export async function enableSemantics(page: Page): Promise<void> {
  await page.waitForSelector("flutter-view, flt-glass-pane", { timeout: 60_000 });
  const placeholder = page.locator("flt-semantics-placeholder");
  if ((await placeholder.count()) > 0) {
    // Off-screen by design; dispatch the click directly rather than
    // asking Playwright to scroll a hidden element into view.
    await placeholder.evaluate((el) => (el as HTMLElement).click());
  }
  await expect
    .poll(() => page.locator("flt-semantics").count(), {
      message: "Flutter semantics tree never appeared",
      timeout: 20_000,
    })
    .toBeGreaterThan(0);
}

/** Lines the app logs about auth/routing — its own statement of auth state.
 *  Redacted: the app logs the first characters of access tokens, and those
 *  must not land in a report or an attachment. */
export function captureAuthLog(page: Page): string[] {
  const lines: string[] = [];
  page.on("console", (msg) => {
    const t = msg.text();
    if (!/Router redirect|onLoad|AuthService|Silent auth|Auth init/.test(t)) return;
    lines.push(/token/i.test(t) ? "[redacted: line mentions a token]" : t);
  });
  return lines;
}

const onLogin = (url: string) => /#\/login(\b|$|\?)/.test(url);

/**
 * Wait until the app has resolved auth. The router's initial location is
 * /login and an authenticated session redirects away once Auth0's silent
 * re-auth returns, so "left /login and stayed away" is the signed-in signal.
 * Returns true if signed in, false if the app settled on /login.
 */
export async function authSettled(page: Page, timeoutMs = 30_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!onLogin(page.url())) {
      // Stay away for a moment: a flash off /login then back is NOT signed in.
      await page.waitForTimeout(2_000);
      if (!onLogin(page.url())) return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

/** Every labelled semantics node currently on screen, as `role:label`. */
export async function semanticsInventory(page: Page): Promise<string[]> {
  return page.$$eval("flt-semantics, [role]", (els) =>
    els
      .map((e) => {
        const role = e.getAttribute("role") ?? "";
        const label = (e.getAttribute("aria-label") ?? e.textContent ?? "").trim().replace(/\s+/g, " ");
        return label ? `${role}:${label.slice(0, 60)}` : "";
      })
      .filter(Boolean),
  );
}
