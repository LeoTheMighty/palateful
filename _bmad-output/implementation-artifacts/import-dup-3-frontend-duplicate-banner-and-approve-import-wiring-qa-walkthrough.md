# import-dup-3 — QA Walkthrough

**Story:** `import-dup-3-frontend-duplicate-banner-and-approve-import-wiring`
**Date:** 2026-04-25

## Summary

Adds the `DuplicateBanner` widget that renders above the Approve-Import
form when the GET response includes `duplicate.matches`. Three button
states (active blue / archived amber / multi-match list-expand). All
four actions wired: Skip / Restore / Add anyway / tap-match (deep-link
to recipe detail).

## Files

| File | Status | Purpose |
|---|---|---|
| `app/lib/features/recipes/add_recipe/widgets/duplicate_banner.dart` | new | Banner widget; stateful for `TapGestureRecognizer` lifecycle |
| `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` | modified | Pull `duplicate.matches`, render banner, wire 5 action handlers |
| `app/test/features/recipes/add_recipe/widgets/duplicate_banner_test.dart` | new | 12 widget tests covering rendering + actions + processing-state |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `import-dup-3-...: backlog → done` |
| `_bmad-output/implementation-artifacts/import-dup-3-frontend-duplicate-banner-and-approve-import-wiring.md` | new | Story spec |
| `_bmad-output/implementation-artifacts/import-dup-3-frontend-duplicate-banner-and-approve-import-wiring-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 Active match (blue) renders Skip + Add anyway | `test('renders active match in blue with Skip + Add anyway only')` | `duplicate_banner_test.dart` |
| AC #2 Archived match (amber) renders Restore + Skip + Add anyway | `test('renders archived match in amber...')` | `duplicate_banner_test.dart` |
| AC #3 Multi-match list with "Show all" | `test('renders multi-match "Show all" button')` | `duplicate_banner_test.dart` |
| AC #4 Banner shows title (tappable), book name, last_cooked, archive date | Rendering tests + `_onBannerTapMatch` deep-link | `duplicate_banner_test.dart` + `import_item_review_screen.dart` |
| AC #5 Skip → calls API + bounces back | `_onBannerSkip` impl | `import_item_review_screen.dart` |
| AC #6 Restore → restoreRecipe + skip + bounce | `_onBannerRestore` impl | `import_item_review_screen.dart` |
| AC #7 Add anyway → existing Approve flow | `_onBannerAddAnyway` flips `_duplicateDismissed` | `import_item_review_screen.dart` |
| AC #8 Widget tests cover three states + all actions | 12 tests | `duplicate_banner_test.dart` |

## Manual QA checklist (~10 min)

Run the local stack with `docker compose up`. Need at least one user
with ≥2 recipes (one active, one archived).

### Case A — Active match (blue banner)

1. Pick an active recipe — note its name.
2. Trigger an import (URL or paste-text) of a recipe with that exact
   name (case-insensitive, extra whitespace OK).
3. Open the Approve-Import screen for the parsed item.

**Expect:**
- Blue banner above the form with text:
  *"You already have **<title>** — currently in **<book>**[, last cooked X ago]."*
- The bold underlined title is tappable.
- Two buttons: filled "Skip" (primary), text "Add anyway".
- Form below is normal — user can still edit fields.

**Test each button:**
- **Skip** → spinner briefly → screen pops back to import-activity
  list. The import is now in `skipped` state.
- **Add anyway** → banner disappears (only). Form stays. Tap the
  bottom "Save Recipe" button to proceed with the original Approve
  flow — creates a second active recipe with the same name.
- **Tap title** → screen pops with `false`, app navigates to
  `/recipes/<id>` (the matched recipe's detail screen).

### Case B — Archived match (amber banner)

1. Archive a recipe (long-press → Archive on the recipe detail).
2. Re-import a recipe with that same name.
3. Open the Approve-Import screen.

**Expect:**
- Amber banner with text:
  *"You archived **<title>** on YYYY-MM-DD."*
- Three buttons: filled "Restore" (primary, amber), text "Skip", text
  "Add anyway".

**Test:**
- **Restore** → spinner → screen pops with `true`. The previously-
  archived recipe is now active again. The import is `skipped`.
- **Skip** (on archived banner) → import is skipped, archived recipe
  remains archived.

### Case C — Multi-match (>1 results)

1. Have two recipes with the same name (one active in book A, one
   active in book B; or one active and one archived).
2. Re-import that same name.

**Expect:**
- Banner shows the active match (sorted first, server-side).
- "+ 1 more match — show all" button below the headline.
- Tap "show all" → bottom sheet lists both matches with book name +
  archived chip. Tapping a row deep-links to that recipe.

### Case D — No match (regression)

Import a recipe whose name is unique in your library.

**Expect:** No banner. Standard form. Standard "Save Recipe" button.

### Case E — Processing state guard

Hard to reproduce manually without slow-network throttling. Covered
by `test('all action buttons disabled when isProcessing')`. Spot-
check by tapping Skip very fast twice on a slow connection — should
not double-fire (you'll see one spinner cycle, one snack toast).

## Test inventory

12 tests, all passing.

| # | Test | What it proves |
|---|---|---|
| 1 | renders active match in blue | Blue palette + Skip + Add anyway buttons |
| 2 | renders archived match in amber | Amber palette + Restore + Skip + Add anyway |
| 3 | renders multi-match "Show all" button | Show-all button visible when otherMatchCount > 0 |
| 4 | singular "match" copy | "+ 1 more match" (no plural) |
| 5 | Skip fires onSkip | Tap registers single callback |
| 6 | Restore fires onRestore | Tap on archived banner |
| 7 | Add anyway fires onAddAnyway | Tap registers single callback |
| 8 | Show all fires onShowAll | Tap registers single callback |
| 9 | all buttons disabled when isProcessing | No callbacks fire on tap |
| 10 | renders last_cooked when present | "last cooked X ago" in copy |
| 11 | omits last_cooked fragment when null | No "last cooked" in copy |
| 12 | falls back on malformed archived_at | "an earlier date" instead of crash |

## Local CI

| Gate | Result |
|---|---|
| `dart analyze` (banner + screen + test files) | clean (2 pre-existing warnings on screen, not from this story) |
| `flutter test test/features/recipes/add_recipe/widgets/duplicate_banner_test.dart` | 12 passed |

## Known follow-ups

- **Snapshot / golden tests** — not added here. Would lock the visual
  layout but would also break with every theme tweak. Visual QA is
  better handled in case-A/B above.
- **Integration test on `ImportItemReviewScreen`** — none added. The
  screen wires `getIt<ApiClient>()` directly; a real integration
  test would need DI override + a fake API client + go_router test
  harness. Out of scope for v1; covered by manual QA + the 12
  widget tests on the banner. Story 4 (regression sweep + e2e) is
  the right place to add an end-to-end Patrol test.
