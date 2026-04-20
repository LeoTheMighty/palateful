# Story cmt-5 — Flutter: manual timer header button + ManualTimerSheet

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** cmt-4 (ships the `resolveCookTimer` helper and the `_activeTimers` surface).

## Scope

- New `ManualTimerSheet` widget — digits-only minute field + 40-char label field + disabled-until-valid Start button. Returns `(int minutes, String label)`.
- `disambiguateTimerLabel(requested, existing)` pure helper appends `" 2"`, `" 3"` when a collision would otherwise produce two identical active-timer chips.
- `cook_mode_screen._buildHeader` gains a persistent 48×48 `Icons.timer_outlined` `IconButton` between the AI chat button and the cooking-time pill. Visible online AND offline.
- `_showManualTimerSheet()` opens the sheet; on submit runs the label through `disambiguateTimerLabel` and calls `_startTimer(Duration(minutes: n), label)` — reusing the same path as extracted/regex timers.

## File list

- `app/lib/features/recipes/cook_mode/widgets/manual_timer_sheet.dart` [NEW]
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` [MODIFY] — header button + `_showManualTimerSheet` + extra import
- `app/test/manual_timer_sheet_test.dart` [NEW]

## Acceptance criteria

- AC1 — 48×48 header button between AI chat and cooking-time pill; tooltip "Add a timer"; visible offline.
- AC2 — Numeric field filters to digits (`FilteringTextInputFormatter.digitsOnly`), validates `[1, 360]`, `min` suffix.
- AC3 — Submit invokes callback with `(int, String)`; cook_mode wraps the label with `disambiguateTimerLabel` before calling `_startTimer`.
- AC4 — `disambiguateTimerLabel` appends `" 2"`, `" 3"`, …, skipping gaps correctly.
- AC5 — Shares the active-timer chip / notification path with extracted/regex timers — no source badge.
- AC6 — 7 widget tests + 4 disambiguation tests all green.
- AC7 — Header button still visible when `_isOffline=true` (shared IconButton sits outside the `!_isOffline` conditional that hides AI chat).
- AC8 — Manual-entry tap flow end-to-end covered in cmt-6 integration.
