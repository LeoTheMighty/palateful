# Story cmt-4 — Flutter: step timers row + upgraded regex fallback

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** (soft) cmt-2 for structured `step.timers` in the wire payload; this story ships independently because the regex path covers every legacy recipe.

## Scope

- Introduce a `StepTimer` data class + `extractTimers(instruction)` regex helper.
- New `StepTimersRow` widget renders horizontally-scrollable `OutlinedButton.icon`s, with `Tooltip` for range upper-bound labels.
- `resolveCookTimer(BuildContext)` helper consolidates the `CookModeTheme.cookTimer` vs. `colorScheme.tertiary` fallback so every timer surface (row + cmt-5 sheet) uses the same accent.
- `cook_mode_screen.dart` `_steps` becomes `List<_StepData>` with per-step `timers` parsed defensively at load.
- Render rule: **hybrid is fallback, not merge** — structured `step.timers` suppresses the regex even if the instruction text mentions additional durations.

## File list

- `app/lib/features/recipes/cook_mode/util/timer_regex.dart` [NEW]
- `app/lib/features/recipes/cook_mode/util/cook_timer_token.dart` [NEW]
- `app/lib/features/recipes/cook_mode/widgets/step_timers_row.dart` [NEW]
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` [MODIFY] — `_StepData`, `_populateFromData`, `_buildStepContent`, remove old `_buildInlineTimer`
- `app/test/timer_regex_test.dart` [NEW]
- `app/test/step_timers_row_test.dart` [NEW]

## Acceptance criteria

- AC1 — `_populateFromData` normalizes malformed step payloads to `timers: []` without crashing.
- AC2 — Hybrid rule: structured non-empty timers suppress the regex.
- AC3 — `extractTimers`: caps 2000 chars, max 10 matches, supports ranges (dash/en-dash/to), decimals, hour/minute/second aliases.
- AC4 — `timer_regex_test.dart` covers 20+ cases including ranges, decimals, aliases, empty, long, malformed.
- AC5 — `step_timers_row.dart` renders concise "N min label" / "N min" form, horizontally scrollable.
- AC6 — `resolveCookTimer` helper falls back to `colorScheme.tertiary` when extension not registered.
- AC7 — Widget test — one timer per `StepTimer` entry.
- AC8 — Widget test — hybrid-fallback verified via suppression check (covered in cmt-6 integration).
- AC9 — Existing cook-mode tests remain green.
