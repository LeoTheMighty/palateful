# Story str-ing-1 — Flutter: stop calling `/v1/ingredients/*` + drop pending-review UI

**Epic:** epic-ingredients-string-simplification
**Status:** done (2026-04-20)

## Summary

Unship every Flutter caller of `GET /v1/ingredients/search`, `POST /v1/ingredients`, and `GET /v1/ingredients/{id}` **before** str-ing-3 deletes the endpoints, so the rollout window has no 404-generating client path. Also retires the never-shipped `IngredientRowStateBadge` (96 LOC + 95 LOC test, in-tree ahead of plan via `riip-7`) and every downstream `pendingReviewIngredient` / `pending_review_ingredient` wiring.

## Changes

### Deleted
- `app/lib/features/recipes/widgets/ingredient_row_state_badge.dart` (96 LOC)
- `app/test/features/recipes/widgets/ingredient_row_state_badge_test.dart` (95 LOC)
- `app/lib/features/pantry/widgets/ingredient_search.dart` (120 LOC — `IngredientSearch` + `IngredientMatch` class)

### Modified
- `app/lib/core/services/api_client.dart` — deleted `searchIngredients`, `createIngredient`, `getIngredient` methods.
- `app/lib/features/recipes/widgets/structured_ingredient_row.dart` — removed `pendingReviewIngredient` parameter on `IngredientRowData` + `copyWith`; removed inline `IngredientRowStateBadge` render; dropped import.
- `app/lib/features/recipes/add_recipe/ingredient_edits_mapping.dart` — dropped `pending_review_ingredient` JSON decoder + downstream wiring.
- `app/lib/features/pantry/screens/pantry_editor_screen.dart` — replaced two-step (search → form) picker flow with a single-pane form. Add mode shows a plain `TextField` (`Key('pantry_editor_name')`, `Semantics(label: 'Ingredient name')`) backed by `_nameController`; save sends `{name: ...}` instead of `{ingredient_id: ...}`. (Backend side — accepting `name` in `PantryIngredientCreate` — lands in str-ing-2.)
- `app/test/features/pantry/pantry_editor_screen_test.dart` — rewrote add-mode tests against the free-text entry flow; kept edit-mode title/delete coverage.

## Cross-story dependency

Pantry editor now posts `{name: "..."}` to `POST /pantries/{id}/ingredients`. Backend still requires `ingredient_id` at this commit, so the pantry-add flow is broken between str-ing-1 and str-ing-2 commits (both land local-only — never pushed mid-epic). str-ing-2 adds `name` XOR `ingredient_id` to `PantryIngredientCreate` with inline-create of the ingredient row, closing the loop. Flagged for the reviewer.

## Acceptance criteria ✅

1. ✅ No Flutter code path calls `GET /v1/ingredients/search`, `POST /v1/ingredients`, or `GET /v1/ingredients/{id}`.
2. ✅ Pantry ingredient-search UI replaced with a free-text name field; add flow plumbs a plain string to the save payload.
3. ✅ No widget renders `IngredientRowStateBadge`; no Flutter model decodes `pending_review_ingredient`.
4. ✅ `dart analyze` on touched surface — only pre-existing warnings remain (none from this story).
5. ✅ `flutter test test/features/recipes/widgets/ test/features/recipes/add_recipe/ test/features/pantry/` → 123 passed.
6. ✅ `rg 'searchIngredients|createIngredient\b|getIngredient\b|pendingReviewIngredient|IngredientRowStateBadge|pending_review_ingredient' app/` → zero matches.

## QA walkthrough

See `str-ing-1-flutter-stop-calling-ingredients-endpoints-and-drop-pending-review-ui-qa-walkthrough.md`.
