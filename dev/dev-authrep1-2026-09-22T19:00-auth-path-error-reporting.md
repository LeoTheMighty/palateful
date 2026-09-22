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

- [ ] Every catch in the auth path reports to Crashlytics with enough context
      to tell the failure modes apart (Auth0 web-auth failure, account-linking
      `api.access.deny()`, `RENEW_FAILED` at cold start, storage failure).
- [ ] Pre-auth failures go to Crashlytics, **not** the `error_logs` mirror,
      which needs a valid token and so can't receive them.
- [ ] Widen `tools/no-silent-catch-check.sh` beyond
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
