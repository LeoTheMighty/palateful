---
hash: shk102
type: dev
created: 2026-11-25T10:03:01-07:00
title: One feedback launcher with an app-wide flush
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 2
status: ready
owner: null
branch: feat/dev-shk102
blocked_by: [shk101]
---

## Goal

Move Profile's feedback opener and offline flush into one launcher that takes a route and a trigger, and flush at startup and on every resume from the app root. Profile looks and behaves as before.

## Acceptance criteria

- [ ] E-8: `flutter test test/features/profile/feedback_launcher_test.dart` passes in `app/` (queued item sent once from a non-Profile screen, queue empty, Profile never built; Profile's tile sends `trigger` `profile`, route `/profile`).
- [ ] `flutter test test/features/profile/feedback_sheet_test.dart` still passes unchanged; `flutter analyze` clean; `bash tools/no-silent-catch-check.sh` exits 0.
- [ ] shk101 is deployed before this merges.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- Platform: `web` when `kIsWeb`, else from `defaultTargetPlatform`; never `dart:io` (design § Feedback launcher).
- The moved catches call `ErrorReporter.report` (the silent-catch guard covers `app/lib/features/**/services/`).

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 2). Gate 4: PASS.
