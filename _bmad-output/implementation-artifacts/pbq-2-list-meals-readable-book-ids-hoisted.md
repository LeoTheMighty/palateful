# Story pbq-2 — `list_meals` hoist `_readable_book_ids`

**Status:** done
**Epic:** epic-perf-backend-query-tuning (highest leverage)
**Depends on:** pbq-0 (query-count test helper).

## Scope

Stop `MealService.hydrate_components` from re-fetching the user's
readable-book set per meal. For the 30-meal home grid, the old code
fired 30 identical `SELECT ... FROM recipe_book_users WHERE user_id=...`
queries. Post-fix, `list_meals` computes the set once, reuses it to
scope the main Meal filter, and threads it through `build_meal_summary`
→ `hydrate_components` via a new optional kwarg.

## Implementation notes

- **Kwarg threading.** `hydrate_components(meal, *, user_id,
  readable_book_ids: set | None = None)` — when `None`, falls back to
  `self._readable_book_ids(user_id)` (original single-meal path).
  Both `_response.build_meal_response` and
  `_response.build_meal_summary` gained the same optional kwarg and
  pass it through verbatim.
- **Double-win refactor.** The pre-existing `readable_books` subquery
  in `list_meals` was a *second* hit on `recipe_book_users` (subquery
  for the main filter). Reusing the same hoisted set for both the
  `Meal.recipe_book_id.in_(...)` filter and the hydration lookup
  collapses two queries on the same table into one — so the
  `qc.query_count_for(RecipeBookUser) == 1` assertion is literally
  tight, not "at most 2".
- **No regression on single-meal callers.** `create_meal`,
  `update_meal`, `get_meal`, `add_recipe_to_meal`,
  `remove_recipe_from_meal`, `reorder_meal_components` all call
  `build_meal_response(meal, db=db, user_id=user.id)` without the
  new kwarg → `None` default → self-fetch → one `recipe_book_users`
  SELECT per call, same as before. Unchanged by design.
- **Scope boundary.** Other list callers that loop over meals
  (`list_meals_in_book`, `list_meals_using_recipe`, `list_favorites`)
  have the same underlying N+1 shape but are out of scope per the
  epic's File Structure — left as follow-ups if `analyze_latency.py`
  flags them after pbq-2 deploys. Strict scope discipline keeps the
  revert surface small.

## File list

- `libraries/utils/utils/services/meal_service.py` [MODIFY] — add
  `readable_book_ids: set | None = None` kwarg to
  `hydrate_components` with None-fallback to `_readable_book_ids`.
- `services/api/src/api/v1/meal/_response.py` [MODIFY] — both
  `build_meal_response` and `build_meal_summary` accept + thread
  the kwarg.
- `services/api/src/api/v1/meal/list_meals.py` [MODIFY] — compute
  `readable_book_ids` once, reuse it for the main filter and
  thread it through `build_meal_summary`.
- `services/api/tests/test_list_meals_filters.py` [MODIFY] — adds
  `test_list_meals_hoists_readable_book_ids_to_single_query`.

## Acceptance criteria — coverage

- AC1 — `hydrate_components(meal, *, user_id, readable_book_ids:
  set | None = None)` — skips per-meal fetch when passed. ✅
- AC2 — `_response.py` both `build_meal_response` and
  `build_meal_summary` accept + thread the kwarg. ✅
- AC3 — `list_meals.py` computes once and passes. ✅
- AC4 — 5 test-callers in `test_meal_service.py` unchanged (verified
  — all use `hydrate_components(meal, user_id="user-1")` with no
  kwarg, `None` default). ✅
- AC5 — Integration test: 30-meal page triggers **1**
  `_readable_book_ids`-shaped query, not 30, asserted via
  `count_queries` + `query_count_for(RecipeBookUser) == 1`. ✅
- AC6 — Non-list callers (`create`/`update`/`get` meal) unchanged —
  regression via the still-green `test_meal_service.py` suite. ✅
- AC7 — p50/p95 before/after for `GET /v1/meals?scope=home` pasted
  into QA walkthrough. ✅

## QA walkthrough

See `pbq-2-qa-walkthrough.md`.

## Rollback

Single commit; revert with `git revert <pbq-2-commit>` — drops the
optional kwarg (None default handles existing single-meal callers)
and restores the original subquery + per-meal self-fetch.
