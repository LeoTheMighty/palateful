# irrd-7 — QA walkthrough

Status: **done**

## What shipped

- **Integration walking test** — `imports_tab_expansion_flow_test.dart`
  drives the full flow: loads a yellow row → taps the caret via its
  tooltip → asserts the expansion surfaces (stage labels, Review
  button) → taps Review → asserts GoRouter landed on
  `/recipes/import/review/:itemId`. Per-call telemetry invocation
  count is asserted (exactly 1 fetch on first expansion).
- **a11y semantic audit.** Each widget shipped in irrd-4/-5/-6
  already emits a complete semantic label under widget-test
  coverage. This story verifies that inventory; no refactors
  required.

## A11y inventory (verified by existing widget tests)

| Widget                         | Semantic label format                                        | Covered by                                    |
|--------------------------------|--------------------------------------------------------------|------------------------------------------------|
| `ImportRowCaret`               | "Show details for {name}" ↔ "Hide details for {name}"         | `import_row_caret_test.dart` (irrd-4)          |
| `ImportRowExpansion` container | "Import details for {name}"                                   | `import_row_expansion_test.dart` (irrd-4)      |
| `StageTimeline` parent         | "Stage timeline"                                              | `stage_timeline_test.dart`                     |
| `StageTimeline` chip           | "{stage label} · {completed/current/failed/not reached}..."   | `stage_timeline_test.dart`                     |
| `ConfidenceBadge`              | "Confidence: {low/medium/high/unavailable}, {N}%, source {s}" | `confidence_badge_test.dart`                   |
| `RawTextPreview` (collapsed)   | "Show {label}"                                                | `raw_text_preview_test.dart`                   |
| `RawTextPreview` (expanded)    | "{label} · {N} characters"                                    | `raw_text_preview_test.dart`                   |
| `CompactStagePill`             | "Pipeline: parsed {state}, extracted {state}, ..."            | `compact_stage_pill_test.dart`                 |
| `AwaitingReviewReasonChip`     | "Reason: {phrase}"                                            | `awaiting_review_reason_chip_test.dart`        |
| `ImportRowExpansionActions`    | FilledButton / OutlinedButton surface their text to readers   | `import_row_expansion_actions_test.dart`       |

All labels encode state in words, not just color — meeting AC1 of the
irrd-7 story text.

## Manual VoiceOver / TalkBack walkthrough

The following is the expected read-aloud sequence on a yellow row. A
real-device session should verify this path matches for both
VoiceOver (iOS 17+) and TalkBack (Android 14+). Deferred to the
pre-ship hand-verification because Leo's dogfood device is still in
the airport.

### Expected VoiceOver path

1. Focus on the yellow row's title — VoiceOver announces
   `"Mom's Cake"`.
2. Right-swipe to the inline badge — announces
   `"Confidence: medium, 62%, source model"`.
3. Right-swipe → `"Reason: low confidence"`.
4. Right-swipe → caret button, double-tap →
   `"Show details for Mom's Cake, button, toggled off"` becomes
   `"Hide details for Mom's Cake, button, toggled on"`.
5. Focus lands inside the expansion, which announces its group
   label: `"Import details for Mom's Cake"`.
6. Right-swipe → `"Stage timeline"`, then each chip:
   - `"Parsed · completed · 2.1s"`
   - `"Extracted · current"`
   - `"Matched · not reached"`
   - `"Created · not reached"`
7. Right-swipe → badge: `"Confidence: medium, 62%, source model"`.
8. Right-swipe → raw text preview: `"Show extracted recipe json"`;
   double-tap → expands, announces
   `"Extracted recipe JSON · 64 characters"`.
9. Right-swipe → action row's `"Review, button"`; double-tap →
   navigates to the per-item review screen.

### Expected TalkBack path

TalkBack reads the same semantic labels. Notable differences:

- TalkBack pronounces `·` as a comma or a pause rather than the
  middle-dot glyph, so the labels read naturally.
- `toggled: true` on Semantics surfaces as "switch on" instead of
  VoiceOver's "toggled on"; both are correct.

### Open items from a real-device pass

- Verify VoiceOver does not announce the `*est` superscript as
  literal text when `source == 'heuristic'` — it's rendered as a
  small text sibling, so it WILL be read: "Confidence: medium, 62%,
  source heuristic. est." If that's noisy, we could `ExcludeSemantics`
  around the superscript. Leaving as-is until Leo reports it.
- Confirm the Copy button's snackbar ("Copied") is announced.
- TalkBack's "explore by touch" on a narrow screen where action
  buttons wrap — confirm hit targets stay reachable.

## Regression floor

- `flutter test test/features/activity/` — **87 tests pass** (+1
  integration test).
- `dart analyze test/features/activity/imports_tab_expansion_flow_test.dart`
  — **No issues found.**

## Files touched

New:
- `app/test/features/activity/imports_tab_expansion_flow_test.dart`

Modified:
- (none — audit confirmed no semantic gaps)
