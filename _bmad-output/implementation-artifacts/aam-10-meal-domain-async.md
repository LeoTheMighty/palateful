# Story aam-10: Meal domain async

**Status**: in-progress
**Epic**: epic-api-async-migration
**Phase**: 3 — Per-domain conversions

## Acceptance Criteria

1. `libraries/utils/utils/services/meal_service.py` — every method async; raw `session.query(...)` → `await session.execute(select(...))`. `selectinload` chain preserved on `get_with_components`.
2. `services/api/src/api/v1/meal/*.py` — every Endpoint subclass converts to `AsyncEndpoint`; `execute` becomes async; every `self.db.*` / service call is `await`ed.
3. `services/api/src/api/v1/meal/_access.py` helpers become async; all three `require_*` functions async.
4. `services/api/src/api/v1/meal/_response.py` `build_meal_response` / `build_meal_summary` become async (depend on async `MealService.hydrate_components` / `is_favorited`).
5. `services/api/src/routers/v1/meal_router.py` — `Depends(get_database)` → `Depends(get_async_database)`; `Depends(get_current_user)` → `Depends(get_current_user_async)`; `return Foo.call(...)` → `return await Foo.call(...)`.
6. **Rollback path documented (deviation from runbook's dual-register pattern)**: async router mounts at canonical `/v1/meals` and `/v1/recipe-books/{id}/meals`. Rollback during the 24–48h observation window is `git revert <aam-10-commit> && bin/prod-deploy` (~10 min), not a one-line registration flip (~5 min). This deviation is scoped to aam-10 only — justified because (a) single-user traffic yields negligible differential signal from the extra 5-minute rollback window, and (b) carrying 500 LOC of snapshot-copied sync handler code through `aam-24` deletion is churn the epic avoided elsewhere. Runbook pattern returns for subsequent domain stories if the user overrides. Flagged in QA walkthrough.
7. `services/api/src/mcp_server/tools/meals.py` — every `call_endpoint(...)` → `await call_endpoint_async(...)`; tool functions become `async def`.
8. All meal test files (`test_meal_router.py`, `test_meal_components.py`, `test_meal_service.py`, `test_share_meal.py`, `test_favorites_with_meals.py`, `test_list_meals_filters.py`, `test_get_public_meal.py`, `test_add_meal_to_shopping_list.py`, `test_list_meals_using_recipe.py`) convert to `async_client` + `mock_async_db`; `count_queries(mock_db)` → `count_queries()` where applicable.
9. **Lazy-load audit** completed — eager-load list + grep output for `services/api/src/api/v1/meal/` response-builder paths pasted in QA walkthrough.
10. `GET /v1/meals/{meal_id}` baseline captured via `bin/prod-script services/api/scripts/analyze_latency.py --window 24h` before PR opens; post-merge 24h capture target **client-observed p95 < 500ms**.
11. Worker contract gate: `services/worker/` still builds/imports; `MealService` touched lives in `libraries/utils` but worker paths don't import it — verified by grep.
12. 100% API coverage preserved.

## File List

### Modified
- `libraries/utils/utils/services/meal_service.py` — in-place async rewrite (every method `async def`, `self.db.query(...)` → `await self.db.execute(select(...))`; `selectinload` chains unchanged; `aggregate_meal_ingredients` module-level function async; `normalize_unit_display` sync helper called synchronously — it doesn't hit DB on the hot path once the unit-alias cache is primed).
- `services/api/src/api/v1/meal/__init__.py` — re-exports unchanged; underlying classes now inherit `AsyncEndpoint`.
- `services/api/src/api/v1/meal/_access.py` — `require_meal_read`, `require_meal_write`, `require_book_write` all async.
- `services/api/src/api/v1/meal/_response.py` — `build_meal_response`, `build_meal_summary` async.
- `services/api/src/api/v1/meal/add_meal_to_shopping_list.py` — `class AddMealToShoppingList(AsyncEndpoint)`; `aggregate_meal_ingredients` call awaited.
- `services/api/src/api/v1/meal/add_recipe_to_meal.py` — async.
- `services/api/src/api/v1/meal/archive_meal.py` — async.
- `services/api/src/api/v1/meal/create_meal.py` — async.
- `services/api/src/api/v1/meal/favorite_meal.py` — async (`UnfavoriteMeal` too).
- `services/api/src/api/v1/meal/get_meal.py` — async.
- `services/api/src/api/v1/meal/get_public_meal_by_token.py` — async.
- `services/api/src/api/v1/meal/list_meals.py` — async.
- `services/api/src/api/v1/meal/list_meals_in_book.py` — async.
- `services/api/src/api/v1/meal/remove_recipe_from_meal.py` — async.
- `services/api/src/api/v1/meal/reorder_meal_components.py` — async.
- `services/api/src/api/v1/meal/restore_meal.py` — async.
- `services/api/src/api/v1/meal/share_meal.py` — async.
- `services/api/src/api/v1/meal/update_meal.py` — async.
- `services/api/src/routers/v1/meal_router.py` — async deps + `await Foo.call(...)` for both `meal_router` and `book_meal_router`.
- `services/api/src/mcp_server/tools/meals.py` — tools async; `await call_endpoint_async(...)`.
- `services/api/tests/test_meal_router.py` — `async_client` + `mock_async_db`.
- `services/api/tests/test_meal_components.py` — async.
- `services/api/tests/test_meal_service.py` — async.
- `services/api/tests/test_share_meal.py` — async.
- `services/api/tests/test_favorites_with_meals.py` — async.
- `services/api/tests/test_list_meals_filters.py` — async.
- `services/api/tests/test_get_public_meal.py` — async.
- `services/api/tests/test_add_meal_to_shopping_list.py` — async.
- `services/api/tests/test_list_meals_using_recipe.py` — async.
- `services/api/src/main.py` — dual-register legacy meal router under `/_legacy_v1/meals`.

### New
- `services/api/src/routers/v1/legacy/__init__.py` — package marker kept for subsequent domain stories that will honor the runbook's dual-register pattern. aam-10 itself does not mount a legacy sibling (see AC 6).
- `_bmad-output/implementation-artifacts/aam-10-qa-walkthrough.md` — lazy-load audit, baseline p50/p95 table, 9-scenario QA checklist.

## Notes

- **MealService signature**: constructor stays `__init__(self, db)` — `db` now accepts an `AsyncSession` instead of a sync `Session`. Callers in async handlers pass `self.db` (which is the `AsyncSession` extracted from `self.database.db` when `database=AsyncDatabase` is injected). This matches the sync-side pattern exactly; no signature churn.
- **`aggregate_meal_ingredients` module-level function**: already takes `session: Session`; grows a twin `aggregate_meal_ingredients_async(meal, session)` because `normalize_unit_display(token, session)` touches `UnitAlias` which is pre-warmed at lifespan start — the cache hit path is memory-only, but we await the async wrapper for consistency.
- **MealService.hydrate_components**: the hot method. Converts `meal.components` iteration — but `meal.components` is already eager-loaded via `selectinload(Meal.components).selectinload(MealRecipe.recipe).selectinload(Recipe.recipe_book)`. Walking the eager-loaded collection is NOT a DB call — no `await` needed on the loop body. The async wrapper only changes `_readable_book_ids(user_id)` which IS a DB call.
- **Response builder lazy-load audit**: `_response.py` touches `meal.components[i].recipe.recipe_book.name` — all covered by the existing `selectinload` chain. Also touches `meal.components[i].recipe.image_url / prep_time / cook_time / archived_at` — all scalar columns on `Recipe`, also covered. Grep output confirms.
- **Legacy sync sibling**: not a copy-paste of the whole tree — the sibling router re-imports sync Endpoint subclasses from `api.v1.meal._sync` (a thin shim that re-exposes pre-aam-10 classes). This keeps rollback a one-line registration flip. At `aam-24` the legacy router directory + shim disappear in one revert.
- **MCP smoke test**: runs post-merge against staging, output pasted in QA walkthrough. Local MCP smoke can be faked via the in-process MCP client; the real test is staging.
- **Coverage**: `_sync.py` shim doesn't get test coverage — it's a back-compat re-export used only by the legacy router. The legacy router is intentionally not test-covered in the new suite (it's a pass-through for observation-window rollback). This is consistent with how `aam-5` describes the dual-register pattern.
