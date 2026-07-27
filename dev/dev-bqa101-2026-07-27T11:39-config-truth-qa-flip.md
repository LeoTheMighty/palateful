---
hash: bqa101
type: dev
created: 2026-07-27T11:39:00-06:00
title: Config truth — qa flip to installed tools, runner resolution green
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
branch: feat/dev-bqa101
---

## Goal
Make the `qa:` block in `devx.config.yaml` stop lying and turn E-1 green. The `projects:` runner table and `run-eval.sh` dispatcher already landed at RED; the only remaining lie is `qa.browser_harness: playwright` / `qa.scripted_test_runner: playwright` — playwright is installed nowhere in this repo. `browser_harness` flips to `none` (interim-truthful; the final `claude-in-chrome` value waits for the Phase 3 enum extension and lands in Phase 5/bqa105).

## Acceptance criteria
- [ ] `devx.config.yaml` has `qa.browser_harness: none` and `qa.scripted_test_runner: flutter-drive`; no occurrence of `playwright` remains anywhere in the file.
- [ ] `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh` (cwd `_devx/workstreams`) exits 0; output pasted as evidence in the status log / PR.
- [ ] `devx config get qa.browser_harness` prints `none`; `devx config get qa.scripted_test_runner` prints `flutter-drive`.
- [ ] The eval script `e1_runner_resolution.sh` is NOT re-authored — it was authored at RED; this story only re-runs it and watches it go green (tests-first discipline).

## Technical notes
- Files: `devx.config.yaml` only.
- Two-step flip is deliberate: `browser_harness` is the constrained upstream enum (`[playwright, cypress, none]` today; `claude-in-chrome` added in bqa103); `scripted_test_runner` is a free string. Schema validation is currently documentation-only (unenforced), but the conservative ordering costs nothing.
- Parallel-safe with bqa102 and bqa103 (disjoint files/repos).
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 1.

## Status log
- 2026-07-27T11:39 — emitted from plan 41ee13 at RED-gate PASS (tests-first phase; RED artifact `evals/e1_runner_resolution.sh` observed failing right-reason, see `evals/RED-report.md`).
