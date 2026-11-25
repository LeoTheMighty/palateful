---
hash: shk106
type: dev
created: 2026-11-25T10:03:01-07:00
title: Admins get the dev-request form
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 6
status: ready
owner: null
branch: feat/dev-shk106
blocked_by: [shk105]
---

## Goal

An admin at prompt and tap gets `File a dev request?` / `Request` and arq103's route pushed on the root navigator; any doubt keeps the user path. Turns E-4 green, adds it to CI, then the device protocol. **External gate X-1: merge only after arq103's `/admin/dev-requests/new` is on `main`.**

## Acceptance criteria

- [ ] `bash run-eval.sh shake-to-report/evals/E-4_role_and_ring.sh` exits 0 (EVAL-GREEN); E-1…E-3 still exit 0.
- [ ] E-10: `flutter test test/features/profile/non_shake_paths_test.dart` passes.
- [ ] After the release that carries this (X-2): E-7's device protocol run on 1 iPhone and 1 Android phone, one Runs row per phone in `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md`.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- Import the path from `AdminDevRequestNewScreen.routePath`; never copy the string.
- The router's `/admin` redirect and the server's `require_admin_async` stay the authority; the host's role check is routing only.
- After E-7: Leo sets the ring to `everyone` in `terraform/environments/prod/main.tf` (an ops step, not this spec).

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 6). Gate 4: PASS.
