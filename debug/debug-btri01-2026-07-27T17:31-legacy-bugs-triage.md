---
hash: btri01
type: debug
created: 2026-07-27T17:31:00-06:00
title: Triage legacy BUGS.md reports against current main — close fixed, file real
from: BUGS.md
status: ready
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
