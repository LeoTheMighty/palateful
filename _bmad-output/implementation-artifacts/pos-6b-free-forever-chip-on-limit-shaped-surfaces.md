# Story pos-6b — FreeForeverChip on limit-shaped surfaces

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)

## Goal

Ship the `FreeForeverChip` widget — locked as **the** canonical
affordance for any surface where a competitor would render a paywall.
Mount it on the two surfaces named in the epic refinement (recipe-
import sheet footer + recipe-book invite bottom sheet). Document the
cross-epic contract: every later epic that touches a limit-shaped
surface must mount this widget, not invent feature-specific copy.

## Acceptance criteria

- [x] New widget `app/lib/shared/widgets/free_forever_chip.dart` with
  three variants (`FreeForeverChip()`, `FreeForeverChip.import()`,
  `FreeForeverChip.household()`). Headline copy is locked at
  `Unlimited — free forever`; subtitle varies per variant.
- [x] Mounted on `AddRecipeSheet` footer below all import options.
- [x] Mounted on the recipe-book invite bottom sheet (the
  `_showInviteBottomSheet` flow in
  `app/lib/features/recipe_books/recipe_book_members_screen.dart`)
  below the TabBarView.
- [x] Widget tests at `app/test/shared/widgets/free_forever_chip_test.dart`:
  default + import + household + Semantics composition + 360-px
  no-overflow (5 tests).
- [x] `tools/copy-grep-allowlist.txt` extended with the 4 hits the
  guard finds in the chip's source (doc comments + import-variant
  subtitle string).
- [x] Standalone QA walkthrough at `pos-6b-qa-walkthrough.md`.

## File List

- `app/lib/shared/widgets/free_forever_chip.dart` (new)
- `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart`
  (mount FreeForeverChip.import below import options)
- `app/lib/features/recipe_books/recipe_book_members_screen.dart`
  (mount FreeForeverChip.household below TabBarView in invite sheet)
- `app/test/shared/widgets/free_forever_chip_test.dart` (new — 5 tests)
- `tools/copy-grep-allowlist.txt` (4 entries for the chip widget)
- `_bmad-output/implementation-artifacts/pos-6b-free-forever-chip-on-limit-shaped-surfaces.md` (this file)
- `_bmad-output/implementation-artifacts/pos-6b-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Cross-epic contract (locked decision)

From the epic refinements: "FreeForeverChip widget is the single
approved affordance for any 'this would be a paywall in another app'
surface. Later epics (Recime import + social-video naturally limit-
shaped) reuse it; do not invent feature-specific copy."

Concrete enforcement:
- Variants are constants. Adding a fourth requires editing
  `free_forever_chip.dart` (so the catalog of approved subtitles is
  audit-visible in one file).
- The widget's doc comment names the contract explicitly.
- pos-6a's grep guard catches paywall vocabulary regressions
  elsewhere; this widget's headline `Unlimited — free forever` is the
  positive surface that fills the void where a paywall would otherwise
  render.

## Out of scope

- Mounting on additional surfaces (calendar share sheet, future
  social-video import landing). Each later epic that lands a new
  limit-shaped surface mounts the chip itself — the contract is in
  the widget, not in this story's File List.
- Animation / dismissibility / per-user "I get it, hide this" toggle.
  The chip is a passive affordance, not a tutorial card.
- Backward-compat removal of the `FreeForeverChip()` (no-subtitle)
  variant if it goes unused — keep all three for now.
