---
hash: bqa101
type: dev
created: 2026-07-27T11:39:00-06:00
title: Config truth — qa flip to installed tools, runner resolution green
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: in-progress
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
