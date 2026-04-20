# Story cmt-2 — Persist timers in `create_recipe_task` with clamp + independent audit

**Status:** in-progress
**Epic:** epic-cook-mode-timers
**Depends on:** cmt-1 (parsed_recipe JSONB now carries `steps[].timers`).

## Scope

Extend `create_recipe_task`'s existing structured-steps path (at `:134`) to read `step_data.get("timers", [])`, apply clamp + filter, and pass `timers=clean_timers` to `RecipeStep(...)`. On any dropped entry, write an independent `service="worker", error_type="TimerClamp"` audit row via a new `_log_timer_clamp` helper (mirrors `advance_recurrence_windows._log_audit`).

## Clamp rules

- Cap at 10 timer entries per step.
- `duration_minutes` must be `int` in `[1, 360]`; anything else drops.
- `label` coerced to `str`, `strip()`ed, truncated to 40 chars; empty/missing label defaults to `"timer"`.
- Non-dict entries dropped.

## File list

- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` [MODIFY] — clamp + audit helper + extend structured-step path to pass `timers` to `RecipeStep`.
- `libraries/utils/test/test_create_recipe_task_timers.py` [NEW] — clamp behaviour, dropped-entry audit row, all-invalid all-drop path.
- `services/api/tests/test_create_recipe_from_import_with_timers.py` [NEW] — integration test exercising the HTTP GET shape via `GetRecipe` so we round-trip through persist + Pydantic response.

## Acceptance criteria

- AC1 — Clean list of timer dicts is passed to `RecipeStep(..., timers=clean_timers)`.
- AC2 — Clamp logic: cap 10, duration `int∈[1,360]`, label coerced + trimmed + 40-char truncate, default label "timer".
- AC3 — Audit row written with `service="worker", error_type="TimerClamp"` via independent `db.commit()` in try/except. Survives main-transaction rollback.
- AC4 — Unit: step with `timers:[{duration_minutes:15,label:"simmer"}]` → RecipeStep.timers equals that exact list.
- AC5 — Unit: 12 timer entries including 2 out-of-range and 2 wrong-type → 8 persisted; 1 audit row; dropped count reflects cap + filter.
- AC6 — Unit: all-invalid timers → `RecipeStep.timers = []`, one audit row, item status "completed".
- AC7 — Unit: post-clamp exception → audit row still persists (independent commit).
- AC8 — `services/api` coverage remains 100%.
