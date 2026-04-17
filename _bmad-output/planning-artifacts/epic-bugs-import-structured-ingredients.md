<!-- refined via party-mode 2026-04-17 -->
# Epic: Bugs — Import Structured Ingredient Editor

## Overview

Commit `4f0de4c fix(extractor): stop duplicating quantity+unit in ingredient text` did the right thing on the backend: the extractor now emits separate `text`, `quantity`, `unit`, `name`, `notes`, `is_optional` fields per ingredient instead of cramming everything into one duplicated string. But the Flutter Import Review screen still binds only `ingredient['text']` (`app/lib/features/recipes/add_recipe/import_item_review_screen.dart:143–145`). Quantity, unit, and notes are silently invisible — the user reviews an ingredient and can't see "1/3 cup melted butter," only "butter."

The recipe wizard has the same gap with a different failure mode: it uses a single text input with a janky split-on-spaces parser (`recipe_wizard_screen.dart:_StepIngredients`), and stores ingredients in an internally-invented shape (`{quantity_display, unit_display, ingredient: {canonical_name}}`) that does not match what either backend endpoint actually accepts. The recipe edit screen (`edit_recipe_screen.dart`) has **no ingredient editor at all today** — only name, description, times, servings, source, tags, and steps are editable. Fixing only Review Import would leave three diverging UXes (Review, wizard, edit-with-no-ingredients); the user locked the decision to upgrade all three. (Bob)

## Goal

After this epic, every ingredient editing surface in the app — Review Import, the recipe wizard, and the recipe edit screen — uses one shared structured row component: numeric quantity, unit dropdown (curated list with free-text fallback), name, notes, and an optional toggle. The structured shape that the extractor and `create_recipe_task` already speak survives end-to-end without truncation. The recipe-create and recipe-update endpoints learn to accept a `name`-based ingredient input (find-or-create), mirroring the import path — a small, scoped backend change that the draft incorrectly claimed away.

## End-User Flow

### Photo or URL import → Review Import
1. User imports a recipe (photo or URL).
2. Backend extracts; the parsed-recipe JSON now contains `{text, quantity, unit, name, notes, is_optional}` per ingredient (current state, post-`4f0de4c`).
3. User opens Review Import for the item.
4. Each ingredient renders as a **structured row**: `[1/3] [cup ▾] [butter] [melted] [☐ optional]`.
   - Quantity field accepts integers, decimals (`0.333`), and common fractions (`1/2`, `1 1/2`).
   - Unit dropdown shows the curated list (cup, tbsp, tsp, oz, fl oz, ml, l, g, kg, lb, each, pinch, dash, clove, slice). User can type to filter; an "Add custom…" affordance allows free-text entry **for this row only** — not persisted into the catalog (per locked decision; surfaced subtly in the dropdown helper text).
   - Name and notes are plain text fields.
   - Optional toggle is a checkbox aligned right with an explicit semantic label tying it to the row's ingredient name (Sally — accessibility).
5. User edits any field; the existing 2-second debounce auto-saves.
6. Saved payload is the same structured shape — `create_recipe_task` consumes `name`, `quantity`, `unit`, `notes`, `is_optional` and find-or-creates the canonical Ingredient row (Winston verified).

### Recipe wizard (new recipe)
1. User taps "+ Recipe" in the wizard.
2. The ingredients step uses the **same structured row component** as Review Import.
3. The list starts with **one empty row pre-rendered** (Sally — empty state). A "+ Add ingredient" button at the bottom appends more.
4. User saves; the wizard sends `{name, quantity, unit, notes, is_optional}` per ingredient. The recipe-create endpoint find-or-creates the canonical ingredient (per the new backend story `bugs-imp-ing-5`) and persists the structured fields.

### Recipe edit (existing recipe)
1. User opens an existing recipe, taps "Edit".
2. The edit screen now includes an **Ingredients** section (currently absent) using the same structured row component.
3. Existing ingredient data hydrates: `quantity_display` from the GET response is a formatted string ("1 1/2") — the row parses it back to a number using the same fraction parser as the input field (Winston flagged the round-trip).
4. Legacy ingredients (created before structured fields existed) hydrate `canonical_name` into the name field; quantity/unit/notes start empty. Nothing is lost.
5. Edit/save/auto-save uses the existing 2s debounce pattern.

### What the user does NOT see change
- Recipe detail (read-only view) and cooking-mode ingredient strip continue to render display-formatted lines via existing code paths. This epic touches edit surfaces only.
- The version-snapshot pipeline (`update_recipe.py` `_create_version_snapshot`) keeps capturing the formatted `quantity_display` string into version rows — no change to history shape (Quinn flagged but verified safe).

## Frontend Changes

**Heavy.** All work is in `app/lib/`.

- New shared widget: `StructuredIngredientRow` — value-in / callback-out (no externally-owned controllers); five fields plus optional toggle; dense layout that fits two rows on iPhone SE 1st-gen width.
- New shared widget: `UnitInput` — dropdown of curated units with type-to-filter, free-text fallback via "Add custom…" entry, single source of truth for the unit catalog.
- New constant file: `app/lib/core/constants/ingredient_units.dart` — single ordered list of curated units. NFR43 is enforced here.
- New utility: `app/lib/core/utils/fraction_parser.dart` — parse `1/2`, `1 1/2`, `0.5` → `Decimal`-equivalent double; format double → fraction string. **Algorithm must mirror the Python `_decimal_to_fraction` (Fraction with `limit_denominator(8)`) so backend display and frontend round-trip agree** (Marcus).
- Modified screen: `import_item_review_screen.dart` — replace single TextField rendering with `StructuredIngredientRow` per ingredient; rewrite `_populateControllers()` and `_buildUserEdits()` to read/write structured shape (`{name, quantity, unit, notes, is_optional}`).
- Modified screen: `recipe_wizard_screen.dart` — replace `_StepIngredients`'s single text input + ad-hoc parser with a list of `StructuredIngredientRow`s; replace the wizard's invented `{quantity_display, unit_display, ingredient: {canonical_name}}` shape with the canonical `{name, quantity, unit, notes, is_optional}` shape; ensure `_saveRecipe` serializes correctly.
- Modified screen: `edit_recipe_screen.dart` — **add an Ingredients section that does not exist today**. Load `data['ingredients']`, render N `StructuredIngredientRow`s with hydration from formatted-string `quantity_display`, wire into the existing `_scheduleSave` debounce pattern. Sized for up to 50 ingredients without controller-leak (NFR40).
- Loading/empty/error states: empty rows render placeholders ("Qty", "Unit", "Name"); the wizard's Ingredients step starts with one empty row pre-rendered; the edit screen renders only what the recipe has plus an "+ Add ingredient" affordance.

## Backend Changes

**Small but real — the draft was wrong to claim "none".** (Winston)

- The Review-Import → `create_recipe_task` path already handles `{name, quantity, unit, notes, is_optional}` via find-or-create (`libraries/utils/utils/tasks/import_tasks/create_recipe_task.py:131–189`). No change.
- The recipe-create endpoint (`services/api/src/api/v1/recipe/create_recipe.py`) and recipe-update endpoint (`services/api/src/api/v1/recipe/update_recipe.py`) currently REQUIRE `ingredient_id: str` (UUID FK to `ingredients.id`). They reject any input lacking it. The wizard cannot send the structured shape end-to-end without a backend change.
- **Story `bugs-imp-ing-5` (NEW, P0):** extend `RecipeIngredientInput` to accept either `ingredient_id` OR `name`. When `name` is present and `ingredient_id` is absent, run the same find-or-create logic that `create_recipe_task._create_recipe_ingredient` uses (lowercase, strip, `find_or_create_by(canonical_name=...)` with `pending_review=True` for new ingredients).
- No schema migrations. No new endpoints. No new env vars.

## Infrastructure Changes

**None.** Genuinely no infra. (Confirmed by infra lens.)

## Design Principles (refined via party-mode 2026-04-17)

1. **One widget, three consumers** (Bob+Marcus) — Review Import, the recipe wizard, AND the recipe edit screen all use the same `StructuredIngredientRow`. Drift is the bug that motivated this epic; reuse is the prevention.
2. **Curated dropdown + free-text fallback, not free-text only** (Sally) — a dropdown gets 90% of users to the right unit fast; free text covers the long tail without forcing the dropdown to grow. Custom entries are per-row, not persisted into the catalog (locked decision); the dropdown helper text says so subtly.
3. **Don't lose user data on legacy ingredients** (Bob+Quinn) — recipes whose ingredients pre-date the structured shape render with `canonical_name` in the Name field and other fields empty, not error states. Nothing is lost or corrupted.
4. **Edit-side only** (locked) — this epic does not redesign read-only ingredient rendering on recipe detail or cooking mode.
5. **Numeric-on-the-wire, fraction-on-the-screen** (Marcus+Winston) — quantity is a `Decimal`/`float` over the wire; the Dart fraction parser+formatter mirrors the Python `format_quantity` algorithm (`Fraction.limit_denominator(8)`) so the same value round-trips identically through both languages.
6. **Backend find-or-create on name, not just on import** (Winston) — extending `RecipeIngredientInput` to accept `name` brings the create/update endpoints into parity with the import path. Same find-or-create rule, one place to evolve it (today: two callsites, the import task and now the endpoint helper).
7. **Delete-row uses snackbar-undo** (Sally) — deleting a row that may contain user-typed quantity/unit/name/notes is destructive enough to warrant the locked snackbar-undo pattern. The draft's "no confirm dialog" is correct; the missing nuance is *recovery*, not *prevention*.
8. **Field-render policy** (Quinn — borrowed from Activity Hub workshop) — every field on the structured ingredient shape is rendered in the row; no silent drops. If a future extractor adds a field (e.g., `prep_method`), it must be added to the row or annotated in code as intentionally-not-shown.

## Inherited Locked Decisions (carry forward to later epics in this run)

- **Ingredient `quantity` is `float`/`Decimal | null` on the wire; fractions are parsed/formatted client-side only.** The wire shape is numeric. This propagates to the photo-pipeline epic and any future ingredient-touching surface (cooking mode redesign, shopping-list autofill, eval fixtures).
- **Ingredient `unit` is a free-text string on the wire**, with the curated dropdown enforced only in the edit UI (NFR43 — Flutter constant). Backend never validates against the curated list. Future US/metric profile work, if it ever happens, would be a separate decision.
- **`name` (string) is an accepted alternate to `ingredient_id` on the recipe-create/update endpoints**, with server-side find-or-create (`pending_review=True` for new ingredients). Future endpoints that accept ingredient input should use the same shared helper.
- **The structured ingredient shape (`{name, quantity, unit, notes, is_optional}`) is canonical** for any client → server ingredient input. The legacy `{quantity_display, unit_display, ingredient: {canonical_name}}` shape from the wizard is dead after this epic; do not reintroduce it elsewhere.
- **Audit-log admin actions** (carries from prior epics — N/A in this epic but inherited rule).
- **Constructive actions don't get snackbar-undo; destructive ones do** (carries from prior epics — applies here to row delete).
- **Directories**: shared Flutter widgets → `app/lib/features/recipes/widgets/`; shared utils → `app/lib/core/utils/`; constants → `app/lib/core/constants/`.

## File Structure (expected)

```
app/lib/core/constants/
└── ingredient_units.dart                          # NEW — curated unit catalog (single source of truth)

app/lib/core/utils/
└── fraction_parser.dart                           # NEW — parse "1/2"/"1 1/2"/"0.5" → double; format double → fraction string (mirrors Python format_quantity)

app/lib/features/recipes/widgets/
├── structured_ingredient_row.dart                 # NEW — shared row widget (qty + unit + name + notes + optional)
└── unit_input.dart                                # NEW — dropdown + free-text fallback widget

app/lib/features/recipes/add_recipe/
├── import_item_review_screen.dart                 # MODIFIED — bind structured shape, render new row
└── recipe_wizard_screen.dart                      # MODIFIED — _StepIngredients replaced with list of StructuredIngredientRow; wizard state-model migrated to canonical shape

app/lib/features/recipes/
└── edit_recipe_screen.dart                        # MODIFIED — add brand-new Ingredients section using StructuredIngredientRow; hydrate quantity from formatted-string; wire into existing debounce save

services/api/src/api/v1/recipe/
├── create_recipe.py                               # MODIFIED (bugs-imp-ing-5) — IngredientInput accepts name OR ingredient_id; find-or-create when only name
└── update_recipe.py                               # MODIFIED (bugs-imp-ing-5) — same change to IngredientInput

services/api/src/api/v1/recipe/
└── _ingredient_input_helper.py                    # NEW (bugs-imp-ing-5) — shared find-or-create helper extracted from create_recipe_task._create_recipe_ingredient

app/test/core/utils/
└── fraction_parser_test.dart                      # NEW — round-trip + boundary cases

app/test/features/recipes/widgets/
├── structured_ingredient_row_test.dart            # NEW — widget test: render, edit, fraction parse, delete-with-undo
└── unit_input_test.dart                           # NEW — widget test: dropdown + free-text fallback

app/test/features/recipes/add_recipe/
├── import_item_review_screen_test.dart            # NEW or MODIFIED — round-trip
└── recipe_wizard_screen_test.dart                 # NEW or MODIFIED — wizard end-to-end including new shape

app/test/features/recipes/
└── edit_recipe_screen_test.dart                   # NEW — first ingredient-section coverage on edit

services/api/tests/
└── test_recipe_ingredient_input.py                # NEW — backend story bugs-imp-ing-5; verify name-only input creates pending-review ingredient and recipe ingredient row
```

## Story Map

| # | Story | Priority | Est. | Dependencies |
|---|-------|----------|------|--------------|
| bugs-imp-ing-1 | Curated units catalog + UnitInput dropdown widget | 🔴 P0 | 0.5 d | None |
| bugs-imp-ing-2 | StructuredIngredientRow shared widget + fraction parser | 🔴 P0 | 1 d | bugs-imp-ing-1 |
| bugs-imp-ing-3 | Integrate into Import Review screen | 🔴 P0 | 0.5 d | bugs-imp-ing-2 |
| bugs-imp-ing-5 | Backend: name-or-id input on recipe create/update | 🔴 P0 | 0.5 d | None (parallel with 1–3) |
| bugs-imp-ing-4 | Integrate into recipe wizard + edit (incl. new ingredient section on edit) | 🟡 P1 | 1.5 d | bugs-imp-ing-2, bugs-imp-ing-5 |

**Total: ~4 days.** Stories 1+2+3 (frontend Review track) and story 5 (backend track) can run in parallel; story 4 fan-ins both.

---

## Story bugs-imp-ing-1: Curated units catalog + UnitInput widget

As a user editing ingredient units anywhere in the app,
I want a dropdown of common units with a free-text fallback,
so that I pick "cup" in two taps but can still type "stalk" when I need to.

### Acceptance Criteria

1. New constant file `app/lib/core/constants/ingredient_units.dart` exports an ordered list `kCuratedUnits` containing: cup, tbsp, tsp, oz, fl oz, ml, l, g, kg, lb, each, pinch, dash, clove, slice. Order is intentional (most common first); list is the single source of truth (NFR43).
2. New widget `UnitInput` is a single-line input that opens a dropdown on focus showing the curated list. Typing filters the list as the user types. An "Add custom: '<typed-text>'" entry appears at the bottom when the typed text doesn't match any curated unit. The dropdown's helper-text footer reads "Custom units apply to this ingredient only" (Sally — surfaces the locked non-persistence decision).
3. Selecting a curated unit sets the value to the canonical short form (e.g., "tbsp" not "Tablespoon"). Selecting "Add custom" sets the value to the typed text verbatim.
4. The widget accepts an initial value that may be a curated unit, a custom unit, or `null`; renders correctly for all three.
5. Empty value renders a placeholder ("Unit").
6. The dropdown opens within 100ms of focus on a typical mid-tier device (NFR40 budget, measured in widget test via `pumpAndSettle` timing assert).
7. Widget tests cover: render with curated value, render with custom value, render with null, type-to-filter (3 letters → ≤3 results), custom entry creation, selection callback fires with correct value.
8. Widget is keyboard-accessible (arrow keys to navigate dropdown, Enter to select) and screen-reader labeled with `Semantics(label: 'Unit selector')`.

### Key Files

- Create: `app/lib/core/constants/ingredient_units.dart`
- Create: `app/lib/features/recipes/widgets/unit_input.dart`
- Test: `app/test/features/recipes/widgets/unit_input_test.dart`

---

## Story bugs-imp-ing-2: StructuredIngredientRow shared widget + fraction parser

As a user editing an ingredient in any screen,
I want quantity, unit, name, notes, and an optional toggle as separate fields,
so that I can see and correct each piece independently — instead of staring at a single mashed text field that hid them.

### Acceptance Criteria

1. New widget `StructuredIngredientRow` is value-in / callback-out: it accepts an `IngredientRowData` value object `{name, quantityNumeric, quantityRaw, unit, notes, isOptional}` and emits an `onChanged(IngredientRowData)` callback. **It does not own any controllers visible to its parent** (Marcus — controllers internal so reorder/insert/delete is safe). The parent owns a `List<IngredientRowData>` and a stable `key` per row.
2. Layout (mobile, smallest supported width = iPhone SE 1st-gen, ≥ 320 logical px):
   - Row 1: `[Quantity (numeric, narrow ~64px)] [UnitInput (~96px)] [Name (flex)]`
   - Row 2: `[Notes (flex)] [Optional toggle (right-aligned, ~80px incl. label)]`
   - Trash-icon delete affordance on the row's far-right edge of Row 1, **separated from the optional toggle by ≥ 24px** to reduce mistap risk (Sally).
   - Name field truncates with ellipsis if iPhone SE width forces it; full content remains accessible by focusing the field (no horizontal scroll on the row itself).
3. Quantity field accepts: integers (`2`), decimals (`0.333`, `1.5`), and common fractions (`1/2`, `3/4`, `1 1/2`). Uses `TextInputType.text` (not `.number`) on iOS so the `/` glyph is reachable; a custom hint subtitle reads `"e.g. 1/2 or 0.5"` (Sally — fraction-input UX). Fraction input is parsed via `fraction_parser.dart` and stored as a double; on display, doubles that round-trip cleanly to common fractions are rendered as fractions (`0.5` → `1/2`).
4. Empty quantity is allowed (rendered as placeholder "Qty"); unit and name may also be empty. Notes and `is_optional` are always optional.
5. Layout fits without horizontal scroll on iPhone SE 1st-gen and tablet widths (NFR40). A golden test is added at iPhone SE width (320×568).
6. **Delete-row uses snackbar-undo (3s)** per inherited locked decision: tapping trash removes the row from the list, surfaces a snackbar `"Ingredient removed. UNDO"`, and on undo re-inserts the row at its original index with the same `IngredientRowData`. (Sally)
7. Widget tests cover: render with all fields populated, render with empty fields, render with legacy ingredient (only `name` populated from `canonical_name`), edit each field independently, fraction parse round-trip, optional toggle toggles, delete + undo restores row at original index, golden at iPhone SE width.
8. Optional toggle has explicit `Semantics(label: 'Mark <name> as optional')` so screen readers connect it to its row (Sally — accessibility).

### Key Files

- Create: `app/lib/features/recipes/widgets/structured_ingredient_row.dart`
- Create: `app/lib/core/utils/fraction_parser.dart` — must mirror Python `format_quantity`'s `Fraction.limit_denominator(8)` algorithm so server-display and client-input round-trip identically.
- Test: `app/test/features/recipes/widgets/structured_ingredient_row_test.dart`
- Test: `app/test/core/utils/fraction_parser_test.dart` — boundary cases: `0`, `1`, `0.5`, `0.333` (≈ `1/3`), `0.1`, `1.25` (= `1 1/4`), `2.5`, `1/3`, `2 1/4`, malformed (`1//2`, `abc`, empty).

---

## Story bugs-imp-ing-3: Integrate StructuredIngredientRow into Import Review

As a user reviewing an imported recipe,
I want each parsed ingredient shown with its quantity, unit, name, and notes broken out and editable,
so that the post-`4f0de4c` extractor's structured output is finally visible to me.

### Acceptance Criteria

1. `import_item_review_screen.dart` replaces its single-TextField-per-ingredient rendering with a list of `StructuredIngredientRow` widgets backed by a `List<IngredientRowData>`.
2. `_populateControllers()` (or its replacement, e.g. `_populateRows()`) reads `parsed_recipe.ingredients[].{text, quantity, unit, name, notes, is_optional}` into per-row `IngredientRowData`. **When both `name` and `text` are present, `name` wins** (matches `create_recipe_task` precedence). When only `text` is present (legacy import-item rows), `text` populates the name field.
3. User edits to any field update the row's data via `onChanged`; on save, `_buildUserEdits()` (or its replacement) writes `user_edits.ingredients` as an array of `{name, quantity, unit, notes, is_optional}` objects (no `text`; the duplicated-string field is dead on the wire from this surface).
4. Empty quantity/unit/notes serialize as `null`, not `""` — matches what the extractor emits today and what `create_recipe_task` expects. (Quinn — explicit AC because the current `_buildUserEdits` writes `""`.)
5. A "+ Add ingredient" button at the bottom of the list appends a new empty row.
6. Delete uses the snackbar-undo pattern from story 2 (no confirm dialog, but recoverable).
7. Backend round-trip test: open Review Import for a fixture import-item, edit one ingredient's notes, save (debounce flush), re-open — the change persists in `user_edits`. Assert via API client mock or test fixture.
8. End-to-end-on-device sanity check (manual, recorded in PR description): photo-import a real cookbook page → open Review Import → confirm `1/3 cup melted butter` shows as `[1/3] [cup] [butter] [melted]` — the visible bug from this epic's motivation is gone.

### Key Files

- Modify: `app/lib/features/recipes/add_recipe/import_item_review_screen.dart`
- Test: `app/test/features/recipes/add_recipe/import_item_review_screen_test.dart`

---

## Story bugs-imp-ing-5: Backend — name-or-id input on recipe create/update endpoints

As the recipe-create and recipe-update endpoints,
I want to accept either an `ingredient_id` (existing canonical) or a `name` (find-or-create),
so that the wizard and edit-screen can send the same structured shape the import path already supports.

### Acceptance Criteria

1. `RecipeIngredientInput` (in both `create_recipe.py` and `update_recipe.py`, or extracted to `services/api/src/schemas/recipe.py`) gains an optional `name: str | None = None` field. `ingredient_id` becomes optional. **Validation**: at least one of `ingredient_id` or `name` must be present, else 400 with `ErrorCode.INGREDIENT_NOT_FOUND`-equivalent (or a new `ErrorCode.INGREDIENT_INPUT_REQUIRED` if a clean code does not exist).
2. When `ingredient_id` is present, behavior is unchanged — verify the existing canonical lookup path still 400s on bad UUIDs.
3. When `ingredient_id` is absent and `name` is present, the endpoint runs the same find-or-create logic as `create_recipe_task._create_recipe_ingredient` (lowercase, strip, `find_or_create_by(canonical_name=...)` with `pending_review=True` and `submitted_by_id=user.id` for new ingredients). The resulting ingredient's UUID is used as the FK on `RecipeIngredient`.
4. The find-or-create logic is **extracted into a shared helper** (e.g. `services/api/src/api/v1/recipe/_ingredient_input_helper.py` or a method on `Database`) so the endpoint and `create_recipe_task` use the same implementation. This is the only refactor in this story; do not relitigate `create_recipe_task` shape. (Winston)
5. `notes`, `is_optional`, `quantity`, `unit` continue to be accepted and persisted unchanged — verify with explicit assertions, no silent drops. (Quinn — field-render policy borrowed for backend.)
6. Tests: (a) name-only input on create → recipe + recipe_ingredient + new pending-review ingredient created; (b) name-only on update → same; (c) name matches an existing ingredient → reuses, does not create duplicate; (d) name-only-blank-string is rejected (no whitespace-only ingredients in the catalog); (e) ingredient_id-only continues to work; (f) both present → ingredient_id wins (avoid silent name drift); (g) neither present → 400.
7. No schema migration. No new DB columns. The audit-log path (existing pattern) records nothing because this is normal user-write — the `pending_review=True` flag on new ingredients is the existing review trail.
8. Backwards-compat: existing clients sending only `ingredient_id` continue to work without modification.

### Key Files

- Modify: `services/api/src/api/v1/recipe/create_recipe.py`
- Modify: `services/api/src/api/v1/recipe/update_recipe.py`
- Create: `services/api/src/api/v1/recipe/_ingredient_input_helper.py` (or equivalent location for shared helper)
- Refactor: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` — `_create_recipe_ingredient` calls the new shared helper instead of inlining find-or-create. (Optional within this story; can be a P2 follow-up if it bloats the diff.)
- Test: `services/api/tests/test_recipe_ingredient_input.py`

---

## Story bugs-imp-ing-4: Integrate StructuredIngredientRow into recipe wizard + edit

As a user creating or editing a recipe outside the import flow,
I want the same structured ingredient editor I see in Review Import,
so that I have one consistent UX for ingredient editing across the app — and the recipe edit screen finally lets me touch ingredients at all.

### Acceptance Criteria

1. The recipe wizard's ingredients step (`_StepIngredients` in `recipe_wizard_screen.dart`) is replaced: the single text input + ad-hoc parser is removed, and a list of `StructuredIngredientRow` widgets renders instead. The wizard's `_ingredients` state changes from `List<Map<String, dynamic>>` of the legacy `{quantity_display, unit_display, ingredient: {canonical_name}}` shape to `List<IngredientRowData>` of `{name, quantity, unit, notes, is_optional}`. The serialization in `_saveRecipe` writes the canonical shape.
2. The recipe edit screen (`edit_recipe_screen.dart`) **gains a new Ingredients section that does not exist today**. The section loads `data['ingredients']` from `getRecipe`, hydrates each into an `IngredientRowData` (parsing the GET response's formatted-string `quantity_display` back to a number via `fraction_parser.dart`), and renders `StructuredIngredientRow` widgets. Save uses the existing `_scheduleSave` 2s debounce.
3. New-recipe wizard: the ingredients list starts with **one empty row pre-rendered** (Sally — empty state). "+ Add ingredient" appends more.
4. Edit-existing-recipe: existing ingredient data hydrates into structured rows. Legacy ingredients (no quantity/unit/notes captured at create time) hydrate `canonical_name` into the name field with the rest empty. **Nothing is lost or corrupted.**
5. Save persists structured fields via the recipe-create / recipe-update endpoints **after `bugs-imp-ing-5` lands**. Wizard sends `{name, quantity, unit, notes, is_optional}` per ingredient (no `ingredient_id` for net-new); edit sends `ingredient_id` (preserved from GET) plus structured fields for existing rows, and `{name, ...}` for newly-added rows.
6. **Regression — read-side**: recipe detail (read-only) and cooking-mode ingredient strip continue to render display-formatted lines correctly after a structured-edit save. The `format_quantity` server-side formatter has not changed. Verify via a focused regression test on `get_recipe` after an update.
7. **Regression — version snapshot**: `update_recipe.py:_create_version_snapshot` continues to capture ingredients into `recipe_versions.snapshot` JSONB without error. The snapshot already uses `format_quantity` — no change to history shape. Verify via existing version-creation tests still pass; add one new test for the name-only ingredient input path. (Quinn)
8. iPhone SE width: the ingredients section in both wizard and edit screens scrolls vertically without horizontal overflow for a recipe with 50 ingredients (NFR40). Controller lifecycle is clean: opening + closing the edit screen 10 times in a row does not leak controllers (verified via `WidgetsBinding.instance.testTextInput` or framework-level lifecycle counters in widget test).
9. End-to-end test: create a new recipe via the wizard with a structured ingredient (`1/2`, `cup`, `butter`, `melted`); save; reopen in edit mode; verify all four fields hydrate correctly (quantity displays as `1/2`, not `0.5`, in the input field).
10. End-to-end test: edit an existing recipe with legacy ingredients (canonical_name only); add structured fields to one ingredient; save; reopen — both legacy and newly-structured ingredients render correctly.

### Key Files

- Modify: `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` (`_StepIngredients` rewritten; wizard state-model migrated; `_saveRecipe` serialization updated)
- Modify: `app/lib/features/recipes/edit_recipe_screen.dart` (new Ingredients section added; hydration logic written; `_scheduleSave` payload extended with `ingredients`)
- Test: `app/test/features/recipes/add_recipe/recipe_wizard_screen_test.dart`
- Test: `app/test/features/recipes/edit_recipe_screen_test.dart`

## Dependencies

- bugs-imp-ing-1 → bugs-imp-ing-2 (StructuredIngredientRow uses UnitInput)
- bugs-imp-ing-2 → bugs-imp-ing-3 (Review Import consumes the row widget)
- bugs-imp-ing-2 + bugs-imp-ing-5 → bugs-imp-ing-4 (wizard + edit consume the row widget AND require the backend to accept name-based input)
- bugs-imp-ing-5 has no dependencies; runs in parallel with the frontend track.

No cross-epic dependencies. This epic is independent of `epic-bugs-import-photo-pipeline` — the structured fields it surfaces already exist on every ingredient regardless of how many recipes came from one photo. The "ingredient quantity is float on the wire" rule (Inherited Locked Decisions) does propagate into the photo-pipeline epic if it ever touches ingredient shape.

## Resolved Workshop Questions (answered 2026-04-17)

1. **Custom-unit persistence:** **No memory, strictly per-row.** Custom unit applies to that one ingredient row only; never auto-promoted to the curated dropdown; no per-user MRU layer. The Flutter constant in `ingredient_units.dart` is the catalog.
2. **`pending_review` ingredient surfacing:** **Defer — SQL is fine for now.** No new admin-review UI in this epic. Today's review path (admin-only `/v1/ingredients/pending` if it exists, or direct SQL) covers the volume. Revisit when noisy.
3. **Cooking-mode strip regression coverage:** **Lock the default — add one focused regression test in story 4 AC6.** The cooking-mode strip's `quantity_display` read path is unchanged but a one-test guard is cheap insurance.

## Open Questions for the User

None. All workshop-spawned questions resolved.
