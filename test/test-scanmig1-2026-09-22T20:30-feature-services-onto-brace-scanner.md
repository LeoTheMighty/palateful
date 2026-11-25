---
hash: scanmig1
type: test
created: 2026-09-22T20:30:00-06:00
title: migrate the feature-services silent-catch section onto the brace-matched scanner
from: dev/dev-authrep1-2026-09-22T19:00-auth-path-error-reporting.md
status: ready
owner: null
branch: null
---

## Goal

`tools/no-silent-catch-check.sh` now has two sections with two different
notions of "this catch reports". Section 1 (feature services) keeps the
original 40-line `sed` window; section 2 (`app/lib/core`, added by authrep1)
brace-matches the catch body via `tools/silent_catch_scan.py`.

The window accepts a safe token from a *neighbouring function*, so it passes
catches that swallow. Measured example, confirmed by palateful-4f and by the
scanner: `app/lib/features/shopping_cart/services/shopping_cart_service.dart:358`
is a pure `debugPrint` swallow of the whole WS message dispatch, and it
passes because `ErrorReporter.report(` appears at `:388` inside
`_handleError`. The allowlist's own header admits the cart case passes
"implicitly".

Not done inside authrep1 because switching section 1 turns today's passes
into failures, and each one needs a per-site decision (report it, surface
it, or allowlist it with a rationale) — that is a separate reviewable unit,
not a side effect of the auth work.

## Acceptance criteria

- [ ] Section 1 uses `tools/silent_catch_scan.py` instead of the `sed`
      window. Both sections then agree on what counts as reporting.
- [ ] Every catch the change newly reveals is resolved on its merits —
      reported, surfaced, or allowlisted with a rationale. Specifically
      `shopping_cart_service.dart:358`, the months-broken cart being one of
      Leo's three complaints.
- [ ] `tools/silent-catch-allowlist.txt` parsing is last-colon-anchored,
      like the core baseline reader: `IFS=:` breaks on any path containing a
      colon (see PR #47's `tools/stale-pointer-check.py` for the same bug).
      Today's entries are colon-free, so this is latent, not live.
- [ ] `tools/silent-catch-self-test.sh` gains a fixture per newly-covered
      shape.

## Technical notes

- The scanner already supports this: `--dir app/lib/features` plus a
  `--path-contains /services/` filter reproduces section 1's file set.
- Consider folding both sections into one baseline-style ratchet once they
  share a scanner; the allowlist's `file:lineno` entries rot on every
  refactor, which its own header documents.

## Status log
- 2026-09-22T20:30 — filed from authrep1 (out-of-scope work revealed while widening the guard to core). Blocked-by: —.
