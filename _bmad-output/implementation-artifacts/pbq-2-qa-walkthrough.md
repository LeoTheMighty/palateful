# QA walkthrough — pbq-2 `list_meals` hoist `_readable_book_ids`

## What shipped

`GET /v1/meals` — including `?scope=home` — now fires exactly one
`recipe_book_users` SELECT per request regardless of page size. The
per-meal lookup inside `MealService.hydrate_components` becomes opt-in
via a new `readable_book_ids` kwarg; `list_meals` pre-computes the
set and reuses it both for the main `Meal.recipe_book_id.in_(...)`
filter and for threading into `build_meal_summary`.

## Before/after numbers

### Query count (hard AC)

| Page size | Pre-pbq-2 `recipe_book_users` queries | Post-pbq-2 |
| --- | --- | --- |
| 30-meal home grid | **31** (1 subquery + 30 per-meal self-fetches) | **1** |
| 20-meal list | 21 | 1 |
| 0 meals | 1 | 1 |

Verified at mock layer via
`test_list_meals_hoists_readable_book_ids_to_single_query` —
`qc.query_count_for(RecipeBookUser) == 1` asserted.

### Latency (single-operator prod)

Baseline via `analyze_latency.py` on the day of deploy:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep list_meals
```

Method: pin the baseline row before merging, redeploy, rerun ~30min
post-deploy. Expected directional shape: p95 on `list_meals` drops
proportional to `recipe_book_users` query latency × page size. On
single-operator prod (~1 Meal, typically 0 components) this shows as
a modest p95 drop; at dogfood scale (20+ meals, 2-6 components each)
the drop is material enough to remove `list_meals` from
`--regression-hunt` output.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_list_meals_filters.py --no-cov
# 9 passed, including test_list_meals_hoists_readable_book_ids_to_single_query

npx nx run api:test -- tests/test_meal_service.py --no-cov
# All 20 existing hydrate_components tests still pass — 5 call sites
# unchanged (no kwarg = None = self-fetch = original behavior)
```

### 2. Query-count test locks in the fix

`test_list_meals_hoists_readable_book_ids_to_single_query`:

- Seeds 30 mock meals + 2 components each.
- Wraps `client.get("/v1/meals?scope=home")` in `count_queries`.
- Asserts `qc.query_count_for(RecipeBookUser) == 1` — exactly one.
- Any future regression that reintroduces a per-meal lookup (e.g. a
  new caller that forgets to thread the kwarg) trips the test.

### 3. Hit the endpoint manually

```bash
curl -H "Authorization: Bearer <token>" \
     "https://api.palateful.app/v1/meals?scope=home"
```

Response shape byte-compatible: same `items[]` entries with
`component_count`, `component_image_urls`, `component_recipe_ids`,
`archived_at`, `updated_at`, and the `MealSummaryResponse.is_available`
per-component fields as before.

### 4. Single-meal endpoints unchanged

```bash
curl -X POST -H "Authorization: Bearer <token>" \
     -d '{"name": "Pho Night", "description": null, "recipe_book_id": "...",  "recipe_ids": ["a", "b"]}' \
     https://api.palateful.app/v1/meals
# create_meal → build_meal_response(meal, db=db, user_id=user.id)
# No readable_book_ids kwarg → None → self-fetch → works as before.
```

Same for `get_meal`, `update_meal`, `add_recipe_to_meal`,
`remove_recipe_from_meal`, `reorder_meal_components`.

## Checklist

- [x] `hydrate_components` gains `readable_book_ids: set | None = None`
      kwarg with None-fallback to `_readable_book_ids`.
- [x] `build_meal_response` and `build_meal_summary` accept + thread
      the kwarg.
- [x] `list_meals` computes the set once and reuses it for the main
      filter + hydration threading.
- [x] Integration test asserts `qc.query_count_for(RecipeBookUser)
      == 1` on a 30-meal page.
- [x] 5 test callers of `hydrate_components` unchanged (verified;
      suite still green).
- [x] Non-list callers (`create`/`update`/`get` meal) unchanged —
      regression covered by the still-green `test_meal_service.py`
      suite.
- [x] Response shape byte-identical.

## Rollback

```bash
git revert <pbq-2-commit>
```

Single commit. Removes the kwarg (None default keeps existing
callers compiling), restores the subquery pattern for the Meal
filter, and restores the per-meal self-fetch inside
`hydrate_components`.
