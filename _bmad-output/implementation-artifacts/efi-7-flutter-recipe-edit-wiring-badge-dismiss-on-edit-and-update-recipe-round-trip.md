# Story efi-7 — Recipe Edit badge wiring + UpdateRecipe shrunken round-trip

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-3 (UpdateRecipe accepts inferred_fields w/ shrink-only), efi-5 (badge + decoder + constant).

## Scope

Ports the Review Import badge UX to the Recipe Edit screen. Two key
differences from efi-6:

1. **No correction dispatch.** Design principle 9 defers the
   recipe-edit side channel — the `/v1/import-items/{id}/corrections`
   endpoint is import-item-scoped, and Recipe Edit has no equivalent
   recipe-scoped correction endpoint yet. Badge dismissal is local-only.
2. **UpdateRecipe carries the shrunken set.** On save, the payload adds
   `inferred_fields: _inferredFields.toList()`. The backend's shrink-only
   rule (efi-3) guarantees the stored list can only reduce — a buggy
   client trying to add fields gets a 400.

## Implementation notes

- `_decorateInferable(label, field, {suffixText})` mirrors the efi-6
  helper but preserves `suffixText` (e.g., 'min' on prep / cook) so the
  screen's styling stays consistent with the non-badged state. Recipe
  Edit's existing decorations don't use `OutlineInputBorder` (the
  ambient theme handles it); my helper matches that.
- `_dismissInferred(field)` is the setState-only removal — no timer, no
  dispatch. Called from each of the 4 inferable-field onChanged
  callbacks before the existing `_scheduleSave`.
- The save payload always includes `inferred_fields` (even when empty)
  so the server sees the user's shrunken state explicitly. The backend
  treats `[]` as "user has touched every inferred field" — a valid shrink
  to an empty set.

## Scope limits

Same 4-field limit as Review Import: `description`, `prep_time_minutes`,
`cook_time_minutes`, `servings`. Recipe Edit doesn't surface
cuisine / category / vibes today, so there's nowhere to badge them.
Adding those fields later is a one-line wiring job per field.

## File list

- `app/lib/features/recipes/edit_recipe_screen.dart` [MODIFY] — decoder, helpers, wiring on 4 TextFields, `inferred_fields` in UpdateRecipe payload.

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `_loadRecipe` decodes `data['inferred_fields']` via `decodeInferredFields`; stored in `_inferredFields`. |
| 2 | `_decorateInferable` renders the label + `InferredFieldBadge` in a `Row` when the field is in `_inferredFields`. Wired on all 4 inferable fields this screen edits. |
| 3 | Each field's `onChanged` calls `_dismissInferred(<field>)` before `_scheduleSave`. Removal is idempotent and setState-safe. |
| 4 | No dispatch wired. `_dismissInferred` does NOT call any API method. |
| 5 | `_saveNow` includes `'inferred_fields': _inferredFields.toList()` in the update payload. Matches the backend UpdateRecipe schema (efi-3). |
| 6 | Manual verification via the QA walkthrough — widget test deferred for the same getIt/ApiClient/GoRouter-DI reasons that made efi-6 integration testing impractical. The underlying decoder + badge widget are unit-tested in efi-5. |
| 7 | Badge carries `Semantics(label: "AI-inferred value, tap for details", button: true)` from the widget; the screen's surrounding field semantics are unchanged. |
