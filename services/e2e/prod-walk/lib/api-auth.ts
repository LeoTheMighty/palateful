import type { Page } from "@playwright/test";

export const API_BASE = process.env.PALATEFUL_E2E_API_BASE ?? "https://api.palateful.app";

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


/**
 * Lifetime of the access token the app is actually using: `exp - iat`, plus
 * the claim NAMES. Decodes the JWT payload only; the token, its signature and
 * every claim VALUE stay out of anything this returns. Settles whether web
 * (auth0-spa-js, Authorization Code + PKCE) gets Auth0's regular token
 * lifetime or the shorter "browser flows" one.
 */
export function tokenLifetime(authHeader: string | undefined): string {
  if (!authHeader) return "no API authorization observed on this page";
  const jwt = authHeader.replace(/^Bearer\s+/i, "");
  const parts = jwt.split(".");
  if (parts.length !== 3) return "access token is not a JWT (opaque) — lifetime not readable client-side";
  try {
    const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8")) as Record<string, unknown>;
    const iat = Number(claims.iat);
    const exp = Number(claims.exp);
    const names = Object.keys(claims).sort().join(", ");
    if (!Number.isFinite(iat) || !Number.isFinite(exp)) return `no numeric iat/exp; claim names: ${names}`;
    return `exp - iat = ${exp - iat} s (${((exp - iat) / 3600).toFixed(2)} h); claim names: ${names}`;
  } catch {
    return "access token payload did not decode";
  }
}
