# import-dup-3 — Frontend: DuplicateBanner + Approve-Import wiring

**Epic:** `epic-import-duplicate-detection`
**Status:** review
**Order in epic:** 3 of 4 (depends on stories 1 + 2; Story 4 is the cross-cutting regression sweep)

## Why

Stories 1 and 2 landed the backend half. This story is the user-facing
piece: when the Approve-Import screen loads and the response includes
a `duplicate.matches` array, render a **DuplicateBanner** above the
recipe form so the user sees "you already have this" at a glance,
with one-tap actions to Skip / Restore / Add anyway.

The banner is the entire payoff of the epic — it's the moment the
user stops re-importing the same internet recipe every six months and
stops forcing themselves to re-discover their own past judgment.

## Scope — files this story touches

**NEW**
- `app/lib/features/recipes/add_recipe/widgets/duplicate_banner.dart`
  — The banner widget. Stateful, owns a `TapGestureRecognizer` for
  the matched-title link; otherwise pure presentation.
- `app/test/features/recipes/add_recipe/widgets/duplicate_banner_test.dart`
  — 12 widget tests covering all three banner states + every action
  callback + the disabled / processing path.
- `_bmad-output/implementation-artifacts/import-dup-3-frontend-duplicate-banner-and-approve-import-wiring.md`
  (this file).
- `_bmad-output/implementation-artifacts/import-dup-3-frontend-duplicate-banner-and-approve-import-wiring-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `app/lib/features/recipes/add_recipe/import_item_review_screen.dart`
  — pull `duplicate.matches` out of the GET response, render the
  banner above the existing form, wire the four action handlers
  (`_onBannerSkip`, `_onBannerRestore`, `_onBannerAddAnyway`,
  `_onBannerTapMatch`) plus the multi-match `_onBannerShowAll`
  bottom sheet.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `import-dup-3-...: backlog → done`.

### Why no separate `ImportItemService`?

The epic text mentions extending an `ImportItemService` with
`skipImportItem`. There is no `ImportItemService` in the codebase
today — `ApiClient.skipImportItem` already exists (added in epic-3
of the original import pipeline) and the screen calls it directly
via `getIt<ApiClient>()`. Wrapping that in a per-feature service
would be premature abstraction; we'll extract one when a second
caller emerges. Scope deviation from epic text noted here so a
future reader doesn't grep for the missing service.

## Acceptance criteria (from the epic)

- [x] **Active match (blue) renders Skip + Add anyway** — verified by
  `test('renders active match in blue with Skip + Add anyway only')`.
- [x] **Archived match (amber) renders Restore + Skip + Add anyway**
  — verified by `test('renders archived match in amber...')`.
- [x] **Multi-match (list with "Show all matches")** — verified by
  `test('renders multi-match "Show all" button when otherMatchCount > 0')`.
- [x] **Banner shows existing recipe title (tappable → recipe detail),
  current book name, last_cooked relative time, archive date if
  archived** — `_onBannerTapMatch` deep-links to `/recipes/{id}`;
  copy verified by all rendering tests.
- [x] **Skip → calls `ImportItemService.skipImportItem` → bounces user
  to import-activity list** — `_onBannerSkip` calls
  `ApiClient.skipImportItem`, emits `ImportItemDismissed`, pops the
  screen. (No separate service — see note above.)
- [x] **Restore → calls `RecipeService.restoreRecipe` → also skips the
  import item → bounces back** — `_onBannerRestore` chains
  `restoreRecipe` → emit `RecipeUnarchived` → `skipImportItem` →
  emit `ImportItemDismissed` → pop. Restore-failure aborts and
  surfaces a SnackBar; skip-failure after restore is a non-fatal
  warning.
- [x] **Add anyway → proceeds with existing Approve flow** —
  `_onBannerAddAnyway` flips `_duplicateDismissed` so the banner
  hides for the rest of the screen's lifetime; user edits + taps
  the existing Save Recipe button.
- [x] **Widget tests cover all three banner states + all action paths**
  — 12 tests in `duplicate_banner_test.dart`, all passing.

## Implementation notes

### Color palette via theme tokens

Active = `colorScheme.primaryContainer` background, `onPrimaryContainer`
text, `primary` accent. Archived = `tertiaryContainer` /
`onTertiaryContainer` / `tertiary`. Both palettes work in light + dark
mode without hard-coded hex. The Material theme already defines
`tertiary` as warm amber-orange, which gives the "we already saw this
and you put it away" vibe the epic asks for.

### Why a stateful widget (not stateless) for a presentational banner?

`TapGestureRecognizer` is a `Listenable` that needs disposal. The
recognizer is bound to the matched-title `TextSpan` so taps on the
title (which is rendered as an inline rich-text link) deep-link to
recipe detail. Wrapping the title in an `InkWell` would force a
block-level tap target, breaking the inline-link styling. State is
limited to the recognizer's lifecycle.

### `_isProcessingDuplicateAction` guard

A user on flaky cellular can tap Skip → spinner doesn't appear fast
enough → tap Skip again. The existing skip endpoint is now idempotent
(story 2), but we still want one-tap-only UX. The guard short-circuits
the second tap on the client side, and disables every button while a
mutation is in flight. Tap-on-match-name still works (it's pure
navigation, not a mutation).

### Restore: failure-mode reasoning

The restore flow is two sequential API calls: `restoreRecipe` then
`skipImportItem`. Failure modes:

1. Restore fails → no skip, surface error SnackBar, stay on screen.
   The user can retry. The recipe stays archived; the import stays
   in awaiting_review. No state is left half-applied.
2. Restore succeeds, skip fails → recipe is restored; import lingers.
   Surface a soft warning. The user can dismiss the import from the
   activity feed later. Far better than rolling back the restore
   (which would delete history again).
3. Both succeed → pop the screen with `true` (caller treats this as
   "import handled").

### Multi-match bottom sheet

When `otherMatchCount > 0`, show a "+N more matches — show all"
button. Tap → opens a `showModalBottomSheet` listing all matches
with their book name + archived state. Tapping a row deep-links to
that recipe (no Skip / Restore action — those are reserved for the
banner's primary match because the user picked that one explicitly).

This keeps the banner compact (one match worth of vertical space)
while still surfacing the multi-match case discoverably.

### Mutation events emitted

| Action | Events emitted | Why |
|---|---|---|
| Skip | `ImportItemDismissed` | Imports tab + see-all + activity refresh |
| Restore | `RecipeUnarchived` then `ImportItemDismissed` | Book's recipe list + Archive view + import feed all refresh |
| Add anyway | none | No backend mutation; subsequent Approve fires its own events |
| Tap match | none | Pure navigation |

## Tests

12 widget tests in `DuplicateBannerTests`, all passing:

| # | Test | Asserts |
|---|---|---|
| 1 | Renders active state | Blue, "You already have...", Skip + Add anyway only |
| 2 | Renders archived state | Amber, "You archived... on YYYY-MM-DD", Restore + Skip + Add anyway |
| 3 | Multi-match show-all button | Plural copy "+ N more matches — show all" |
| 4 | Singular match copy | "+ 1 more match — show all" |
| 5 | Skip fires onSkip | Tap → callback invoked once |
| 6 | Restore fires onRestore | Tap on archived banner → callback invoked once |
| 7 | Add anyway fires onAddAnyway | Tap → callback invoked once |
| 8 | Show all fires onShowAll | Tap → callback invoked once |
| 9 | All buttons disabled when isProcessing | Taps are no-ops when mutation in flight |
| 10 | Renders last_cooked when present | "last cooked X ago" appears in copy |
| 11 | Omits last_cooked fragment when null | Phrase absent from copy |
| 12 | Falls back on malformed archived_at | Renders "an earlier date" instead of crashing |

## Local CI status

- `dart analyze` (banner + screen + test files) — clean (only 2 pre-
  existing warnings on `import_item_review_screen.dart` from before
  this story).
- `flutter test test/features/recipes/add_recipe/widgets/duplicate_banner_test.dart`
  — 12 passed.
