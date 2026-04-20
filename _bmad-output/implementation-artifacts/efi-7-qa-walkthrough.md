# efi-7 — QA walkthrough

Recipe Edit wiring. Badge renders on 4 inferable fields; edits shrink
the set locally; save sends the shrunken set to the backend via
UpdateRecipe.

## Local checks

```bash
cd app
dart analyze lib/features/recipes/edit_recipe_screen.dart
flutter test test/core/constants/inferable_fields_test.dart \
             test/features/recipes/widgets/inferred_field_badge_test.dart
```

Expected: analyze shows only the 2 pre-existing warnings
(`error_banner` import + `_errorDetail` field); all tests green.

## Manual device sanity

Requires a recipe that has `inferred_fields` populated (import a cookbook
photo through Review Import with `EXTRACTOR_INFER_MISSING_FIELDS=true`
and approve it).

1. Open the recipe → tap Edit.
2. Verify: sparkle appears next to whichever inferable fields the
   extractor flagged (Description, Prep time, Cook time, Servings).
3. Edit one field (e.g., Cook time).
4. Verify:
   * Sparkle disappears immediately.
   * NO network call fires (unlike Review Import — there's no correction
     endpoint here).
5. Tap Save (or wait 2s for auto-save).
6. Inspect the `PUT /v1/recipes/{id}` payload:
   * `inferred_fields` key is present.
   * The edited field's name is NOT in the list; everything else still is.
7. Reload the edit screen. Verify:
   * The edited field's sparkle is gone (persisted).
   * The other inferable fields still show sparkles.

## Server invariant check

Try to forge an expansion (artificial — no UI path to do this):

```bash
curl -sX PUT ":API/v1/recipes/$RECIPE_ID" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"inferred_fields": ["cook_time_minutes", "servings", "nonsense"]}' \
     | jq .
```

Expected: HTTP 400, `error_message: "inferred_fields can only be reduced,
not expanded"`, `data.allowed` contains the current stored set only.
