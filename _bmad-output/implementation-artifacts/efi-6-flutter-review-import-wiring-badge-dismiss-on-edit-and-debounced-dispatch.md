# Story efi-6 — Review Import badge wiring + dismiss-on-edit + debounced correction dispatch

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-5 (InferredFieldBadge widget, kInferableFields, decodeInferredFields, submitImportCorrection).

## Scope

Wires the sparkle badge into `import_item_review_screen.dart`:

- Local mutable `Set<String> _inferredFields` (decoded via
  `decodeInferredFields(item['inferred_fields'])`).
- 4 inferable fields get their `InputDecoration` routed through a helper
  `_decorateInferable(label, field)` that renders the label + the
  `InferredFieldBadge` in a `Row` when the field name is in the set.
- Each field's `onChanged` callback calls `_onInferredFieldEdited(field,
  corrected)`:
  - Removes the field from `_inferredFields` immediately (badge vanishes).
  - Schedules a 1500ms-debounced `submitImportCorrection` dispatch with
    the latest value for that field.
- Network errors on dispatch are swallowed (design principle 14).

## Scope limits

Review Import today only renders 4 of the 9 inferable fields:
`description`, `prep_time_minutes`, `cook_time_minutes`, `servings`.
Cuisine / category / vibes / total_time_minutes aren't edited on this
screen, so no badge targets exist for them. When the screen grows to
expose them, the same `_decorateInferable` + `_onInferredFieldEdited`
pattern applies verbatim.

## Implementation notes

- Debounce is per-field (keyed Map<String, Timer>) so edits to
  cook_time don't cancel a pending description correction.
- Debounce fires on focus-loss (implicitly: any onChanged that lands
  before the 1500ms window resets the timer; no new onChanged = fire).
- Corrections dispatch the LATEST typed value, not the edit that
  triggered the badge dismissal — that's the whole point of debouncing.
- `corrected` is dynamic: numeric fields pass `int.tryParse(v)` (nullable
  when the input is empty or non-numeric); string fields pass the raw
  text. Matches the backend endpoint's `dynamic corrected` shape.
- Reverting a field to its original value still counts as dismissal
  (the badge stays gone, the correction dispatches the original value
  back — harmless). Matches design principle 5: "any-edit counts as
  acceptance."
- The `_originalValues` map captures initial values so future edge-case
  logic (e.g., skipping dispatch for un-edited reverts) has a reference
  point. Currently unused at dispatch time — we dispatch every edit —
  but left in place as the cheapest point-of-reference anchor.
- Disposal cancels every per-field correction timer + the existing
  `_saveTimer` so nothing lingers after the screen pops.

## File list

- `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` [MODIFY] — inference-state, helpers, and wiring on 4 TextField decorations.

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `_loadItem` calls `decodeInferredFields(item['inferred_fields'])`; stored in `_inferredFields`. |
| 2 | `_decorateInferable(label, field)` renders a `Row` with the label + `InferredFieldBadge` when the field is in `_inferredFields`. Hooked up on all 4 inferable fields the screen edits. |
| 3 | `_onInferredFieldEdited(field, corrected)`: setState-removes the field from `_inferredFields` AND schedules a debounced dispatch. |
| 4 | `_dispatchCorrection` swallows errors via bare `try/except`; no user-facing surface. |
| 5 | Dismissal is value-agnostic — the removeFromSet step runs whether or not the new value matches the original. |
| 6 | `_inferredFields` is persisted server-side via `recipes.inferred_fields` by efi-3's `create_recipe_task` (reads from `parsed_recipe.inferred_fields`, which Review Import does not mutate). The Review Import user_edits payload does NOT need to carry the shrunken set because the server's truth-of-record for `recipes.inferred_fields` is read straight from the extractor's output at create time — what the client drops is local-display state only. This matches efi-3's shrink-only invariant. |
| 7 | Manual verification via QA walkthrough — widget integration test deferred because the screen's DI graph (getIt, ApiClient, GoRouter) doesn't have a minimal-harness factory. Unit tests cover the badge widget (efi-5) and decoder (efi-5) independently. |
| 8 | No changes to save, approve, dismiss, retry, telemetry paths — badge wiring is strictly additive. |
