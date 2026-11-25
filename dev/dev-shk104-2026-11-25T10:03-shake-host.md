---
hash: shk104
type: dev
created: 2026-11-25T10:03:01-07:00
title: Shake host — prompt, suppression, feedback for every admitted user
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 4
status: ready
owner: null
branch: feat/dev-shk104
blocked_by: [shk102, shk103]
---

## Goal

The host above the router, the modal-route observer on every navigator, the client ring, and the prompt; every admitted user (admins too) routes to feedback. Ring stays `admins`: the dogfood build. Turns E-1, E-2, E-3 green and adds them to CI's Flutter job.

## Acceptance criteria

- [ ] `bash run-eval.sh shake-to-report/evals/E-1_user_path.sh` (from `_devx/workstreams`) exits 0 (EVAL-GREEN); likewise `E-2_everyday_motion.sh` and `E-3_no_interruption.sh`.
- [ ] E-5: `flutter test test/core/shake/shake_eligibility_test.dart` passes; the whole `flutter test` suite passes.
- [ ] CI's Flutter job runs the three evals after `flutter test` and is green.
- [ ] `E-4_role_and_ring.sh` still exits 1, now only for `x1-route-missing` and the admin-copy markers.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- The prompt needs an explicit `persist: MediaQuery.accessibleNavigationOf(context)`: in Flutter 3.41 a snackbar with an action never times out otherwise (design § Host, RQ10).
- The evals boot the real `PalatefulApp`, feed sensors_plus's `user_accel` channel and expect lifecycle `resumed`; prompt copy is fixed by FR-5.
- Use `defaultTargetPlatform`, never `dart:io` `Platform`.

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 4). Gate 4: PASS.
