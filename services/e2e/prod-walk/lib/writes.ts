import { test, type APIResponse, type Page } from "@playwright/test";

/** Everything a script creates carries this prefix, so it is recognisable
 *  on the account and deletable by name if an id was lost mid-run. */
export const E2E_PREFIX = "[e2e-walk]";

export const API_BASE = process.env.PALATEFUL_E2E_API_BASE ?? "https://api.palateful.app";

/**
 * Scripts that create data run against a REAL account. They skip unless the
 * operator opts in explicitly for this run — the gate is mechanical, not a
 * convention someone has to remember.
 */
export function requireWriteOptIn(): void {
  test.skip(
    process.env.PALATEFUL_E2E_ALLOW_WRITES !== "1",
    "creates data on the real account — set PALATEFUL_E2E_ALLOW_WRITES=1 only with the account owner's go-ahead",
  );
}

/**
 * The app holds its API token in memory (web Auth0, no cache). Cleanup must
 * not depend on the UI under test, so we reuse the Authorization header the
 * app itself sends. Kept in this closure only: never logged, attached or
 * written anywhere.
 */
export function captureApiAuth(page: Page): { header: () => string | undefined } {
  let header: string | undefined;
  page.on("request", (req) => {
    if (!req.url().startsWith(API_BASE)) return;
    const h = req.headers()["authorization"];
    if (h) header = h;
  });
  return { header: () => header };
}

export async function api(
  page: Page,
  auth: { header: () => string | undefined },
  method: "GET" | "DELETE",
  path: string,
): Promise<APIResponse> {
  const header = auth.header();
  if (!header) throw new Error(`no API authorization captured yet — cannot ${method} ${path}`);
  return page.request.fetch(`${API_BASE}${path}`, { method, headers: { authorization: header } });
}

/** The id of a created resource, tolerant of `{id}` or `{data:{id}}` shapes. */
export function idOf(body: unknown): string | undefined {
  const b = body as { id?: unknown; data?: { id?: unknown } } | null;
  const id = b?.id ?? b?.data?.id;
  return typeof id === "string" || typeof id === "number" ? String(id) : undefined;
}

/** Shopping lists as {id, name}, tolerant of a bare array or `{items|data|lists}`. */
export function listsOf(body: unknown): Array<{ id: string; name: string }> {
  const b = body as Record<string, unknown> | unknown[];
  const arr = (Array.isArray(b) ? b : (b?.items ?? b?.data ?? b?.lists ?? b?.shopping_lists ?? [])) as Array<Record<string, unknown>>;
  return arr.map((l) => ({ id: String(l.id), name: String(l.name ?? "") }));
}
