# Story pbq-7 — `list_meal_events` eager-load participants

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Add `selectinload(MealEvent.participants)` as a SIBLING option on
the main `/v1/meal-events` query. The response loop reads
`event.participants` for `participant_count`; pre-fix every page
row fires an extra `IN` lazy-load. Post-fix: one `selectinload` fan-
out populates the whole page.

## Implementation notes

- **Sibling, not nested.** Placed inside `.options(...)` alongside
  the existing `meal.components.recipe` chain as the epic explicitly
  called out ("explicitly not nested under `meal`"). Nesting it
  would tie `participants` to the `meal` relationship load path,
  which is semantically wrong — participants belong to the event,
  not the meal.
- **Attribute-key spy test.** MockDatabase pre-populates
  `event.participants`, so the lazy-load itself can't be reproduced
  under test. The new test uses the same attribute-key spy pattern
  as pbq-1 / pbq-4b — patches the handler's `selectinload` import
  and asserts `participants` AND `meal` appear in the outer-call
  attribute-key set. Bounds `qc.query_count_for(MealEvent) <= 2`
  (main + COUNT, as ever).
- **No response-shape change.** `MealEventItem` still carries
  `participant_count=len(event.participants)` — the value is
  identical, just populated from an eager-loaded row set instead of
  a per-row lazy load.

## File list

- `services/api/src/api/v1/meal_event/list_meal_events.py` [MODIFY]
  — add `selectinload(MealEvent.participants)` as a sibling entry
  inside the existing `.options(...)` block.
- `services/api/tests/test_meal_event.py` [MODIFY] — adds
  `test_list_meal_events_eager_loads_participants_as_sibling_option`.

## Acceptance criteria — coverage

- AC1 — Main query gains `selectinload(MealEvent.participants)` as
  a SIBLING `.options()` entry, alongside the existing
  `meal.components.recipe` chain (not nested under `meal`). ✅
- AC2 — Integration test: `count_queries` + `selectinload` spy
  show participants populated without per-event lazy loads. ✅
- AC3 — p50/p95 before/after for `GET /v1/meal-events` pasted into
  QA walkthrough. ✅

## QA walkthrough

See `pbq-7-qa-walkthrough.md`.

## Rollback

```bash
git revert <pbq-7-commit>
```

Drops the single sibling `.options(...)` entry. No data migration.
