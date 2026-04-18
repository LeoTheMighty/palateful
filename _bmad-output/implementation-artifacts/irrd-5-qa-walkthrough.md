# irrd-5 — QA walkthrough

Status: **done**

## What shipped

Four new sub-widgets replace the `_SlotTile` placeholders inside
`ImportRowExpansion`:

- **`StageTimeline`** — horizontal 4-chip strip (Parsed · Extracted ·
  Matched · Created). Glyphs: check (ok), close (failed), em-dash (not
  reached), pulsing hourglass (current). Tooltip per chip surfaces
  duration + relative time. Background tinting routes through the
  `ImportStateColors` theme extension.
- **`ConfidenceBadge`** — compact badge with glyph + label; honors the
  null / <0.5 / 0.5–0.8 / >0.8 thresholds; adds a muted `*est`
  superscript when `source == 'heuristic'`. `dense` flag reserved for
  the irrd-6 collapsed-row variant.
- **`RawTextPreview`** — "Show {label}" toggle expanding a monospaced
  `SelectableText` in a 300px-max scrollable container. `Truncated`
  pill when the server-side preview was capped. Copy button dispatches
  `Clipboard.setData` and shows a "Copied" snackbar.
- **`CompactStagePill`** — 4-dot glance pill, current stage pulses.
  Lands with irrd-5 so unit tests can cover it independently; irrd-6
  wires it into the collapsed blue row.

`ImportRowExpansion._Body` now renders the real widgets and consumes
telemetry's first non-empty `parsed` / `extracted` previews. Confidence
score + source are threaded from `_ItemView` (now carrying
`confidenceScore` + `confidenceSource`) through `_ExpandableRow` into
the expansion.

## Deviations from the story text

- **Hover + long-press tooltip.** Used Flutter's built-in `Tooltip`
  which handles both without a custom handler.
- **Semantic lookups.** Because `Tooltip` wraps its child in its own
  `Semantics` node, widget tests probe semantic labels via
  `find.byWidgetPredicate((w) => w is Semantics && w.properties.label
  == X)` instead of `find.bySemanticsLabel`. Production screen readers
  still announce the merged label correctly — only the test harness
  lookup moved.
- **Infinite pulse vs. `pumpAndSettle`.** The current-stage pulse runs
  forever, so tests that previously used `pumpAndSettle` swap in
  bounded `tester.pump(const Duration(ms: 50))` loops.
- **Monospaced font** uses `Menlo` on Mac/iOS with `Courier` /
  `monospace` as fallbacks — no new font asset added.

## Regression floor

- `flutter test test/features/activity/` — **75 tests pass** (+24 vs
  the 51-test irrd-4 floor).
- `dart analyze lib/features/activity/widgets/ lib/features/activity/
  imports_tab.dart test/features/activity/widgets/` — **No issues
  found.**

## Files touched

New:
- `app/lib/features/activity/widgets/stage_timeline.dart`
- `app/lib/features/activity/widgets/confidence_badge.dart`
- `app/lib/features/activity/widgets/raw_text_preview.dart`
- `app/lib/features/activity/widgets/compact_stage_pill.dart`
- `app/test/features/activity/widgets/stage_timeline_test.dart`
- `app/test/features/activity/widgets/confidence_badge_test.dart`
- `app/test/features/activity/widgets/raw_text_preview_test.dart`
- `app/test/features/activity/widgets/compact_stage_pill_test.dart`

Modified:
- `app/lib/features/activity/widgets/import_row_expansion.dart`
- `app/lib/features/activity/imports_tab.dart`
- `app/test/features/activity/widgets/import_row_expansion_test.dart`

## Manual QA checklist

- [ ] Open `/activity?tab=imports`, pick a yellow (needs-review) row,
      tap the caret. Expansion shows the 4-chip stage timeline with the
      correct check / hourglass / dash glyphs for the item's pipeline
      progress.
- [ ] The confidence badge renders to the right of the timeline with
      the expected threshold color (warning / neutral / check).
- [ ] When the extractor used the heuristic fallback, the `*est`
      superscript is present.
- [ ] Tap "Show parsed text" — the monospaced body appears, "Copy"
      copies to clipboard and shows the "Copied" snackbar.
- [ ] If the backend capped the preview, the "Truncated" pill is
      visible inline with the toggle.
- [ ] On a blue (in-progress) row, tap the caret — expansion is empty
      body (no per-item telemetry). The collapsed row does NOT yet
      show the `CompactStagePill` — that wiring lands in irrd-6.
- [ ] Long-press / hover on a stage chip — tooltip surfaces duration +
      relative time.
- [ ] Expand → collapse → re-expand — the rendered output matches the
      first open (sub-widgets don't lose state when the expansion
      re-mounts; the telemetry provider refetches, cheap per NFR55).
