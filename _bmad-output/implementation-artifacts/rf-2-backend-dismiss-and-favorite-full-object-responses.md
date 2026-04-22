# Story rf-2 — Backend response-shape fixes for dismiss + favorite

**Epic**: epic-reactive-foundation-home-imports
**Status**: review
**Created**: 2026-04-22

## Scope

Unblock client-side cache-patching on three endpoints by expanding their
response payloads. All changes are **additive** — old clients reading only
the legacy fields keep working.

## Acceptance criteria (from epic)

1. `POST /v1/import-items/{id}/dismiss` keeps the existing top-level fields
   (`item_id`, `dismissed_at`, `job_dismissed`) AND adds an optional
   `item: ImportItemSummary | None` carrying the full updated row. ✅
2. `POST /v1/recipes/{id}/favorite` returns the full `GetRecipe.Response`
   with `is_favorite` nested inside. Full recipe payload (ingredients,
   steps, tags, notes) — same shape as `GET /v1/recipes/{id}`. ✅
3. `POST /v1/meals/{id}/favorite` returns the full `MealResponse`
   (hydrated components, `is_favorite` nested inside). ✅
4. Three new Python router tests assert the response shape:
   - `test_rf2_response_shapes.py::TestDismissResponseShape` (2 tests —
     legacy fields + new `item` object). ✅
   - `test_rf2_response_shapes.py::TestFavoriteRecipeResponseShape`
     (2 tests — add + remove paths). ✅
   - `test_rf2_response_shapes.py::TestFavoriteMealResponseShape`
     (2 tests — favorite + unfavorite paths). ✅
5. Flutter parsing test (`rf2_response_parsing_test.dart`) verifies
   golden JSON fixtures for each endpoint. Covers pre-rf-2 server
   fallback (missing `item`) without crash. ✅
6. Deploy order: backend merges + deploys first; app binary ships any
   time after. Client fallback: when `item: null`, read the legacy
   fields and invalidate-and-refetch — no crash. ✅

## Files added / modified

- `services/api/src/api/v1/recipe/_response.py` — **new** shared
  `build_recipe_response` helper (extracted from `get_recipe.py`). Reused
  by `toggle_favorite.py`; future recipe-mutation endpoints plug into
  the same shape. Accepts optional `is_favorite` to skip re-querying
  when the caller already knows the post-mutation state.
- `services/api/src/api/v1/recipe/get_recipe.py` — refactored to
  delegate to `build_recipe_response`. No behavior change.
- `services/api/src/api/v1/recipe/toggle_favorite.py` — returns full
  recipe response; `Response` aliases `GetRecipe.Response`.
- `services/api/src/api/v1/meal/_response.py` — `build_meal_response`
  gains optional `is_favorite` override (same rationale as recipe).
- `services/api/src/api/v1/meal/favorite_meal.py` — returns
  `MealResponse` via `build_meal_response`; passes explicit
  `is_favorite` state.
- `services/api/src/api/v1/import_job/dismiss_import_item.py` — adds
  optional `item: ImportItemSummary` field; legacy fields untouched.
- `services/api/tests/test_rf2_response_shapes.py` — **new**.
- `services/api/tests/test_meal_components.py` — +1 `MockQuery([])` per
  favorite test to match the new `_readable_book_ids` call inside
  `build_meal_response`. Not a semantic change; just a mock-sequence
  update.
- `app/test/core/services/rf2_response_parsing_test.dart` — **new**.

## QA walkthrough

- [ ] `npx nx run api:test -- tests/test_rf2_response_shapes.py --no-cov`
      — 6 pass.
- [ ] `npx nx run api:test -- tests/test_recipe.py::TestToggleFavorite
      tests/test_import.py::TestDismissImportItem
      tests/test_meal_components.py::TestFavoriteEndpoints --no-cov` —
      all pass (no regressions on pre-rf-2 tests after mock-sequence
      update).
- [ ] `npx nx run api:lint` — clean.
- [ ] `flutter test test/core/services/rf2_response_parsing_test.dart`
      — 6 pass.
- [ ] Full API suite failure count unchanged from baseline (29 pre-
      existing unrelated failures).

## Deploy order (Infra)

Backend deploys first. The three endpoints become additive:

- Old client + new backend: ignores `item`/full-recipe/full-meal fields,
  keeps reading `is_favorite` / `item_id` / `dismissed_at` / `job_dismissed`.
  Works.
- New client + old backend: `item` missing → falls back to
  invalidate-and-refetch. One extra round-trip per dismiss, no crash.
  Works but degraded.
- New client + new backend: patches cached state from `item` /
  full-recipe / full-meal. Works optimally.

No migrations. No new env vars. No Terraform. Standard deploy.

## Payload size note

Favorite toggle jumps from ~100 bytes → 3–12 KB for recipes, similar
for meals (component count dependent). Acceptable given the low
frequency of the endpoint. Flagged in epic Risks; fallback is a
`?slim=true` query param in a follow-up if dogfood reports slowness
on cellular.
