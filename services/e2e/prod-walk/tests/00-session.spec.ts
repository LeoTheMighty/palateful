// READ-ONLY. Proves the harness can drive the signed-in production app, and
// measures Leo's first complaint: does a session survive a reload?
//
// Every assertion here fails if the thing it checks is broken: an expired or
// unrestored session settles on /login and fails `signedIn`; a semantics tree
// that never appears fails `enableSemantics`; a login screen shown to a
// "signed-in" user fails the Google-button check.
import { expect, test } from "@playwright/test";
import {
  authCookieExpiries,
  authSettled,
  captureAuthErrors,
  captureAuthLog,
  enableSemantics,
  semanticsInventory,
} from "../lib/flutter.js";

test("a saved session opens the signed-in app, and survives a reload", async ({ page }, info) => {
  const authLog = captureAuthLog(page);
  const authErrors = captureAuthErrors(page);
  await info.attach("auth-cookies-at-start.txt", { body: (await authCookieExpiries(page)).join("\n"), contentType: "text/plain" });

  await page.goto("/", { waitUntil: "load" });
  const signedIn = await authSettled(page);
  await info.attach("auth-log-first-load.txt", { body: authLog.join("\n"), contentType: "text/plain" });
  expect(signedIn, `app settled on ${page.url()} — the saved session did not restore (see auth-log attachment)`).toBe(true);

  await enableSemantics(page);
  await expect(page.getByRole("button", { name: /Sign in with Google/i })).toHaveCount(0);
  const inventory = await semanticsInventory(page);
  await info.attach("signed-in-inventory.txt", { body: inventory.join("\n"), contentType: "text/plain" });
  expect(inventory.length, "signed-in screen exposed almost no labelled nodes").toBeGreaterThan(5);

  // Reload: the web SDK keeps tokens in memory, so this exercises the
  // silent re-auth path a real user hits on every refresh.
  authLog.length = 0;
  await page.reload({ waitUntil: "load" });
  const stillSignedIn = await authSettled(page);
  await info.attach("auth-log-after-reload.txt", { body: authLog.join("\n"), contentType: "text/plain" });
  await info.attach("auth-cookies-at-end.txt", { body: (await authCookieExpiries(page)).join("\n"), contentType: "text/plain" });
  expect(stillSignedIn, `after reload the app settled on ${page.url()} — session did not survive a refresh`).toBe(true);

  // An Auth0 denial is silent on web (no message, just /login). If one
  // happened at any point, fail with the reason the app never surfaces.
  expect(authErrors, `Auth0 returned an error the app did not show: ${JSON.stringify(authErrors)}`).toEqual([]);
});
