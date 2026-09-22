import { homedir } from "node:os";
import { join } from "node:path";

/**
 * Where the signed-in browser state lives. OUTSIDE the repo by default, on
 * purpose: a gitignored file inside the tree is one `git add -f`, one
 * mis-scoped ignore rule, or one tracked-but-ignored accident away from a
 * commit. The file holds a live Auth0 session for a real account.
 *
 * Override with PALATEFUL_E2E_STATE (absolute path) if needed.
 */
export const SESSION_PATH =
  process.env.PALATEFUL_E2E_STATE ??
  join(homedir(), ".config", "palateful-e2e", "prod-session.json");

export const BASE_URL = process.env.PALATEFUL_E2E_BASE_URL ?? "https://palateful.app";
