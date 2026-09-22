---
hash: authrep1
type: dev
created: 2026-09-22T19:00:00-06:00
title: N1 — the auth path reports its failures (both of Leo's auth complaints are uncollected)
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: in-progress
owner: /devx-c2872fff
branch: feat/dev-authrep1
---

## Goal

Two of Leo's three complaints are auth, and neither is collected anywhere:
`auth_service.dart` and `login_screen.dart` make no `ErrorReporter` calls,
`login()` swallows every exception into one string, and the credential-restore
catch wipes the session with a `debugPrint` (clidet1, 2d). A push channel can't
forward a signal that doesn't exist, so this ranks #3 overall.

## Acceptance criteria

- [x] Every catch in the auth path reports to Crashlytics with enough context
      to tell the failure modes apart (Auth0 web-auth failure, account-linking
      `api.access.deny()`, `RENEW_FAILED` at cold start, storage failure).
- [x] Pre-auth failures go to Crashlytics, **not** the `error_logs` mirror,
      which needs a valid token and so can't receive them.
- [x] Widen `tools/no-silent-catch-check.sh` beyond
      `app/lib/features/**/services/` so it can see `app/lib/core/` (G12, from
      clidet1's N5). Today the guard can't see the file that swallows most.

## Technical notes

- Root causes are 2d's: `RENEW_FAILED` wiping a good refresh token on a
  transient network blip; the account-linking Action's deliberate deny.
- Client-side, so the Terraform apply-path issue does not apply.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: —.
- 2026-09-22T12:00 — claimed for /devx (hand-claim: main lane frozen for #41's Terraform apply, so the claim commit lands on feat/dev-authrep1, not main — coordinator leonidbelyi-41). Base: 64c8b7f5 (post-#35).
- 2026-09-22T13:40 — phase 2: spec ACs direct (v2 native); 3 ACs; workstream=none; red-artifacts=none.
- 2026-09-22T14:20 — phase 3: auth path reports at every catch. Scope grew beyond the spec's list once the widened guard could see: `api_client.dart`'s 401 refresh interceptor (3 catches, incl. the refresh-succeeded-then-retry-failed case), `main.dart`'s cold-start block (the forced logout on a failed `/me`), and `auth_service_web.dart`'s callback paths. Sink chosen per event by whether the token can still authenticate the mirror, not per call site.
- 2026-09-22T15:05 — phase 4: 3-agent parallel adversarial review (blind hunter / edge cases / acceptance audit); 30 findings (8 HIGH, 14 MED, 8 LOW); ALL fixed in-place. Load-bearing fix: the scanner had two false-verdict bugs in opposite directions — a `}` in a string after a `${...}` truncated the catch body (flagging a catch that reports) and safe tokens were matched against raw source (so a comment saying "rethrow" rescued a swallow) — plus the guard failed OPEN on a duplicated baseline row. Re-review clean; every finding now has a self-test fixture.
- 2026-09-22T15:20 — phase 5: local gates green — flutter test 1667 passed, flutter analyze 0 errors, no-silent-catch-check + 18-assertion self-test OK, `flutter build web --release` exit 0 (PR CI never compiles web; only pushes to main do, so a web-only break would surface as a failed deploy).
