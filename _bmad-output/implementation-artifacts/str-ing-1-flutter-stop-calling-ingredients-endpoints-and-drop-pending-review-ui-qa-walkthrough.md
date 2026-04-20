# str-ing-1 — QA walkthrough

Manual-smoke checklist for the reviewer. Expected runtime ~3 minutes.

## Pre-reqs
- Current git branch: `main` (str-ing-1 commit is latest HEAD prior to str-ing-2).
- App: `flutter run` in `app/`.

## Checks

### 1. Ingredient endpoints unreferenced
- `rg 'searchIngredients|createIngredient\b|getIngredient\b|pendingReviewIngredient|IngredientRowStateBadge|pending_review_ingredient' app/` → **must return zero matches**.
- `rg '/v1/ingredients' app/lib/` → **must return zero matches**.

### 2. Pantry add flow (visual)
- Open the app → Profile → Pantry → FAB (+).
- Expect: free-text "Ingredient" TextField with hint `e.g. olive oil`, auto-focused; `Save` button present from the start (greyed out).
- Type "olive oil" → keyboard action is `next`.
- Fill Quantity `2`, Unit `tbsp`, pick Storage `pantry`.
- Tap Save — note: backend will reject `{name: ...}` with 4xx until str-ing-2 lands. Expect `Save failed. Please try again.` copy. **This is expected** — the cross-story dependency is documented in the story file.

### 3. Pantry edit flow
- Open an existing pantry item.
- Expect: NO TextField for name; instead a `ListTile` shows the existing ingredient name + category. Quantity / Unit / Storage / Expires editable. `Save` enabled when quantity is valid. `Delete` icon in AppBar.
- Tap Save → should succeed (unchanged from prior behaviour).

### 4. Review Import screen
- Import any recipe (URL).
- Open the item in Review Import.
- Expect: NO sparkle badge (`Icons.auto_awesome`) anywhere in the ingredient rows. Row layout is `qty / unit / name / caret / delete`, end-to-end, no empty slot at 320pt width.
- Verify: tap the caret to reveal notes + optional — still works.

### 5. Recipe wizard ingredient rows
- Start a new recipe via Add Recipe → Paste Text.
- Expect: ingredient rows render without any badge. Name field is plain text, no autocomplete suggestion dropdown, no server roundtrip.

### 6. Widget test coverage
- `flutter test test/features/recipes/widgets/` → pass (48 tests).
- `flutter test test/features/recipes/add_recipe/` → pass (all ingredient-mapping tests green).
- `flutter test test/features/pantry/` → pass (3 editor tests green: free-text field, save-disabled gate, edit-mode title).

### 7. No leftover imports
- `dart analyze lib/features/pantry/ lib/features/recipes/widgets/ lib/features/recipes/add_recipe/ lib/core/services/api_client.dart` → no new warnings from this story's files.

## Sign-off

- [ ] All 7 checks pass.
- [ ] No unexpected regressions on the Review Import row layout (visual).
- [ ] Cross-story note on pantry save is acknowledged (expected to be broken until str-ing-2 lands).
