---
hash: shk103
type: dev
created: 2026-11-25T10:03:01-07:00
title: Motion dependency and the shake recognizer
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 3
status: ready
owner: null
branch: feat/dev-shk103
blocked_by: []
---

## Goal

sensors_plus 6.1.x and its `NSMotionUsageDescription`, the one adapter that imports it, and the pure-Dart recognizer, unit-tested with synthesized traces. Nothing subscribes yet. Riskiest phase: no PR-time CI builds iOS or Android.

## Acceptance criteria

- [ ] `flutter test test/core/shake/shake_recognizer_test.dart` passes (the E-2 trace shapes plus a boundary case at every `ShakeTuning` edge).
- [ ] `flutter analyze` clean; `flutter build web --release` succeeds.
- [ ] `flutter build apk --debug` and `flutter build ios --simulator --no-codesign` both succeed locally; their last lines are pasted in the PR body.
- [ ] `sensors_plus` constrained `>=6.1.1 <7.0.0` (7.x needs AGP 8.12.1 / Gradle 8.13 / Kotlin 2.2.0).

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- `app/pubspec.yaml` on `main` fires Xcode Cloud. Do not bump the version; the PR body says one failed Xcode Cloud run is expected unless Leo bumps it.
- `app/lib/core/**` is under the silent-catch ratchet: no new swallowing catch.

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 3). Gate 4: PASS.
