---
hash: btri01
type: debug
created: 2026-07-27T17:31:00-06:00
title: Triage legacy BUGS.md reports against current main — close fixed, file real
from: BUGS.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/debug-btri01
---

## Goal
The pre-devx BUGS.md holds five undated bug reports that likely predate epics which have since landed. Verify each against current main (and prod where possible); close the fixed ones with evidence, file a dedicated `debug/` spec for any that still reproduce.

## Acceptance criteria
- [ ] "Creating a Meal breaks" — verified against the landed Meals epics (meals-create-and-view etc.); closed with evidence or filed as its own debug spec
- [ ] "PUSH NOTIFICATIONS" (never seen one work) — verified against the landed notifications epics + `inspect_user_push.py` output; closed or filed
- [ ] "Logging out shows a weird auth0 page" — verified against bas-1 (`f839f67`, returnTo on Auth0 native logout); closed or filed
- [ ] "Shopping cart still broken / can't open / WebSocket errors" — verified against bas-3 (`e781a56`, cart open reliability + WS error reporting) and Crashlytics; closed or filed
- [ ] "Strange errors when token needs refresh" — verified against bas-4 (`db1a8e4`, Dio interceptor logout on refresh failure); closed or filed
- [ ] BUGS.md annotated (or trimmed) so it no longer double-tracks anything alive in DEBUG.md

## Technical notes
- These reports sit in the second section of BUGS.md, above the "old" markers. The bas-1..4 epic (`epic-bugs-auth-and-shopping`) landed after they were written and targets four of the five directly.
- Use `audit_errors.py` (aggregate then drill) and Crashlytics to check for live occurrences rather than only code inspection.

## Status log
- 2026-07-27T17:31 — imported from BUGS.md during BMAD→devx migration
- 2026-07-27T11:31:30-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
- 2026-07-27T17:44:24.959Z — loop iteration 1: Triaged the two auth items from legacy BUGS.md — closed the token-refresh report with new passing regression tests, and refiled the Auth0 logout report as a live bug after finding bas-1 shipped a malformed returnTo.
  - Change: Added app/test/core/services/api_client_401_refresh_test.dart — 5 passing tests pinning the bas-4 401-refresh interceptor (refresh succeeds/returns-false/throws, retry-also-401 loop guard, no-auth-service), the tests bas-4's own ACs specified but never shipped
  - Change: Filed debug/debug-lgort1-…-auth0-logout-returnto-malformed.md: bas-1's returnTo puts Environment.auth0Scheme (com.palateful.app) in the path slot auth0_flutter fills with the bundle id (com.palateful.palateful), so the logout report still reproduces
  - Change: Filed debug/debug-cldb01-…-client-latencies-db-auth-500.md for a live prod 500 (DB password auth failure on POST /v1/client-latencies) found while gathering error evidence
  - Change: Annotated BUGS.md with per-item triage verdicts for the logout and token-refresh reports, added both new specs to DEBUG.md, and added a MANUAL.md item to read back the Auth0 tenant's Allowed Logout URLs
  - Learning: Prod error_logs is effectively empty (21 rows total, 20 of them worker audit rows) and prod has only 2 users / 2 meals / 3 meal_events — absence of errors is NOT usable evidence for closing the remaining three reports; code inspection and Crashlytics are the only real sources
  - Learning: bas-1 is a no-op-at-best: auth0_flutter's WebAuthentication.logout() already defaults returnTo to the SDK-registered callback URL, so passing an explicit hand-built string can only regress. The epic doc's claim that 'no Auth0 dashboard config' was needed is also wrong — Allowed Logout URLs is a separate list from Allowed Callback URLs
  - Learning: Environment.auth0Scheme (com.palateful.app) != the iOS bundle id / Android applicationId (com.palateful.palateful); any code that conflates them for Auth0 URL construction is broken
  - Learning: The bas-* epic stories were merged without the unit tests their own acceptance criteria listed — worth checking bas-2/bas-3 for the same gap in later iterations
  - Learning: bin/prod-script works with the ambient AWS creds, but the permission classifier blocks runs whose script text touches push_tokens/credential-shaped columns — the inspect_user_push.py data AC #2 wants may need the user to run it
