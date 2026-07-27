---
hash: rbv101
type: debug
created: 2026-07-27T17:30:00-06:00
title: Recipe-book view renders meal and recipe cards at different sizes
from: BUGS.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/debug-rbv101
---

## Goal
Everything in the recipe-book detail view renders at the same card size — meals and recipes visually uniform in the mixed grid.

## Acceptance criteria
- [ ] Repro exists (screenshot or widget test demonstrating the size mismatch in the book-detail mixed grid)
- [ ] Root cause documented with evidence in the status log
- [ ] Fix + regression test (widget test pinning card dimensions across both item types)

## Technical notes
- Reported in BUGS.md (top, newest entry): "Everything in the recipe book view should be the same size, meals and recipes."
- The book-detail screen renders recipes + meals in a single mixed grid sorted by `updated_at` (see the ffm-5 skip note in `_bmad-output/implementation-artifacts/sprint-status.yaml` for context on that screen's layout).

## Status log
- 2026-07-27T17:30 — imported from BUGS.md during BMAD→devx migration
- 2026-07-27T11:03:31-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
- 2026-07-27T17:25:13.019Z — loop iteration 1: Reproduced, root-caused, and fixed the book-detail card size mismatch: meals and recipes now render at identical dimensions in every layout, pinned by a 5-test widget regression suite.
  - Change: Added MixedCardBody + mixed_card_metrics shared layout: fixed 180pt hero over an info block that fills the parent's box (128pt fallback when unbounded), clipped rather than overflowing — this is what makes both card types come out the same size
  - Change: Extracted the screen-private _RecipeCard into a public BookRecipeCard widget so card geometry is testable, and capped its tag row at 2 chips to match home's RecipeCard
  - Change: Replaced book detail's two divergent grid branches (plain Column at 1 column, childAspectRatio 0.75 above) with a single GridView using mainAxisExtent: kMixedCardExtent for all column counts
  - Change: Rewired MealTile onto MixedCardBody so it stops sizing to its own text
  - Change: Added app/test/features/recipe_books/book_card_sizing_test.dart — 5 tests covering cross-type equality, content-independence, overflow safety, no-silent-clipping, and grid-cell/card agreement
  - Learning: The visible bug lived entirely in the columns==1 branch of recipe_book_detail_screen.dart (Column(children: cards)) — phones are under the 600pt breakpoint, so users never hit the grid branch. Measured mismatch at 390pt: recipe 320px vs meal 262px.
  - Learning: Home's RecipeCard uses an AspectRatio(1.2) hero, so switching home's grid to a fixed mainAxisExtent overflows it by 111px at wide widths and breaks 27 home tests. Home must keep its aspect-ratio delegate; the cards have to fill-the-box rather than be rigidly fixed-height.
  - Learning: MealTile is shared with home and is also unit-tested in an unbounded Center, so it cannot use a bare Expanded — MixedCardBody branches on constraints.maxHeight.isFinite to stay valid in both contexts.
  - Learning: MealTile already overflowed its home grid cell by ~37px before this work (270pt content in a 233pt cell); the fill-the-box change silently fixes that too.
  - Learning: Recipe info content needs 128pt, not the 108pt I first guessed — 108 clipped the tag row by 8px with no error, since Card's clipBehavior: antiAlias hides it. A test asserting the last Chip's bottom stays inside the info block now guards the constant.
  - Learning: Running `dart format` on these files applies a newer formatter style than the repo uses and churns unrelated lines; there is no CI format gate, so edits should be hand-formatted to match surrounding code.
  - Learning: 3 tests in test/features/activity/imports_tab_test.dart fail on a clean tree (pre-existing, unrelated) — expect 1526 pass / 3 fail as the current suite baseline.
