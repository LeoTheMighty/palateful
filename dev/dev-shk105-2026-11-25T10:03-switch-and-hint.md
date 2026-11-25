---
hash: shk105
type: dev
created: 2026-11-25T10:03:01-07:00
title: Device switch and discoverability hint
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 5
status: ready
owner: null
branch: feat/dev-shk105
blocked_by: [shk104]
---

## Goal

`Shake to report` in Profile's settings, remembered on the device, and the Send Feedback subtitle hint for eligible non-admins.

## Acceptance criteria

- [ ] E-9: `flutter test test/features/profile/shake_settings_test.dart` passes (off → 0 subscriptions now and after a restart; hint present only for an eligible non-admin).
- [ ] CI's Flutter job green, including E-1…E-3.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- SharedPreferences pattern of `app/lib/providers/theme_mode_provider.dart`; key `shake_report_enabled`, default on.

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 5). Gate 4: PASS.
