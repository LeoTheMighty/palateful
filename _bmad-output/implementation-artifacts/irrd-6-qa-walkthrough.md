# irrd-6 — QA walkthrough

Status: **done**

## What shipped

- **Collapsed yellow rows** now render a dense `ConfidenceBadge` + a
  1-word `AwaitingReviewReasonChip` inline with the recipe name.
  Delivers the glanceable triage signal Leo asked for ("I can sort
  Needs Review by confidence without tapping anything").
- **Collapsed blue rows** render `CompactStagePill` inline with the
  job title. Stage data is synthesized from the job's aggregate
  status (`parsed` ok once processedItems > 0, everything else
  pending) since per-item telemetry isn't available for job-level
  rows.
- **Expansion action buttons** wired per state via
  `ImportRowExpansionActions`:
  - **Needs Review** → Review (primary, navigates to
    `/recipes/import/review/:itemId`) + Archive (optimistic, existing
    `_archiveItem` with snackbar-undo).
  - **Failed** → Retry (fires `POST
    /v1/import-items/:id/retry`, invalidates telemetry, "Retrying"
    snackbar) + Archive.
  - **Auto-Imported** → View Recipe (navigates to
    `/recipes/:id`) + Archive.
  - **In Progress** → no buttons (cancel stays out-of-scope for this
    epic per the PRD addendum).
- **`ImportRow`** gains a new `leadingInlineContent` slot rendered to
  the right of the title. Preserves the widget's state-agnostic
  contract — `imports_tab.dart` owns per-state composition and just
  drops a sub-tree in.
- **`_ItemView`** extended with `awaitingReviewReason` threaded
  through to the collapsed row. Irrd-3's `confidence_score` +
  `confidence_source` continue to flow through unchanged.

## Deviations from the story text

- **State-transition 500ms highlight flash** (AC10 of irrd-4). Still
  deferred — the expansion persists naturally across state
  transitions because the row's id stays stable in the expanded-set;
  only the animation polish is missing. Small follow-up.
- **Blue-row expansion remains empty.** We render the compact pill
  inline on the collapsed blue row (AC2 satisfied), but the
  expansion body stays empty for blue since there's no per-item
  telemetry to draw from. The expansion body is still discoverable
  via the caret but carries zero rich detail for now — a cancel
  action would be the natural future fill, and that's explicitly
  deferred.
- **Archive is wired via `_archiveItem`** — the same handler used by
  the swipe-to-archive path. The snackbar undo is reused verbatim.
- **Retry semantics.** We fire the retry endpoint, invalidate the
  telemetry provider, and show a brief snackbar. The row's
  `statusLabel` updates via the 30s poll; we don't force an
  immediate reload. Keeps the code simple and matches how swipe
  archive works.

## Regression floor

- `flutter test test/features/activity/` — **86 tests pass** (+11 vs
  the 75-test irrd-5 floor; +35 vs irrd-4's 51).
- `dart analyze lib/features/activity/{widgets,imports_tab.dart}
  test/features/activity/widgets/` — **No issues found.**

## Files touched

New:
- `app/lib/features/activity/widgets/awaiting_review_reason_chip.dart`
- `app/lib/features/activity/widgets/import_row_expansion_actions.dart`
- `app/test/features/activity/widgets/awaiting_review_reason_chip_test.dart`
- `app/test/features/activity/widgets/import_row_expansion_actions_test.dart`

Modified:
- `app/lib/features/activity/widgets/import_row.dart` — added the
  `leadingInlineContent` slot.
- `app/lib/features/activity/widgets/import_row_expansion.dart` —
  forwards per-state action callbacks into the new
  `ImportRowExpansionActions` row.
- `app/lib/features/activity/imports_tab.dart` — extended
  `_ItemView` + `_ExpandableRow`, wired collapsed-row inline content
  per state, derived per-state action callbacks, added `_retryItem`
  helper, synthesized job-level telemetry for the blue compact pill.

## Manual QA checklist

- [ ] Open `/activity?tab=imports`. Yellow (Needs Review) rows show
      the inline dense confidence badge next to the title, plus the
      reason chip ("low confidence" / "unmatched ingredients" /
      "missing title" / "manual review") when available.
- [ ] Blue (In Progress) rows show a 4-dot pill inline next to the
      title. Current dot pulses.
- [ ] Expand a yellow row → caret opens → action row renders with
      **Review** + **Archive**. Tap Review → navigates to
      `/recipes/import/review/:itemId`.
- [ ] Expand a red row → action row renders with **Retry** +
      **Archive**. Tap Retry → snackbar "Retrying" flashes; on next
      poll the row moves back to In Progress.
- [ ] Expand a green row → action row renders with **View Recipe** +
      **Archive**. Tap View Recipe → navigates to `/recipes/:id`.
- [ ] Expand a blue row → action row renders nothing.
- [ ] Archive button inside any non-blue expansion fires the same
      optimistic archive + snackbar-undo that swipe-to-archive
      provides today.
- [ ] Narrow the window — action buttons wrap to a second row and
      stay tappable.
