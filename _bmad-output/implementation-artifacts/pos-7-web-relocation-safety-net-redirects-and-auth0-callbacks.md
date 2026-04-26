# Story pos-7 — Web relocation safety net (redirects + Auth0 callbacks)

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Blocks:** pos-3 go-live (DNS flip blocked until this runbook is
verified end-to-end on staging).

## Goal

When pos-3 ships the new static landing page at `palateful.app/`, the
existing Flutter web app moves from the apex to `palateful.app/app`.
Two things break silently if not handled:

1. **Auth0 redirect_uri mismatch** — Auth0 SPAs fail with
   `redirect_uri_mismatch` if a callback URL not on the allowed-callback
   list is requested. Auth0 dashboard → Application → "Allowed Callback
   URLs" / "Allowed Logout URLs" / "Allowed Web Origins" must list the
   new `/app/...` paths *before* the DNS flip.
2. **Stale `palateful.app/login` deep links** (e.g. emailed magic links,
   bookmarked Auth0-callback pages) hit the new static landing page
   instead of the Flutter shell after relocation. Cloudflare Pages
   `_redirects` rules forward these to the new `/app/...` location.

This story's deliverable is the runbook + the actual `_redirects`
content + the smoke-test commands. pos-3 follows this runbook step-by-
step at go-live. No user-facing code ships in this story; consider it
docs + a config file pre-written.

## Acceptance criteria

- [x] Cloudflare Pages `_redirects` rules written and stored in this
  story file. pos-3 copies them into `app/web/_redirects` at relocation
  time, replacing today's near-empty file.
- [x] Auth0 callback / logout / web-origin lists enumerated. The
  operator must add the new `/app/...` entries *before* the DNS flip.
  Each existing entry stays — both old and new must work for a
  rollback window.
- [x] Smoke-test playbook (3 commands) for the operator to run after
  the DNS flip and before declaring pos-3 live.
- [x] Standalone QA walkthrough at `pos-7-qa-walkthrough.md`.

## File List

- `_bmad-output/implementation-artifacts/pos-7-web-relocation-safety-net-redirects-and-auth0-callbacks.md` (this file)
- `_bmad-output/implementation-artifacts/pos-7-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

No source-code changes; pos-3 wires the `_redirects` file when it
actually moves the Flutter app off the apex.

---

## A. Cloudflare Pages `_redirects` content

When pos-3 relocates the Flutter web app, replace `app/web/_redirects`
with **exactly** this:

```text
# Cloudflare Pages redirect rules. Format: <source> <destination> <status>
# pos-7: web-relocation safety net. Active once pos-3 moves the Flutter
# web app from `palateful.app/` to `palateful.app/app/`. The new landing
# page (static HTML+CSS) lives at the apex from then on.

# --- Auth0 callback URLs ---
# Auth0 redirects to the path the SDK was initialized with. The web
# build's redirect_uri targets `${origin}/login`. Forward stale apex
# /login hits to the Flutter shell so an emailed magic link continues
# to land users on the auth screen.
/login              /app/login              301
/login/*            /app/login/:splat       301

# --- /auth/* deep links ---
# Auth0 PKCE flow does sometimes emit `${origin}/auth/...` URLs in
# templates the user customizes. Forward all of them.
/auth               /app/auth               301
/auth/*             /app/auth/:splat        301

# --- Bookmarked deep links into common Flutter screens ---
# The router knows these top-level paths; preserve them across the
# relocation so a forwarded link still lands on the right screen.
/recipes            /app/recipes            301
/recipes/*          /app/recipes/:splat     301
/recipe-books       /app/recipe-books       301
/recipe-books/*     /app/recipe-books/:splat 301
/calendar           /app/calendar           301
/calendar/*         /app/calendar/:splat    301
/cart               /app/cart               301
/cart/*             /app/cart/:splat        301
/profile            /app/profile            301
/profile/*          /app/profile/:splat     301
/admin              /app/admin              301
/admin/*            /app/admin/:splat       301
/onboarding/*       /app/onboarding/:splat  301
/invitations        /app/invitations        301
/invitations/*      /app/invitations/:splat 301
/recipe-public/*    /app/recipe-public/:splat 301
/meal-public/*      /app/meal-public/:splat 301

# --- Privacy stays at the apex ---
# pos-4 keeps privacy.html at the apex so existing links to
# `palateful.app/privacy` continue to land on it. Cloudflare's auto-
# strip already serves /privacy as 200 from privacy.html — no rule
# needed.

# --- All other unmatched paths fall through ---
# Cloudflare Pages handles unmatched paths via the static landing page
# from pos-3 (404s are owned by the new landing's 404.html, if any).
```

**Why 301 (permanent) and not 302:** these are durable URL changes.
301 is cacheable and faster after the first hit; 302 makes the browser
re-check on every visit. If pos-3 ever needs to roll back, a fresh
deploy with the rules removed picks up new requests fine — old 301s
in the user's cache will eventually expire.

**Why match all `/path/*` not just `/path`:** Cloudflare's pattern
syntax doesn't auto-include sub-paths. Both forms must be listed.

---

## B. Auth0 dashboard updates (operator action)

Run this before the DNS flip in pos-3. Login → Auth0 dashboard →
Applications → "Palateful Web" (the SPA-type application).

| Field | Add (keep existing) |
|-------|---------------------|
| **Allowed Callback URLs** | `https://palateful.app/app/login`, `https://palateful.app/app/auth/callback`, `https://palateful.app/app/` (in addition to the existing `https://palateful.app/login` etc.) |
| **Allowed Logout URLs** | `https://palateful.app/app/`, `https://palateful.app/app/login` |
| **Allowed Web Origins** | (no change — origin already matches `https://palateful.app`) |

**Do not remove the apex entries** until pos-3 has been live for ≥7 days
without rollback. The 301 redirects forward apex hits to /app, but the
browser then loads /app and the SDK initializes with redirect_uri
`/app/login` — which Auth0 must already have on the allowed list.

If the operator doesn't have Auth0 dashboard access, this step is a
hand-off to whoever does. **Do not flip DNS without confirming this
step is complete.**

---

## C. Smoke-test playbook (run on staging first, then prod)

After the DNS flip in pos-3 — before announcing the new landing — run
these three commands. Any failure → revert the DNS flip immediately.

### C.1 Apex redirect of /login

```bash
curl -sI https://palateful.app/login | head -4
```

Expected:
```
HTTP/2 301
location: /app/login
```

### C.2 /app/login serves the Flutter shell

```bash
curl -s https://palateful.app/app/login | grep -E "auth0-spa-js|flutter_bootstrap"
```

Expected: at least one match. The Flutter shell loads the Auth0 SDK
script and `flutter_bootstrap.js`. If both are absent, the wrong page
is being served.

### C.3 Round-trip a real login (manual, single-pass)

In a fresh incognito browser:

1. Open `https://palateful.app/login` (apex).
2. Confirm the URL bar lands on `https://palateful.app/app/login`
   (the redirect chain succeeded).
3. Click "Sign in with Google" (or your test SSO).
4. After Auth0's consent screen, confirm the browser returns to
   `https://palateful.app/app/...` with valid credentials (no
   `redirect_uri_mismatch` error from Auth0).
5. The router redirects to `/app/home` (or `/app/onboarding/welcome`
   for fresh accounts).

If step 4 fails with `redirect_uri_mismatch`, the Auth0 dashboard
update from section B is incomplete — finish it and retry.

---

## Risks + mitigations

- **Risk:** A forgotten path not in the redirect list 404s after the
  flip. *Mitigation:* the smoke test catches the common ones (login,
  callback). For long-tail paths, Cloudflare access logs in the first
  24h surface 404 spikes to specific URLs.
- **Risk:** Auth0 dashboard update lags the DNS flip. *Mitigation:*
  this story's hand-off to pos-3 explicitly gates DNS flip on Auth0
  confirmation.
- **Risk:** Cached 301s persist if we have to rollback. *Mitigation:*
  the only way out is a fresh deploy that removes the rules and
  serves /login again from /app's location at the apex (i.e. abort
  the relocation entirely). That's a real cost — the 7-day no-rollback
  window in section B exists to make this rare.
