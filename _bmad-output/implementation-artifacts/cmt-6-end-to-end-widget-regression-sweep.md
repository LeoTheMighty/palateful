# Story cmt-6 — End-to-end widget regression sweep

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** cmt-4, cmt-5 (all render paths in place).

## Scope

Adds `test/cook_mode_timers_integration_test.dart` covering the four epic paths (extracted-only, regex-only, manual, hybrid-is-fallback) and the defensive parse path for malformed wire payloads. Also ships a QA walkthrough with the manual device-test plan.

## Why integration by composition (not full-screen mount)

Mounting the full `CookModeScreen` requires wiring `getIt<ApiClient>` + `CookTimerNotificationService` + `RecipeCacheService` + a goroute context. The existing cook-mode tests use standalone widget replicas for the same reason — the `_buildStepContent` branch + the `_showManualTimerSheet` flow are pure-enough logic that composing the same decision rule directly in the test (`_resolveStepTimers`) is honest regression coverage without duplicating implementation. When cmp epic lands its ThemeExtension plumbing and DI simplifies, we can consider a proper mount-based integration test.

## File list

- `app/test/cook_mode_timers_integration_test.dart` [NEW]
- `_bmad-output/implementation-artifacts/cmt-6-qa-walkthrough.md` [NEW]

## Acceptance criteria

- AC1 — Existing cook-mode suites remain green (9 test files, 96 tests total).
- AC2 — Integration: structured one-timer step + instruction with more durations → exactly 1 button.
- AC3 — Integration: no structured + "Bake 25 min, rotate at 12 minutes" → 2 buttons.
- AC4 — Integration: empty structured + "rise until doubled" → 0 inline buttons.
- AC5 — Integration: hybrid-as-fallback case asserted (extracted suppresses regex).
- AC6 — Manual QA walkthrough file covers the 3 paths + hybrid on device.
