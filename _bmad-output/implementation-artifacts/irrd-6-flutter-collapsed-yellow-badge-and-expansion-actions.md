# irrd-6 — Flutter: collapsed yellow badge + blue pill + expansion actions

Status: **done**

## Scope

Surface the confidence badge + awaiting-review reason chip inline on
collapsed yellow rows; mount the `CompactStagePill` inline on collapsed
blue rows; build the expansion's bottom action-button row with Review
/ Retry / View Recipe / Archive, keyed on row state.

## Acceptance checklist (from epic)

- [ ] Collapsed yellow row: inline `ConfidenceBadge` (dense) + 1-word
  `AwaitingReviewReasonChip` alongside the recipe name.
- [ ] Collapsed blue row: `CompactStagePill` inline with the recipe
  name. Stage data is synthesized from the job's aggregate status
  (no per-item telemetry available for blue rows).
- [ ] Expansion actions row, per state:
  - Yellow: **Review →** (primary) + **Archive** (secondary)
  - Red: **Retry** (primary) + **Archive** (secondary)
  - Green: **View Recipe** (primary) + **Archive** (secondary)
  - Blue: no actions (cancel stays out-of-scope this epic)
- [ ] Optimistic fires:
  - **Archive** hides the row, 3s snackbar undo, calls
    `/v1/import-items/{id}/archive`.
  - **Retry** fires the existing retry endpoint; on success the row's
    statusLabel redraws to the pending state.
  - **Review** + **View Recipe** are pure go_router pushes.
- [ ] Action buttons respect ≥44dp hit targets; wrap on narrow widths.
- [ ] Widget test per state assertion (right button set for each
  state). Integration test: yellow expansion → tap Review → assert
  navigation to `/recipes/import/review/:itemId`.

## Wiring

- `AwaitingReviewReasonChip` — tiny new widget keyed on the
  `awaiting_review_reason` enum (irrd-1 exposed it on the list
  payload). Null renders nothing.
- `_ItemView` extended with `awaitingReviewReason` (already carries
  confidence fields from irrd-5).
- `ImportRow` gains an optional `leadingInlineContent` slot rendered
  right of the title, above the statusLabel. This is where the
  confidence badge + reason chip live for yellow, and the compact
  pill for blue. Keeping it an explicit named slot (vs hard-coded
  per-state logic inside `ImportRow`) preserves the widget's
  state-agnostic contract.
- `ImportRowExpansionActions` — new sub-widget that takes
  `{state, onReview, onRetry, onView, onArchive}` nullable callbacks
  and renders the right button set. Consumed inside the `_Body` of
  `ImportRowExpansion`. Each callback is wired per-row from
  `imports_tab.dart`.
- Archive path reuses the existing `_archiveItem` helper already
  plumbed in `imports_tab.dart`.
- Retry path calls `ApiClient.retryImport(itemId)` (already exists
  per mvp-6). On success, we invalidate the telemetry provider so
  the next render redraws the stage timeline, then show a quick
  "Retrying" snackbar. The row's statusLabel updates on the next 30s
  poll.

## Notes / deviations

- **Blue CompactStagePill uses synthesized stage data.** Because blue
  rows have no per-item `item_id` (the row is job-level), we
  synthesize an `ImportItemTelemetry` from the job's status /
  processedItems. Specifically: parsed → ok if processedItems > 0,
  else pending; extracted/matched/created → pending. This is
  cosmetic; the expansion renders nothing for blue rows anyway.
- **State-transition-while-expanded 500ms highlight flash (AC10 of
  irrd-4).** Still deferred — a follow-up can thread an animation
  controller into `_ExpandableRow`. The expansion persists naturally
  because the row id is stable.

## File list

New:
- `app/lib/features/activity/widgets/awaiting_review_reason_chip.dart`
- `app/lib/features/activity/widgets/import_row_expansion_actions.dart`
- `app/test/features/activity/widgets/awaiting_review_reason_chip_test.dart`
- `app/test/features/activity/widgets/import_row_expansion_actions_test.dart`

Modified:
- `app/lib/features/activity/widgets/import_row.dart` — add
  `leadingInlineContent` slot.
- `app/lib/features/activity/widgets/import_row_expansion.dart` —
  mount the actions row.
- `app/lib/features/activity/imports_tab.dart` — wire badges + pill
  + action callbacks.
- `app/test/features/activity/widgets/import_row_expansion_test.dart`
  — extend for the actions row rendering.
