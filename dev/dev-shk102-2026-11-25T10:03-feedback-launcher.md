---
hash: shk102
type: dev
created: 2026-11-25T10:03:01-07:00
title: One feedback launcher with an app-wide flush
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 2
status: in-review
owner: palateful-72
branch: feat/dev-shk102
blocked_by: [shk101]
---

## Goal

Move Profile's feedback opener and offline flush into one launcher that takes a route and a trigger, and flush at startup and on every resume from the app root. Profile looks and behaves as before.

## Acceptance criteria

- [x] E-8: `flutter test test/features/profile/feedback_launcher_test.dart` passes in `app/` (queued item sent once from a non-Profile screen, queue empty, Profile never built; Profile's tile sends `trigger` `profile`, route `/profile`).
- [x] `flutter test test/features/profile/feedback_sheet_test.dart` still passes unchanged; `flutter analyze` clean; `bash tools/no-silent-catch-check.sh` exits 0.
- [ ] shk101 is deployed before this merges.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- Platform: `web` when `kIsWeb`, else from `defaultTargetPlatform`; never `dart:io` (design § Feedback launcher).
- The moved catches call `ErrorReporter.report` (the silent-catch guard covers `app/lib/features/**/services/`).

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 2). Gate 4: PASS.
- 2026-11-25 — implemented on `feat/dev-shk102` (`4ab24985`), PR into `feat/shake-report-workstream` (not `main`; not merged). E-8 `feedback_launcher_test.dart` 15/15 and `feedback_sheet_test.dart` 9/9 (file unchanged); full `flutter test` 1802 passed vs base 1787 (every base test present by name, +15 new); `flutter analyze` 165 issues, the same set as base `d2afd5f2` with line numbers normalized (0 new); `tools/no-silent-catch-check.sh` OK (16 feature service files vs 15); `flutter build web --release` built. The app-root tests boot the real `PalatefulApp`; 12 deliberate breakages (no startup or resume flush in `main.dart`, no sign-in gate, wrong trigger or route from Profile, no coalescing, web read from `defaultTargetPlatform`, a swallowed submit catch, the trigger dropped from the context, Profile's announcement or flush removed, query string kept) each fail only the tests aimed at them. The shell guard's 40-line window cannot see 2 of the launcher's 3 catches (a neighbouring `ErrorReporter.report(` satisfies it); `tools/silent_catch_scan.py` flags each one when stripped, and tests cover two of them. P0s E-1…E-4 still RED, same counts and markers as RED-report, controls pass: no motion listener exists until shk104. `devx gate evals f89791 --verify` PASS. Interpreted: flush concurrency coalesces (two observers on one resume would double-send); only Profile shows "Sent queued feedback"; the app-root observer now registers in E2E mode too. AC 3 (shk101 deployed first) is the merge gate's: both reach `main` in the workstream PR.
- 2026-11-25 — PR #138 opened into `feat/shake-report-workstream` at `c61d2cc9`.
