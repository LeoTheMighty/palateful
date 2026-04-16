# Story Pantry.4: Meal-Cooked → Pantry Decrement Hook

Status: done

## Story

As Leo marking a meal as cooked on the calendar,
I want the ingredients I used to be automatically decremented from my pantry,
so that the pantry doesn't drift from reality over time and "you already have" dedup on the shopping list keeps working.

## Context

Meal events are updated via `PUT /meal-events/{event_id}` (`services/api/src/api/v1/meal_event/update_meal_event.py:18`), which sets `meal_event.status`. The status lifecycle is `"planned" → "shopping" → "prepping" → "cooking" → "completed" | "skipped"` (values listed in `update_meal_event.py:14`). Today nothing happens when status flips to `"completed"`.

This story adds a pantry subscriber that fires when a meal event transitions to `"completed"` and decrements matching `pantry_ingredient` quantities by the recipe's ingredient quantities (scaled by `meal_event.servings` if present, otherwise by the recipe's native servings count — effectively a 1× scale).

This is the hardest story in the epic because of unit normalization. The recipe says "1 cup diced onion" and the pantry says "2 whole onions" — these don't cleanly subtract. Per epic design principle, the hook is **best-effort**: when units normalize cleanly, decrement; when they don't, skip silently and log at `WARNING`. Never block the user's action on a unit conversion failure.

The dispatcher infrastructure from pantry-3 (`libraries/utils/utils/events/`) is reused here — this story only adds a new event type and a new subscriber.

## Acceptance Criteria

1. New event dataclass `MealEventCompleted(user_id: UUID, meal_event_id: UUID, recipe_id: UUID, servings: float)` added to `libraries/utils/utils/events/events.py`.
2. `services/api/src/api/v1/meal_event/update_meal_event.py` dispatches `MealEventCompleted` after a successful commit when the status transitions from any non-`"completed"` value to `"completed"`. A status change that does not cross into `"completed"` (e.g., `prepping → cooking`) does not dispatch. A re-submission of `completed → completed` (client idempotency) does not dispatch.
3. New subscriber file `services/api/src/api/subscribers/pantry_meal_subscriber.py` registered in `register_subscribers()`. Behavior:
   - Loads the recipe with all `recipe_ingredients` eager-loaded.
   - Resolves the user's default pantry (`get_or_create_default_pantry`).
   - For each `recipe_ingredient`, looks up an active `pantry_ingredient` in the pantry with the same `ingredient_id`. If none, skip.
   - Computes the consumed quantity: `consumed = recipe_ingredient.quantity_normalized * (meal_event.servings / recipe.servings)`. If `meal_event.servings` is null, treat as `1.0` scale. If `recipe.servings` is null or 0, skip that ingredient (log `WARNING`).
   - Compares `unit_normalized` strictly. If pantry row's `unit_normalized != recipe_ingredient.unit_normalized`, skip the decrement silently, log at `WARNING` with ingredient + both units.
   - If units match, decrement: `new_quantity = max(0, pantry_row.quantity_normalized - consumed)`.
   - If `new_quantity == 0`, set `pantry_row.archived_at = now()` (item is used up; preserve row for history).
4. All decrements for a single event fire in one DB transaction. Partial failure: if the transaction fails, log at `ERROR` and swallow — the subscriber must not raise back to the caller.
5. Each successful decrement logs at `INFO`: `pantry_auto_decrement user_id=… ingredient_id=… from=X.X to=Y.Y`. Each skipped decrement (unit mismatch or missing pantry row) logs at `WARNING` or `DEBUG` respectively.
6. A simple decrement audit log is kept in a new table `pantry_ingredient_events`: `(id, pantry_id, ingredient_id, event_type, delta_quantity, source_meal_event_id, created_at)`. Rows are inserted for every decrement. This enables future debugging ("why did my pantry say X?") without requiring structured log retention. Migration is additive.
7. Re-cooking the same meal event (hypothetical — status already `"completed"`, user PATCHes again) does NOT double-decrement because AC #2 guards on transition. But if a dev agent later allows completed → planned → completed, that WOULD double-decrement. Acceptable for MVP — flag in Dev Notes.
8. No user-facing prompt or error on unit mismatch. No snackbar on the Flutter side for this hook. It is genuinely invisible — the pantry list screen (pantry-5) will reflect the new quantities on next load.
9. Unit tests for the subscriber:
   - Happy path: pantry has 100g flour, recipe uses 50g, meal servings match recipe servings → pantry now 50g, audit row inserted.
   - Servings scaling: recipe native 4 servings, meal event 2 servings → decrements are halved.
   - Unit mismatch: pantry has "2 whole onions", recipe has "1 cup diced onion" → no change, WARNING logged.
   - Missing pantry row: recipe uses butter, pantry has no butter → no error, no change.
   - Clamp to zero: pantry has 10g, recipe uses 100g → pantry becomes 0, archived, audit row for -10g (not -100g).
   - No recipe servings: `recipe.servings is None` → every ingredient is skipped with WARNING.
   - Partial match: recipe has 5 ingredients, pantry has 3 → 3 decremented, 2 skipped silently (DEBUG level).
10. Integration test: seed a user + recipe + pantry with known ingredients + meal event. PUT meal event to `"completed"`. Assert pantry quantities changed as expected and that `pantry_ingredient_events` rows were written.
11. The existing `ShoppingListItemPurchased` subscriber from pantry-3 continues to work unchanged (regression check).

## Tasks / Subtasks

- [ ] Task 1: Event type + migration (AC: #1, #6)
  - [ ] Add `MealEventCompleted` to `libraries/utils/utils/events/events.py`
  - [ ] Create new model `libraries/utils/utils/models/pantry_ingredient_event.py` for the audit table
  - [ ] New Alembic migration `YYYYMMDDHHmmss_add_pantry_ingredient_events.py` creates the table. Additive only.

- [ ] Task 2: Dispatch from update_meal_event (AC: #2)
  - [ ] Modify `services/api/src/api/v1/meal_event/update_meal_event.py:18` to capture `previous_status` before update
  - [ ] After commit, if `previous_status != "completed" and new_status == "completed"`, dispatch `MealEventCompleted`
  - [ ] Include `meal_event.servings` in the payload (read it from the updated row, not the input payload, so defaults apply)

- [ ] Task 3: Subscriber implementation (AC: #3, #4, #5)
  - [ ] `services/api/src/api/subscribers/pantry_meal_subscriber.py`
  - [ ] Opens its own DB session (same pattern as pantry-3 subscriber)
  - [ ] Loads recipe with `selectinload(Recipe.recipe_ingredients)` to avoid N+1 on ingredient lookups
  - [ ] Wraps all decrements in a single `async with session.begin():` block
  - [ ] Writes one `pantry_ingredient_event` row per actual decrement (not per attempted decrement)

- [ ] Task 4: Register subscriber (AC: #3)
  - [ ] Add `register("MealEventCompleted", handle_meal_event_completed)` to `register_subscribers()`

- [ ] Task 5: Tests (AC: #9, #10, #11)
  - [ ] `services/api/test/subscribers/test_pantry_meal_subscriber.py` — covers all AC #9 scenarios
  - [ ] `services/api/test/v1/meal_event/test_update_meal_event_pantry_hook.py` — integration test for AC #10
  - [ ] Re-run (or include) the integration test from pantry-3 to confirm both subscribers coexist (AC #11). Can be a single combined test file if desired.

## Dev Notes

- **This is the hardest story in the epic.** Do not try to make it perfect. Ship best-effort decrement with strict unit matching. If Leo finds under-decrement causes real UX pain, a future epic can add a real unit converter or a user-facing "confirm what you used" prompt.
- **Unit converter is out of scope.** Do not call external unit libraries, do not write a conversion map. Strict string equality on `unit_normalized`. The `quantity_normalized`/`unit_normalized` columns exist *aspirationally* in the schema — they are populated during import, but their normalization quality is inconsistent. That's a known debt.
- **Do not block the PUT response.** The subscriber fires after commit; even if it throws, the user gets a 200. This is critical — the user's "mark as cooked" gesture must feel instant and reliable.
- **Audit table justification.** The `pantry_ingredient_events` table is cheap insurance. When Leo says "my pantry looks wrong," a single SELECT answers "what did the system do to it and when." Future UI can surface this too. Scope-wise, the table is additive and costs ~1 hour of work.
- **Servings semantics**: `meal_event.servings` is the portion size the user actually cooked (e.g., "cooked for 2 people, recipe is for 4"). `recipe.servings` is the recipe's base serving count. The scale ratio is `meal_event.servings / recipe.servings`. If either is `None` or `0`, the safe behavior is to skip decrement (not assume 1.0) — a WARNING log tells us to fix the data upstream.
  - **Exception**: if `meal_event.servings` is `None`, treating it as `recipe.servings` (= 1.0× scale) is acceptable per AC #3. The null `meal_event.servings` usually means "user didn't specify, I cooked the full recipe." Null `recipe.servings` is different — the recipe itself is malformed data and we can't scale.
- **Do not dispatch on status changes to `"skipped"`.** Only `"completed"` triggers decrement. Skipped meals don't consume pantry.
- **Flag for future work**: if re-completing a meal becomes a user flow (plan → skipped → re-planned → completed), this hook will double-decrement. Consider a `pantry_decremented_at` flag on `meal_event` in a future story.
- **Do not add Celery / async workers.** The decrement is fast (a few row updates). Inline post-commit is fine for MVP.

### Project Structure Notes

- `libraries/utils/utils/models/pantry_ingredient_event.py` — new audit model
- `services/api/src/api/subscribers/pantry_meal_subscriber.py` — new subscriber co-located with pantry-3's
- Migration under `services/migrator/migrations/versions/`

### References

- `services/api/src/api/v1/meal_event/update_meal_event.py` (line 18) — hook attach point
- `libraries/utils/utils/models/meal_event.py` (line 22) — MealEvent model with `status`, `servings`, `recipe_id`
- `libraries/utils/utils/models/recipe.py` — Recipe with `servings` and `recipe_ingredients` relationship (confirm exact path at implementation time; likely `libraries/utils/utils/models/recipe.py`)
- `libraries/utils/utils/models/pantry_ingredient.py` — rows being decremented
- `libraries/utils/utils/events/` — dispatcher from pantry-3
- [Story: pantry-3-shopping-list-hook.md] — dispatcher dependency, subscriber pattern reference
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `pytest services/api` — 1403/1403 pass (6 subscriber + 5 dispatch tests added)
- `pytest libraries/utils` — 57/57 pass
- `npx nx run-many -t lint --projects api,utils,migrator` — clean

### Completion Notes

- Additive migration `f1p2t3r4y5e6 ← e1p2t3r4y5a6` creates
  `pantry_ingredient_events` (pantry_id, ingredient_id, event_type,
  delta_quantity, source_meal_event_id, timestamps). Indexed on pantry_id.
- New model `utils/models/pantry_ingredient_event.py`.
- New helper `utils/services/pantry_service.decrement_pantry_from_recipe`
  encapsulates the decrement math + audit write. Strict string equality on
  `unit_normalized`; mismatches are **silently skipped** and logged at
  WARNING (per user instructions and the epic's best-effort principle — no
  user prompts, never block the caller).
- Clamp-to-zero auto-archives the pantry row. The audit delta records the
  actual amount consumed, not the attempted consumption.
- `update_meal_event.py` captures `previous_status` and dispatches
  `MealEventCompleted` only on a `!= "completed" → "completed"` transition.
  Re-submitting `completed → completed` is a no-op. A crash in the dispatch
  is swallowed so the PUT still returns 200.
- Subscriber `pantry_meal_subscriber.py` opens its OWN `Database()` session
  (the request's session is not guaranteed open post-commit) and rolls back
  cleanly if anything throws.
- **Known limitation**: `MealEvent` has no `servings` column today, so the
  hook always uses a 1.0× scale (consumes the recipe's full yield). The
  subscriber already supports `event.servings / recipe.servings` — when a
  `servings` column is later added to `MealEvent`, populating the dispatch
  payload is a one-line change.
- **Known limitation**: re-cooking a meal (planned → completed → planned →
  completed) would double-decrement. Out of scope for MVP; flagged in the
  story's Dev Notes. A `pantry_decremented_at` flag on `meal_event` is a
  future improvement.

### QA Walkthrough

- [ ] Plan a recipe-linked meal. Verify pantry has a row for one of the
      recipe ingredients with a matching `unit_normalized`.
- [ ] PUT `/v1/meal-events/{id}` with `status: "completed"` → request returns
      200; the matching pantry row's `quantity_normalized` is reduced; a
      row appears in `pantry_ingredient_events` with `event_type="decrement"`
      and a negative `delta_quantity`.
- [ ] Re-PUT `status: "completed"` → no additional decrement, no new audit row.
- [ ] Mark another meal completed where a recipe ingredient uses a different
      `unit_normalized` than the pantry → no change, no audit row, server
      log contains `pantry_decrement_skip_unit_mismatch` at WARNING.
- [ ] Complete a meal whose recipe requires more than is currently in the
      pantry (e.g., recipe=100g, pantry=10g) → pantry clamps to 0, row is
      archived, audit `delta_quantity = -10g`.
- [ ] Complete a meal whose `recipe_id` is null → no dispatch, no decrement.
- [ ] Complete a meal with `status: "skipped"` → no dispatch, pantry unchanged.

### File List

**Created**
- `services/migrator/migrations/versions/20260416000001_create_pantry_ingredient_events.py`
- `libraries/utils/utils/models/pantry_ingredient_event.py`
- `services/api/src/api/subscribers/pantry_meal_subscriber.py`
- `services/api/tests/test_pantry_meal_subscriber.py`
- `services/api/tests/test_update_meal_event_pantry_hook.py`

**Modified**
- `libraries/utils/utils/services/pantry_service.py` — added
  `decrement_pantry_from_recipe` + `DecrementOutcome`
- `services/api/src/api/v1/meal_event/update_meal_event.py` — captures
  `previous_status`, dispatches `MealEventCompleted`
- `services/api/src/api/subscribers/__init__.py` — registers the meal
  subscriber
- `services/api/tests/conftest.py` — added `MockPantryIngredientEvent`
