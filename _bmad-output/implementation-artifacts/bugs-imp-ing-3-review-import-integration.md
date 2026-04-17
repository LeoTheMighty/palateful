# Story bugs-imp-ing-3: Integrate StructuredIngredientRow into Import Review

Status: done

## Story

As a user reviewing an imported recipe,
I want each parsed ingredient shown with its quantity, unit, name, and notes
broken out and editable,
so that the post-`4f0de4c` extractor's structured output is finally visible
to me.

## Context

The extractor already emits `{text, quantity, unit, name, notes, is_optional}`
per ingredient. The Review Import screen silently strips everything but
`text`. `create_recipe_task._create_recipe_ingredient` already consumes
`name`/`quantity`/`unit`/`notes`/`is_optional` via find-or-create, so the
backend is ready — this is purely a frontend binding upgrade.

## Acceptance Criteria

1. `import_item_review_screen.dart` uses `StructuredIngredientRow`s backed
   by a `List<IngredientRowData>`.
2. `_populateControllers` reads `{text, quantity, unit, name, notes, is_optional}`
   into per-row `IngredientRowData`. When both `name` and `text` exist,
   `name` wins (mirrors `create_recipe_task` precedence). When only `text`
   exists, it populates the name field.
3. `_buildUserEdits` writes `ingredients` as `{name, quantity, unit, notes,
   is_optional}` per row. Empty fields serialize as `null`, not `""`.
4. `+ Add ingredient` button appends a new empty row with stable key.
5. Delete uses snackbar-undo (3s) — row restored at original index.
6. Focus-group smoke test: populate fixture with a structured ingredient
   (quantity=0.333, unit="cup", name="butter", notes="melted"); verify the
   row renders with all fields filled, and `_buildUserEdits()` round-trips.

## Key Files

- Modify: `app/lib/features/recipes/add_recipe/import_item_review_screen.dart`
- Test: `app/test/features/recipes/add_recipe/import_item_review_screen_test.dart`
