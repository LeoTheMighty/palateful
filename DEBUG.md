# DEBUG — Bugs to fix

Conventions: `[ ]` ready · `[/]` in-progress · `[-]` blocked · `[x]` done. Status field on each entry is the source of truth; checkbox is the glanceable mirror.

## Imported from BUGS.md (2026-07-27)

- [/] `debug/debug-rbv101-2026-07-27T17:30-book-view-card-sizing.md` — Recipe-book view renders meal and recipe cards at different sizes. Status: in-progress. From: BUGS.md (newest report).
- [/] `debug/debug-btri01-2026-07-27T17:31-legacy-bugs-triage.md` — Triage legacy BUGS.md reports against current main (meal creation, push notifs, auth0 logout, shopping cart, token refresh — all likely fixed by bas-1..4 + landed epics); close with evidence or file real debug specs. Status: in-progress.

## Found during /devx runs (2026-07-27)

- [x] `debug/debug-imptab1-2026-07-27T18:50-imports-tab-sections-not-rendering.md` — Imports tab: 3 widget tests red on `main` (`imports_tab_test.dart`). Root cause: **test fixture rot, not a code regression** — fixtures hardcoded `2026-04-18` and aged past the 30-day recency cutoff at `imports_tab.dart:168`, which suppresses `completed`/`skipped` items only. Fixtures re-anchored to `now`; assertions unchanged. Status: done. PR: https://github.com/LeoTheMighty/palateful/pull/6 (merged 640987e). ~~May be a user-visible regression~~ — it is not; the cutoff is intended behaviour with See-all as the escape hatch.
- [x] `debug/debug-dvxci1-2026-07-27T18:35-devx-ci-npm-test-missing-script.md` — `devx-ci` `test` job red on every run (incl. `push` to `main`): `npm test --silent` with no `test` script in package.json; sibling lint/coverage jobs guard with `--if-present`, test did not. One-line fix landed via PR #6 (merged 640987e) — ported there byte-identically because dvxci1 and imptab1 were a mutual block. Status: done. **Open question still unresolved**: whether the TS/JS `devx-ci` should exist at all in a Python/Flutter repo where `ci.yml` already runs the real suites.
- [/] `debug/debug-rshred1-2026-07-27T21:35-rotation-red-artifacts-break-main-pytest.md` — `ci.yml / test` (pytest) red on `main` since `5a6174d` (rotation-self-heal RED stage): `ModuleNotFoundError: No module named 'utils.services.db_credentials'` at collection. RED artifacts merged to `main` import modules their implementing stories (`rsh103`, `rsh105`) haven't written yet, so the shared merge gate stands red for every unrelated PR. Status: in-progress. From: bqa101 Phase 8 post-merge check. **Fix is a policy decision** (don't merge RED to main, vs. exclude RED from default collection) — and `rsh101` is actively claimed by another session, so scope any fix to `ci.yml` collection config.

- [ ] `debug/debug-arci1-2026-07-27T23:10-await-remote-ci-single-workflow-blind-spot.md` — `devx devx-helper await-remote-ci` reports terminal `success` when the *newest* run is green, ignoring a sibling workflow that failed on the same `headSha`. Observed on `408aeaf`: the helper said success (`CI & Deploy`) while `devx-ci` was red and `devx merge-gate` correctly said `merge:false`. Defense-in-depth failure, not an incident — the gate caught it — but Phase 7 is documented as the place that waits for CI. Status: ready. From: rsh101 Phase 8.

## Found during import verification (2026-07-27)

- [/] `debug/debug-rcres1-2026-07-27T18:21-deleted-occurrence-resurrection.md` — Deleted recurring-meal occurrence resurrects on next materialize pass (delete detaches the row from its rule → invisible to the materializer's dedup → slot re-inserts; also `is_recurring` never set on materialized rows). Status: in-progress. From: bugs-cal-3b verification.

