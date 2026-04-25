# recipe-bulk-org-5 — Regression sweep + e2e

**Epic:** `epic-recipe-bulk-organize`
**Status:** review
**Order in epic:** 5 of 5

## Why

Stories 1–4 add new affordances (bulk Add/Move buttons, source
disambiguation, pill row) and modify a busy backend endpoint. Story 5
is the "did we break anything" sweep: re-verify the existing flows that
share the same surfaces and add a single end-to-end test that exercises
the multi-source bulk-move loop.

## Scope — what this story checks (no new code)

**Regression checks** (manual + existing widget tests under `flutter test`):

1. **Long-press → Archive** still works on home and on the recipe-book
   detail screen — story 1 added two buttons between the primary and
   archive slots without changing the archive plumbing.
2. **Create Meal / Add to Meal** primary-action flow unchanged for
   recipe-only and meal-mixed selections.
3. **Bulk-move authorization** — backend still rejects 403 when the
   user lacks editor/owner on the destination or any source book.
4. **Reactivity** — after a bulk move emit, both source and destination
   `recipeBooksProvider` / `homeContentProvider` invalidate; the home
   grid and book detail screens reflect the move without a manual
   refresh.

**e2e** (new test):

- `app/test/features/home/bulk_move_e2e_test.dart` — ProviderScope +
  fake `ApiClient` integration test that:
  - seeds 5 recipes across 2 source books
  - long-presses → Move to → picks a destination
  - confirms the priorMap is sent through the right service path
  - asserts the toast renders the expected breakdown text
  - asserts an Undo move groups by source and emits inverse calls

## Files this story touches

**NEW**
- `app/test/features/home/bulk_move_e2e_test.dart`
- `_bmad-output/implementation-artifacts/recipe-bulk-org-5-regression-sweep-and-e2e.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-bulk-org-5-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  this story `backlog → done` and the epic `in-progress → done`.

## Acceptance

- All existing widget tests under `app/test/features/home/` and
  `app/test/features/recipe_books/` pass.
- All API tests under `services/api/tests/test_recipe.py::TestBulkMoveRecipes`
  pass (covered by story 2).
- Manual regression checklist (in the QA walkthrough below) passes.
- The e2e test above exists and passes.
