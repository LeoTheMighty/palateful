# QA walkthrough — Story `ifh-2`

> Decimal-typed response serialization sweep on recipe endpoints. Wire change: `GetRecipe.quantity_normalized` and `GetPublicRecipe.quantity_normalized` now serialize as JSON numbers (e.g. `1.5`) instead of strings (`"1.5"`).

## Pre-flight

```bash
cd /path/to/palateful
git pull origin main
npx nx run api:test          # expect 2570 passing, 100% coverage
npx nx run api:lint          # All checks passed!
```

## Manual checks (server contract)

### 1. Wire payload is a JSON number on populated `quantity_normalized`

```bash
TOKEN=...
RECIPE_ID=<recipe-with-non-null-quantity_normalized>
# Find one if needed:
#   psql -c "SELECT recipe_id FROM recipe_ingredients WHERE quantity_normalized IS NOT NULL LIMIT 1;"

curl -s "http://localhost:8080/v1/recipes/$RECIPE_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '.ingredients[0]'
```

Expected: `quantity_normalized` is a JSON **number** (no quotes), not a JSON string.

```jsonc
{
  "id": "...",
  "ingredient": {...},
  "quantity_display": "1 1/2",
  "unit_display": "cups",
  "quantity_normalized": 1.5,        // number, not "1.5"
  "unit_normalized": "cup",
  ...
}
```

### 2. Wire payload is `null` on missing `quantity_normalized`

Find a recipe ingredient with no normalized quantity (e.g., "salt to taste"):

```bash
curl -s "http://localhost:8080/v1/recipes/$RECIPE_WITH_NULL_QTY" \
  -H "Authorization: Bearer $TOKEN" | jq '.ingredients[] | select(.quantity_normalized == null)'
```

Expected: `"quantity_normalized": null` (no string fallback).

### 3. Public-recipe endpoint mirrors the fix

```bash
SHARE_TOKEN=<some-public-recipe-share-token>
curl -s "http://localhost:8080/v1/public/recipes/$SHARE_TOKEN" | jq '.ingredients[0].quantity_normalized'
```

Expected: number or null, never a string.

### 4. Recipe detail screen renders without throwing

In the Flutter app:
- Open a recipe whose ingredients have non-null `quantity_normalized` (e.g., a recipe imported via the URL or PDF flows where the parser produced a normalized quantity).
- Confirm the recipe-detail screen renders all ingredients without an error banner or crash.
- Pull-to-refresh — confirm no `_TypeError` shows up in `flutter logs` or via Sentry.

## Regressions to watch

- **Pantry list still loads.** Pantry's `_asDouble(json['quantity_normalized'])` handles both num AND String; this change keeps it on the num path. Confirm by opening the Pantry tab and verifying ingredient quantities render.
- **Existing get-recipe tests still pass.** The wire shape change is intentional but other endpoint-level tests assert `quantity_normalized` content; verify no test that hits get_recipe expects a string. (`npx nx run api:test` passed → all such expectations are satisfied.)
- **`create_recipe` / `update_recipe` responses are unchanged.** Those endpoints' `quantity_display: Decimal` field is intentionally NOT touched (out of scope per the story file). If a future Dart consumer breaks on those, the fix is the same one-line `field_serializer` we apply here.
- **`quantity_display: str` is unchanged on get_recipe / get_public_recipe / restore_recipe_version.** These were already strings; no risk.

## Post-merge follow-ups

- If `error_logs` ever surfaces a `_TypeError` from a recipe-related Dart screen on a Decimal cast, the fix template is the `@field_serializer` shown in this story.
- A separate epic could sweep cooking_log / meal_event / pantry response Decimal fields preemptively. Not required today — none have surfaced as bugs.
