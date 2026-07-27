# DEBUG — Bugs to fix

Conventions: `[ ]` ready · `[/]` in-progress · `[-]` blocked · `[x]` done. Status field on each entry is the source of truth; checkbox is the glanceable mirror.

## Imported from BUGS.md (2026-07-27)

- [/] `debug/debug-rbv101-2026-07-27T17:30-book-view-card-sizing.md` — Recipe-book view renders meal and recipe cards at different sizes. Status: in-progress. From: BUGS.md (newest report).
- [/] `debug/debug-btri01-2026-07-27T17:31-legacy-bugs-triage.md` — Triage legacy BUGS.md reports against current main (meal creation, push notifs, auth0 logout, shopping cart, token refresh — all likely fixed by bas-1..4 + landed epics); close with evidence or file real debug specs. Status: in-progress.

## Found during import verification (2026-07-27)

- [ ] `debug/debug-rcres1-2026-07-27T18:21-deleted-occurrence-resurrection.md` — Deleted recurring-meal occurrence resurrects on next materialize pass (delete detaches the row from its rule → invisible to the materializer's dedup → slot re-inserts; also `is_recurring` never set on materialized rows). Status: ready. From: bugs-cal-3b verification.

