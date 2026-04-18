# Story cpms-2: Backend — remove populate-from-calendar endpoint + tests

**Status:** done
**Epic:** epic-calendar-per-meal-shopping-add

## Goal

Net deletion. Remove the `POST /v1/shopping-lists/{list_id}/populate-from-calendar`
endpoint, its Endpoint class, its routes-entry, its tests, and its doc
section. No shim — in dogfood the 404 window is effectively zero
(cpms-1 shipped the per-card replacement in the same sprint cycle).
Shared helpers (`get_user_calendar_ids`, `utils/deadline.py::calculate_item_due_date`)
stay — both have live callers outside this module. The surviving
`populate_from_recipe` handler's WebSocket broadcast already covers
the per-item `item_added` events for connected shopping-list members,
so real-time sync is preserved.

## Scope

### Source

- DELETE `services/api/src/api/v1/shopping_list/populate_from_calendar.py`.
- EDIT `services/api/src/api/v1/shopping_list/__init__.py` — drop the
  `from .populate_from_calendar import PopulateFromCalendar` import
  (line 17) and the `"PopulateFromCalendar"` string in `__all__`
  (line 48).
- EDIT `services/api/src/routers/v1/shopping_list_router.py` — drop
  the `PopulateFromCalendar` name from the `from api.v1.shopping_list
  import (...)` block and delete the
  `@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")`
  handler (lines 300–317).

### Tests

- DELETE `services/api/tests/test_populate_from_calendar.py` in full.
- EDIT `services/api/tests/test_coverage_gaps.py` — remove the section 3
  header comment (around lines 226–229) and the
  `TestPopulateFromCalendarExtended` class (lines 231–525). Keep all
  other classes intact.
- EDIT `services/api/tests/test_meal_calendar_xor_constraint.py` —
  the comment at lines 134–136 references `PopulateFromCalendar` as
  justification for not adding a CheckConstraint. Reword to drop the
  deleted-endpoint reference but preserve the invariant (source_meal_id
  is descriptive provenance and may co-exist with recipe_id +
  meal_event_id on a row).

### Docs

- EDIT `docs/SHARED_SHOPPING_CART.md` — delete the "Calendar
  Integration" block at lines 677–691 that documents the endpoint.
- EDIT `_bmad-output/planning-artifacts/architecture.md` — append a
  dated strikethrough note at line 1091 noting the endpoint is
  removed per FR-CPMS-1.

### Shared helpers stay

- `get_user_calendar_ids` — confirmed callers in `list_meal_events.py`
  and `list_recurrence_rules.py`.
- `utils/deadline.py::calculate_item_due_date` — confirmed callers in
  `populate_from_recipe.py` and `get_deadlines.py`.

## Acceptance Criteria

1. No Python module at
   `services/api/src/api/v1/shopping_list/populate_from_calendar.py`.
2. `from api.v1.shopping_list import PopulateFromCalendar` raises
   `ImportError`; `__all__` no longer lists it.
3. `POST /v1/shopping-lists/{list_id}/populate-from-calendar` returns
   404 (FastAPI no longer registers the route).
4. `npx nx run api:lint` passes. `npx nx run api:test` passes at the
   pinned **100% coverage** for `services/api/src/` — no orphaned lines
   left behind. `npx nx run migrator:check-models` is unchanged
   (no model edits).
5. `docs/SHARED_SHOPPING_CART.md` no longer documents the endpoint.
6. `rg 'populate[-_]from[-_]calendar|PopulateFromCalendar' services/
   docs/` returns no runtime hits (matches inside `_bmad-output/**`
   are planning artifacts and are allowed).
7. The row-level invariant in `test_meal_calendar_xor_constraint.py`
   (`test_no_new_check_constraint`) still guards that no
   `source_meal`-gated CheckConstraint is added.
8. `architecture.md` carries a dated strikethrough note at line 1091
   pointing to FR-CPMS-1 as the authority for the removal.

## Tests

- No new tests added. `test_populate_from_recipe.py` and the
  surviving classes in `test_coverage_gaps.py` continue to exercise
  the per-recipe add path.
- Coverage re-runs clean at 100% — deleted helpers would only trip
  coverage if other production code referenced them; grep above
  confirms the module's two shared helpers have live callers.

## File List

Modified:
- `services/api/src/api/v1/shopping_list/__init__.py`
- `services/api/src/routers/v1/shopping_list_router.py`
- `services/api/tests/test_coverage_gaps.py`
- `services/api/tests/test_meal_calendar_xor_constraint.py`
- `docs/SHARED_SHOPPING_CART.md`
- `_bmad-output/planning-artifacts/architecture.md`

Deleted:
- `services/api/src/api/v1/shopping_list/populate_from_calendar.py`
- `services/api/tests/test_populate_from_calendar.py`

## QA Walkthrough

See `cpms-2-qa-walkthrough.md`.
