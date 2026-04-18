# Story riip-8: Regression pass — three surfaces + structural snapshot

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Make sure the one-line ingredient row works everywhere it shows up,
and leave behind a test that fails loud if a future refactor
accidentally regresses back to the two-row layout.

## Scope (from epic)
- **Three surfaces confirmed** to render `StructuredIngredientRow`
  from riip-6's rewrite. Each already consumes the shared widget via
  `ingredient_edits_mapping.dart`; no per-surface code change was
  needed — the row swap is transitive.
  - Review Import (`import_item_review_screen.dart`)
  - Recipe wizard (`recipe_wizard_screen.dart`)
  - Recipe edit (`edit_recipe_screen.dart`)
- **Structural regression test** in
  `structured_ingredient_row_structure_test.dart` asserts:
  1. `qty`, `caret`, and `delete` share the same **immediate parent
     Row** — if a future edit splits them into two Rows inside a
     Column (the old two-row layout), the test fails.
  2. The notes field lives in the **expansion Row**, not the main Row
     — so "one-line plus expansion" stays the shape.
  3. Caret tap target ≥ 40pt (Material minimum) at 320-pt width.
- Cooking-mode read-only ingredient rendering audited and not
  touched (out of scope per epic ACs).

## What's explicitly deferred
- **Golden tests at iPhone SE 1st-gen** (AC7). Pixel-diff tooling
  requires reference images checked into the repo. The structural
  regression test above catches the `Row`→`Column` drift the epic
  called out as the failure mode golden tests would guard against.
  If Leo wants actual pixel regression coverage, that's a 0.5-day
  follow-up.
- **End-to-end smoke on a real device** (AC4). This loop doesn't have
  a physical device hooked up; the in-test layout assertions at 320-pt
  MediaQuery are a reasonable proxy, and every Flutter test exercises
  the full rendering pipeline. The real-device pass is a manual QA
  step before the release build — tracked in the QA walkthrough.

## File List
- `app/test/features/recipes/widgets/structured_ingredient_row_structure_test.dart` — new

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-8-qa-walkthrough.md`.
