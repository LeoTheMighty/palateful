import { existsSync } from "node:fs";
import { defineConfig } from "@playwright/test";
import { BASE_URL, SESSION_PATH } from "./lib/session.js";

if (!existsSync(SESSION_PATH)) {
  throw new Error(
    `No signed-in session at ${SESSION_PATH}.\n` +
      "Capture one first: `npx nx run e2e:prod-capture-session` (a person signs in; the password never touches this repo).",
  );
}

export default defineConfig({
  testDir: "./tests",
  // A real account: never run scripts concurrently against it.
  workers: 1,
  fullyParallel: false,
  // No retries: on a live system a retry turns an intermittent bug into a
  // green run. A flake here is a finding, not noise.
  retries: 0,
  // Live network + Auth0 silent re-auth: generous, measured caps. The
  // assertions — not the timeouts — are what make a pass mean something.
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    storageState: SESSION_PATH,
    navigationTimeout: 60_000,
    actionTimeout: 20_000,
    screenshot: "only-on-failure",
    // OFF by default: a trace records request headers, i.e. live bearer
    // tokens, into test-results/. Opt in only when debugging, and delete it.
    trace: process.env.PALATEFUL_E2E_TRACE === "1" ? "retain-on-failure" : "off",
    video: "off",
  },
});
