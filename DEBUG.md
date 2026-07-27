# DEBUG — Bugs to fix

Conventions: `[ ]` ready · `[/]` in-progress · `[-]` blocked · `[x]` done. Status field on each entry is the source of truth; checkbox is the glanceable mirror.

## Imported from BUGS.md (2026-07-27)

- [/] `debug/debug-rbv101-2026-07-27T17:30-book-view-card-sizing.md` — Recipe-book view renders meal and recipe cards at different sizes. Status: in-progress. From: BUGS.md (newest report).
- [/] `debug/debug-btri01-2026-07-27T17:31-legacy-bugs-triage.md` — Triage legacy BUGS.md reports against current main (meal creation, push notifs, auth0 logout, shopping cart, token refresh — all likely fixed by bas-1..4 + landed epics); close with evidence or file real debug specs. Status: in-progress.

## Found during /devx runs (2026-07-27)

- [ ] `debug/debug-imptab1-2026-07-27T18:50-imports-tab-sections-not-rendering.md` — Imports tab: 3 widget tests red on `main` (`imports_tab_test.dart`), assertions find **zero** widgets for `Auto-Imported · 1` / `Done`, pointing at the bucketing path rather than a copy change. Blocks `ci.yml / flutter-test` → blocks the merge gate for every PR. Status: ready. From: bqa101 Phase 7 remote-CI failure. **May be a user-visible regression, not just test drift.**
- [/] `debug/debug-dvxci1-2026-07-27T18:35-devx-ci-npm-test-missing-script.md` — `devx-ci` `test` job red on every run (incl. `push` to `main`): `npm test --silent` with no `test` script in package.json; sibling lint/coverage jobs guard with `--if-present`, test did not. One-line fix applied on bqa101's PR #3 — verified green (run 30294452547). Status: in-progress. From: bqa101 Phase 7. **Open question in the spec**: whether the TS/JS `devx-ci` should exist at all in a Python/Flutter repo where `ci.yml` already runs the real suites.

## Found during import verification (2026-07-27)

- [/] `debug/debug-rcres1-2026-07-27T18:21-deleted-occurrence-resurrection.md` — Deleted recurring-meal occurrence resurrects on next materialize pass (delete detaches the row from its rule → invisible to the materializer's dedup → slot re-inserts; also `is_recurring` never set on materialized rows). Status: in-progress. From: bugs-cal-3b verification.

