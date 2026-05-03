# Story `ifh-2` — Backend: Decimal-typed response serialization sweep

**Status:** review
**Epic:** `epic-import-flow-hardening`

## Goal

Prevent recurrence of the cart-bug class (commit `a5c8438`, 2026-05-03) on the recipe surface. Pydantic v2's default JSON mode renders `Decimal` as a JSON string. Any Dart consumer that does the obvious `(json[key] as num?)?.toDouble()` cast crashes on a populated Decimal field — the exact symptom that killed `shopping.cart` `loadList` for every list with a non-null quantity.

The audit handoff specifically called out `services/api/src/api/v1/recipe/_response.py` and the `quantity_normalized` field as the most likely recurrence surface.

## Sweep results

Every Decimal-typed field on every Recipe-domain response schema was inspected. Outcomes:

| Schema | Field | Type | Decision |
|---|---|---|---|
| `GetRecipe.IngredientResponse` | `quantity_normalized` | `Decimal \| None` | **FIXED** — `@field_serializer` Decimal → float |
| `GetPublicRecipe.IngredientResponse` | `quantity_normalized` | `Decimal \| None` | **FIXED** — same |
| `CreateRecipe.IngredientResponse` | `quantity_display` | `Decimal` | Out of scope — see notes |
| `UpdateRecipe.IngredientResponse` | `quantity_display` | `Decimal` | Out of scope — see notes |
| `RestoreRecipeVersion.IngredientResponse` | `quantity_display` | `str` | No-op (already a str on the wire) |
| `GetRecipe.IngredientResponse` | `quantity_display` | `str` | No-op |
| `GetPublicRecipe.IngredientResponse` | `quantity_display` | `str` | No-op |

### Why `create_recipe` / `update_recipe` `quantity_display: Decimal` is out of scope

Dart consumers of `createRecipe()` / `updateRecipe()` go through `_asMap(response.data)` → `Map<String, dynamic>` with no strict cast on `quantity_display`. The current behavior — Pydantic emits the Decimal as a JSON string — has been working for the entire history of these endpoints. Adding a `field_serializer` that coerces to `float` would silently change the wire format from `"1.5"` to `1.5`. Even though the Dart Map<String, dynamic> consumer wouldn't crash, downstream display logic that expects a String (e.g., direct concatenation, regex parsing) might. **No motivating bug, no concrete gain, real surprise risk → leave alone.**

This means the `create_recipe` / `update_recipe` responses retain their current wire shape, where `quantity_display` arrives as a JSON string. If a future bug surfaces (a Dart consumer doing `as num?` on it), the fix is the same one-line `field_serializer` we apply here.

### What about the rest of the codebase?

- Pantry/cooking_log/meal_event/shopping_list also use Decimal in response schemas. Pantry uses a forgiving `_asDouble` parser (handles num OR String). Shopping list was the original bug surface and is already fixed (a5c8438). Cooking_log and meal_event response Decimal fields haven't surfaced as bugs in error_logs and the sweep is bounded to recipe per the epic AC. Flagged for follow-up if/when error_logs surfaces a hit.

## What changed

### `services/api/src/api/v1/recipe/get_recipe.py`
- Added `field_serializer` import.
- `IngredientResponse.quantity_normalized` carries a `@field_serializer("quantity_normalized")` that coerces `Decimal | None → float | None`.

### `services/api/src/api/v1/recipe/get_public_recipe.py`
- Same change applied to the sibling response.

### `services/api/tests/test_schemas.py`
- New `TestRecipeIngredientDecimalSerialization` (4 tests): populated + null cases on both `GetRecipe.IngredientResponse` and `GetPublicRecipe.IngredientResponse`. Asserts `model_dump_json()` produces a JSON number (not a string) for populated values, and `null` for null values.

## Acceptance criteria status

- [x] `GetRecipe.IngredientResponse.quantity_normalized` carries `@field_serializer` coercing `Decimal | None` → `float | None`.
- [x] Sibling `GetPublicRecipe` response gets the same fix.
- [x] Sweep documented (this file + commit message): every Decimal-typed Recipe response field inspected, fixed/no-op/out-of-scope decision recorded.
- [x] `model_dump_json()` produces a JSON number for populated cases, `null` for null cases. Pinned by 4 tests.
- [x] `npx nx run api:test` green (2570 passing, 100% coverage).
- [x] `npx nx run api:lint` green.

## Notes

- The `@field_serializer` runs before JSON encoding, so the wire payload is `{"quantity_normalized": 1.5}` not `{"quantity_normalized": "1.5"}`. Verified by `model_dump_json()` + `json.loads` round-trip in the new tests.
- The Dart `_asDouble` parser in `app/lib/features/pantry/models/pantry_ingredient.dart` handles num OR String, so existing pantry consumers keep working in both directions. The fix protects future consumers that might do a strict `as num?` cast.
- `quantity_display: str` everywhere it's a string — no change needed. The audit handoff mentioned `quantity_display` as a candidate but only the `create_recipe` / `update_recipe` variants are typed `Decimal`, which is out of scope per the table above.
