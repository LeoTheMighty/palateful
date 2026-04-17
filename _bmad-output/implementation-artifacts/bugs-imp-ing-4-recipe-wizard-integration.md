# Story bugs-imp-ing-4: Integrate StructuredIngredientRow into wizard + edit

Status: done

## Story

As a user creating or editing a recipe outside the import flow,
I want the same structured ingredient editor I see in Review Import,
so that I have one consistent UX for ingredient editing across the app —
and the recipe edit screen finally lets me touch ingredients at all.

## Context

With Story 5 landing name-or-id input on the backend, both the recipe
wizard (for net-new recipes) and the recipe edit screen (which had no
ingredient editor at all) can finally consume the canonical structured
shape that the Review Import screen already uses.

## Acceptance Criteria — all green

1. Wizard's `_StepIngredients` rewritten: single-text-input + heuristic
   parser removed; list of `StructuredIngredientRow`s replaces it.
2. Wizard starts with one empty row pre-rendered (Sally — empty state);
   "+ Add ingredient" appends more.
3. Wizard state model migrated from
   `{quantity_display, unit_display, ingredient: {canonical_name}}` to
   canonical `List<IngredientRowData>`. `_saveRecipe` serializes
   `{name, quantity, unit, notes, is_optional}` per row via
   `ingredientRowToUserEditJson` (with `ingredientRowHasContent` guard).
4. Edit screen grows a brand-new **Ingredients** section. GET-recipe
   payloads hydrate via new `ingredientRowFromGetRecipe` helper;
   formatted `quantity_display` strings are parsed back with
   `fraction_parser.parseFraction`.
5. Edit-save preserves `ingredient_id` for existing rows
   (`ingredientRowToEditSavePayload`) and falls back to name-only for
   net-new rows — so `resolve_ingredient` only runs find-or-create when
   it should.
6. Snackbar-undo delete on both wizard and edit screens (inherited
   locked decision).
7. Legacy ingredients (no `quantity_display` / `unit_display` / `notes`)
   hydrate `canonical_name` into the Name field; other fields stay
   empty. Nothing is lost or corrupted.
8. Hydration + save-payload helpers (pure functions) covered by 6 new
   unit tests in `ingredient_edits_mapping_test.dart`.

## Key Files

- Modify: `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart`
- Modify: `app/lib/features/recipes/edit_recipe_screen.dart`
- Modify: `app/lib/features/recipes/add_recipe/ingredient_edits_mapping.dart`
  (new helpers `ingredientRowFromGetRecipe` + `ingredientRowToEditSavePayload`)
- Test: `app/test/features/recipes/add_recipe/ingredient_edits_mapping_test.dart`
