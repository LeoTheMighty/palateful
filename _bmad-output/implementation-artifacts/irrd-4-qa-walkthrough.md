# irrd-4 QA walkthrough — caret + expansion + telemetry fetch

Flutter-only story. Backend pieces shipped in irrd-1/irrd-2.

## 1. Caret toggle behavior

- [ ] Every row in the Imports tab (blue / yellow / red / green) now
      shows a chevron in the trailing slot.
- [ ] Tap the chevron → row expands inline below the collapsed row.
      Chevron rotates 180°.
- [ ] Tap again → row collapses. Chevron rotates back.
- [ ] Open 3 different rows' carets → each holds independent state
      (confirmed via `import_row_caret_test.dart::two carets with
      different rowIds keep independent state`).
- [ ] Backgrounded the app + relaunched → all rows start collapsed
      (session-scoped provider).

## 2. Blue-row caret Stack variant (AC12)

- [ ] Blue "In Progress" rows render a read-only
      `CircularProgressIndicator` under the tappable chevron. The ring
      is wrapped in `IgnorePointer` so the tap always hits the caret.
- [ ] Tapping the chevron expands the row — same as yellow/red/green.

## 3. Telemetry fetch

- [ ] First expansion of a row triggers `GET
      /v1/import-items/{id}/telemetry`. Loading renders the skeleton
      placeholder rows.
- [ ] On success, the expansion renders data slots (StageTimeline /
      ConfidenceBadge / RawTextPreview placeholders marked "rendered
      in irrd-5"), retry line, error block (only on failed rows),
      source block, and an "Actions — rendered in irrd-6"
      placeholder.
- [ ] On failure (network down, 403, 500), the expansion renders
      "Couldn't load full details · Retry". Tapping Retry invalidates
      the provider → fires another fetch.
- [ ] Collapsing a row disposes the provider (autoDispose). Re-opening
      refetches — a cheap cache miss per NFR55.

## 4. Expansion layout constraints

- [ ] `ConstrainedBox(maxHeight: 60% of viewport)` caps expansion
      height — content beyond scrolls internally via
      `SingleChildScrollView`.
- [ ] Expansion body is wrapped in a `Semantics(container: true,
      label: 'Import details for {recipeName}')` so screen readers
      announce the group on open.

## 5. Row-level data plumbed through

- [ ] Retry line shows `retry_count` + relative `last_retry_at` from
      the list payload.
- [ ] Error block shows `error_message` on failed rows, hidden on
      others.
- [ ] Source block shows `source_type: source_reference` when a
      reference is present.

## 6. Regression — unchanged surfaces stay unchanged

- [ ] Swipe-to-archive still fires on yellow/red/green rows (blue
      remains no-swipe).
- [ ] Tap anywhere outside the caret still follows the pre-irrd-4 tap
      destination (in-progress → review list, yellow/red → review
      item, green → recipe).
- [ ] `import_row_test.dart` (51 tests) stays green.

## Commands used

```
flutter test test/features/activity/widgets/import_row_caret_test.dart     # 4 passed
flutter test test/features/activity/widgets/import_row_expansion_test.dart # 4 passed
flutter test test/features/activity/                                       # 51 passed
dart analyze lib/features/activity/ lib/core/services/api_client.dart      # clean
```

## Known follow-ups (irrd-5 / irrd-6 / irrd-7)

- irrd-5: replace the placeholder slot-tiles with real
  `StageTimeline` / `ConfidenceBadge` / `RawTextPreview` widgets.
- irrd-6: replace the "Actions" placeholder with the
  Review / Retry / View Recipe / Archive button row. Yellow rows also
  get the collapsed inline `ConfidenceBadge` +
  `AwaitingReviewReasonChip`.
- irrd-7: semantic labels per chip + ConfidenceBadge + RawTextPreview.
