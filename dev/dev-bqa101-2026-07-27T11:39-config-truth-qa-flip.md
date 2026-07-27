---
hash: bqa101
type: dev
created: 2026-07-27T11:39:00-06:00
title: Config truth — qa flip to installed tools, runner resolution green
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: done
owner: /devx-2026-07-27T1221-13346
branch: feat/dev-bqa101
---

## Goal
Make the `qa:` block in `devx.config.yaml` stop lying and turn E-1 green. The `projects:` runner table and `run-eval.sh` dispatcher already landed at RED; the only remaining lie is `qa.browser_harness: playwright` / `qa.scripted_test_runner: playwright` — playwright is installed nowhere in this repo. `browser_harness` flips to `none` (interim-truthful; the final `claude-in-chrome` value waits for the Phase 3 enum extension and lands in Phase 5/bqa105).

## Acceptance criteria
- [x] `devx.config.yaml` has `qa.browser_harness: none` and `qa.scripted_test_runner: flutter-drive`; no occurrence of `playwright` remains anywhere in the file.
- [x] `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh` (cwd `_devx/workstreams`) exits 0; output pasted as evidence in the status log / PR.
- [x] `devx config get qa.browser_harness` prints `none`; `devx config get qa.scripted_test_runner` prints `flutter-drive`.
- [x] The eval script `e1_runner_resolution.sh` is NOT re-authored — it was authored at RED; this story only re-runs it and watches it go green (tests-first discipline).

## Technical notes
- Files: `devx.config.yaml` only.
- Two-step flip is deliberate: `browser_harness` is the constrained upstream enum (`[playwright, cypress, none]` today; `claude-in-chrome` added in bqa103); `scripted_test_runner` is a free string. Schema validation is currently documentation-only (unenforced), but the conservative ordering costs nothing.
- Parallel-safe with bqa102 and bqa103 (disjoint files/repos).
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 1.

## Status log
- 2026-07-27T11:39 — emitted from plan 41ee13 at RED-gate PASS (tests-first phase; RED artifact `evals/e1_runner_resolution.sh` observed failing right-reason, see `evals/RED-report.md`).
- 2026-07-27T12:21:55-06:00 — claimed by /devx in session /devx-2026-07-27T1221-13346
- phase 2: spec ACs direct (v2 native); 4 ACs; workstream=browser-qa-agent; red-artifacts=`browser-qa-agent/evals/e1_runner_resolution.sh`. Re-ran the RED artifact on `main` before touching code and watched it fail right-reason: runner-resolution half already green (`4 planned (all with commands) + 2 deferred`), threshold half RED (`MISSING BEHAVIOR: devx.config.yaml still names playwright 2 time(s)`), exit 1.
- phase 3: flipped `qa.browser_harness: playwright → none` and `qa.scripted_test_runner: playwright → flutter-drive`, plus a comment recording why the flip is two-step (constrained enum upstream; final driver value lands in bqa105 after bqa103's enum extension). One file touched: `devx.config.yaml`. Eval artifact NOT re-authored (AC #4) — `git diff --name-only main..HEAD` lists `devx.config.yaml` only.
- phase 4: single-pass adversarial review (10-line diff — below the parallel-agent threshold); 2 findings (1 HIGH, 1 MED, 0 LOW); ALL fixed in-place — HIGH: the first draft of the explanatory comment used the literal string `playwright` twice, which would have kept `grep -c playwright` at 2 and flipped E-1 straight back to RED while *looking* like the flip had landed; caught and rewritten before the first eval run. MED: the comment named the future driver token literally, re-creating the same grep-collision class one phase downstream — removed the literal, kept the bqa103/bqa105 hash pointers. Also verified each factual claim the comment makes rather than trusting it: `flutter drive` is genuinely what the harness invokes (`services/e2e/scripts/run_all.sh:62`), `none` is legal in the current upstream enum (`design.md:47`), and no sibling eval greps this file for any other token. Re-review clean; E-1 re-run green after the fixes.
- phase 5: local CI — touched surface is `devx.config.yaml` only, which intersects no `projects[*].path` (api/utils/app/e2e/workstream-evals), so no lint/test runner applies; the governing gate is E-1 itself. Coverage informational under YOLO. Evidence (cwd `_devx/workstreams`, exit 0):
  ```
  runner resolution OK: 4 planned (all with commands) + 2 deferred
  E-1 GREEN: all 6 expectations resolve (or legally defer) and the qa: block names no uninstalled tools
  ```
  `devx config get qa.browser_harness` → `none`; `devx config get qa.scripted_test_runner` → `flutter-drive`; `grep -c playwright devx.config.yaml` → `0`. All 4 ACs met.
- phase 6: committed `a5f997c` (`devx.config.yaml` + this spec).
- phase 7: pushed `feat/dev-bqa101`; PR #3 opened against `main` (https://github.com/LeoTheMighty/palateful/pull/3). `devx pr-body` rendered with zero unresolved placeholders on the final pass. Two earlier pr-body attempts mis-passed `--tour-orientation` (it takes a path to the tour JSON, not inline prose, and not markdown) — both fail-softed to a tour section without the text fallback, and the body was re-rendered and `gh pr edit`-ed to the correct form; noting the flag's contract here because it is not obvious from the flag name.
- phase 7.5: tour gathered, narrated (2 stops, 3 decision-ledger entries, 1 fully grep-verified trail), validated by `devx tour build`, published to the `devx-tours` orphan branch (commit `96dfa43`, branch created). Linked from the PR body with the orientation fallback.
- phase 7: remote CI came back **failure** on run 30293935751 (`devx-ci` / `test`). Investigated before assuming ownership: the failure is **pre-existing and unrelated to bqa101** — `gh run list --workflow=devx-ci.yml` shows `failure` for every retained run including `push` to `main`, predating this branch. Root cause: `.github/workflows/devx-ci.yml:43` ran `npm test --silent` with no `--if-present` guard while its sibling `lint` (:31) and `coverage` (:55) jobs both have one, and `package.json` declares no `test` script. Filed `debug/debug-dvxci1-*.md` + DEBUG.md row, and applied the one-line root-cause fix on this branch per the skill's fix-the-root-cause-on-the-branch rule (`6ea893d`). **Scope note**: this reaches outside the spec's declared `devx.config.yaml only` surface into shared CI infra — deliberate and flagged, because the alternative was that no devx PR in this repo can ever merge (PRs #1, #2, #3 were all stuck on the same red). The fix makes the job a no-op here, so the debug spec leaves open for the user whether a TS/JS `devx-ci` should exist at all in a Python/Flutter repo where `ci.yml` already runs pytest + flutter test.
- phase 7: post-fix, `devx-ci` is **green** (run 30294452547 — `test` job passes in 18s, confirming the dvxci1 root cause). `ci.yml` however came back **failure** on `flutter-test`: 3 tests in `app/test/features/activity/imports_tab_test.dart`. Again checked ownership before acting — `main`'s own run 30293754580 fails with the *identical* three tests and identical counts (`1521 tests passed, 3 failed`), and bqa101 touches no Dart. Filed `debug/debug-imptab1-*.md` + DEBUG.md row with the evidence (assertions find **zero** widgets, not wrong ones → points at the bucketing path, not a copy change) and did **not** expand scope a second time to fix it — that is unrelated feature work, not a drive-by.
- phase 8: `devx merge-gate bqa101` → `{"merge":false,"reason":"CI not green (conclusion=failure)","advice":["wait for CI"]}`; `check-hold 3` → `{"hold":false}` (no hold). Not merged. The gate's "wait for CI" advice cannot resolve here — CI is terminally failed on a pre-existing red, so re-polling would loop forever — and merging would require an `--admin` override that is not authorized. **PR #3 is left open pending the user's call on imptab1** (fix it, or override). All bqa101 ACs are met and E-1 is green regardless.
- 2026-07-27T19:55 — merged via PR #3 (squash → 46336bd). Unblocking took
  two out-of-scope reds filed at Phase 7, neither caused by this story:
  dvxci1 (`devx-ci` `test`) and imptab1 (`flutter-test`). They were a mutual
  block — PR #3 needed imptab1 fixed, and imptab1's PR #6 needed dvxci1's
  workflow line. Resolved by landing imptab1 off `main` as PR #6 with the
  dvxci1 line ported byte-identically, then merging `origin/main` back here;
  the workflow file resolved with no conflict. No merge-gate override was
  used — `devx merge-gate bqa101` returned `{"merge":true}` on a fully green
  PR. bqa102 ∥ bqa103 are now unblocked.
