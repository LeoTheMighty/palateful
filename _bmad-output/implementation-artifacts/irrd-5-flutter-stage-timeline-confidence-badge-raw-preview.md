# irrd-5 — Flutter: StageTimeline / ConfidenceBadge / RawTextPreview / CompactStagePill

Status: **done**

## Scope

Replace the `_SlotTile` placeholders inside `import_row_expansion.dart`
(landed in irrd-4) with the real rich-detail sub-widgets the epic
promises. Also ship the collapsed-blue-row **`CompactStagePill`**
(4-dot pulse pill) since irrd-6 depends on it and it's natural to
land with the stage-derivation logic here.

## Acceptance checklist (from epic)

- [ ] `StageTimeline` — horizontal 4-chip strip; ✓ / ⏳ (pulse) / ✗ /
  — glyphs per stage; theme-extension colors.
- [ ] Hover / long-press per chip surfaces duration + timestamp
  tooltip.
- [ ] `CompactStagePill` — 4-dot row with current-stage pulse,
  blue-only; expansion-free glance.
- [ ] `ConfidenceBadge` — score + source; null → `—`; <0.5 warning;
  0.5–0.8 neutral; >0.8 check; heuristic `*est` badge.
- [ ] `RawTextPreview` — label + payload; collapsed by default;
  expands to monospace `SelectableText` in a max-300px scrollable
  container; Truncated pill when server truncated; Copy button.
- [ ] `ImportRowExpansion` renders real widgets (one
  `RawTextPreview` per populated stage preview).
- [ ] Widget tests per sub-widget covering render + glyph thresholds +
  pulse-animation active + truncated-state rendering.

## Wiring

- `StageTimeline` reads the `ImportItemTelemetry` stages list.
  Current stage = first `pending` entry whose predecessors are all
  terminal (or the first `pending` when none are terminal yet).
  `failed` status wins in case of ambiguity (we stop advancing once a
  stage fails).
- `ConfidenceBadge` takes `{score: double?, source: String?}` — read
  off the list response `confidence_score` + `confidence_source` that
  irrd-3 exposed. Threaded through `_ItemView` + `ImportRowExpansion`.
- `RawTextPreview` takes `{label, text, truncated}` from a single
  `StageEntry`. The expansion renders one for `parsed` (OCR) and one
  for `extracted` (extractor JSON) whenever either has non-empty
  preview.
- `CompactStagePill` takes the same stage list as `StageTimeline`;
  rendered only on the collapsed blue row by irrd-6 (widget lands
  here so unit tests can cover it independently).

## Notes / deviations

- **Tooltip on chip** uses `Tooltip` with both `message` (hover) and
  long-press fallback (Flutter's default behavior). No custom
  long-press handler needed for AC3.
- **Pulse animation** uses `AnimationController` + `AnimatedBuilder`
  + `Tween<double>` on opacity — `vsync` via
  `SingleTickerProviderStateMixin`. Disposed on widget dispose; test
  verifies controller is running (`animation.status ==
  AnimationStatus.forward` after one pump).

## File list

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
- `app/lib/features/activity/widgets/import_row_expansion.dart` —
  swap `_SlotTile` placeholders for real widgets; accept
  `confidenceScore` + `confidenceSource` params.
- `app/lib/features/activity/imports_tab.dart` — extend `_ItemView`
  with `confidenceScore` + `confidenceSource`; thread into the
  `_ExpandableRow` composition.
- `app/test/features/activity/widgets/import_row_expansion_test.dart`
  — stubs updated to assert against the real widgets, not
  `_SlotTile`'s debug subtitle.
