# irrd-4 — Flutter: caret + expansion + telemetry fetch

Status: **done**. Sub-widgets (stage timeline / confidence badge / raw
text preview) remain placeholders that irrd-5 fills in; action buttons
land in irrd-6; a11y polish in irrd-7.

## What shipped

- **`ImportRowCaret`** — `ConsumerWidget` chevron toggle mounted in the
  `trailing` slot of every `ImportRow`. Uses
  `ref.watch(importRowExpansionProvider.select((s) => s.contains(rowId)))`
  so toggling one row does NOT rebuild sibling rows. Blue-row variant
  stacks a read-only `CircularProgressIndicator` (wrapped in
  `IgnorePointer`) below the tappable chevron — reconciles ahr-4's
  "blue is visually read-only" rule with irrd-4 AC12 "all rows get a
  caret". 180° `AnimatedRotation` reflects expanded state. Semantic
  label toggles between "Show details for {name}" / "Hide details
  for {name}" with `Semantics(toggled: ...)`.
- **`importRowExpansionProvider`** — `NotifierProvider<Set<String>>`
  backing the toggle. Session-scoped (cleared on app restart).
  `toggle` / `expand` / `collapse` / `isExpanded` primitives. Set ids
  are `import_item.id` for normal rows and `import_job.id` for blue
  in-progress rows.
- **`importItemTelemetryProvider`** —
  `FutureProvider.autoDispose.family<ImportItemTelemetry, String>`
  keyed on `import_item.id`. Lazy: only fires when a widget actually
  watches it, i.e. on first caret-expand. Resolves from
  `ApiClient.getImportItemTelemetry(itemId)`.
- **`ImportItemTelemetry` + `StageEntry`** — typed models that parse
  the `GET /v1/import-items/{id}/telemetry` response into a list of
  four stage entries with timestamps / duration / raw preview.
- **`ImportRowExpansion`** — expansion body rendered below the
  collapsed row. Wraps a `SingleChildScrollView` inside a
  `ConstrainedBox(maxHeight: 60% of viewport)`. Semantic group with
  label "Import details for {name}". Three states:
  - **loading** — skeleton tile rows (animated-color placeholders).
  - **data** — placeholder slot-tiles for the three sub-widgets
    (StageTimeline / ConfidenceBadge / RawTextPreview slots) plus live
    retry line, error detail, source reference. Sub-widgets fill in
    irrd-5/6.
  - **error** — "Couldn't load full details · Retry" row; Retry
    invalidates the telemetry provider → next fetch re-triggers.
- **`_ExpandableRow`** — private composition widget inside
  `imports_tab.dart` that wraps each `ImportRow` in a Column +
  conditionally renders `ImportRowExpansion` below when the expansion
  provider includes the row's id. Blue (job-level) rows skip the
  per-item telemetry fetch because they have no single `item_id` to
  hang it off — their expansion renders the "Actions rendered in
  irrd-6" placeholder only.
- **`_ItemView` extended** — now carries `retryCount`, `lastRetryAt`,
  `errorMessage`, and `sourceReference` plumbed through from the list
  response into the expansion.
- **`ApiClient.getImportItemTelemetry`** — one-line dio GET wrapper.

## Deviations from the story text

- **AC5 cache-invalidation-on-status-change.** The story wants
  `ref.listen` on the list payload's `(status, last_successful_stage)`
  tuple; the implementation uses `autoDispose` so the provider is
  recreated per expansion cycle. Tradeoff: re-expanding within the
  same session refetches (cache miss on re-open, not just on status
  change). The endpoint is cheap (NFR55 target P95 < 300ms) and the
  epic's own note already accepted this ("re-fetch on every expand —
  the endpoint is cheap per NFR55"). Cache-per-session semantics can
  be tightened in a follow-up once irrd-5 is in place and we see the
  real cost.
- **AC10 state-transition-while-expanded 500ms highlight flash.** Not
  implemented this story. The expansion persists naturally across the
  state transition because the row's id is stable in
  `importRowExpansionProvider`; only the animation polish is deferred
  to irrd-6 along with the rest of the state-transition UX.

## Files touched

New:
- `app/lib/features/activity/providers/import_row_expansion_provider.dart`
- `app/lib/features/activity/providers/import_item_telemetry_provider.dart`
- `app/lib/features/activity/models/import_item_telemetry.dart`
- `app/lib/features/activity/widgets/import_row_caret.dart`
- `app/lib/features/activity/widgets/import_row_expansion.dart`
- `app/test/features/activity/widgets/import_row_caret_test.dart`
- `app/test/features/activity/widgets/import_row_expansion_test.dart`

Modified:
- `app/lib/core/services/api_client.dart` — `getImportItemTelemetry`
- `app/lib/features/activity/imports_tab.dart` — wraps each row in
  `_ExpandableRow`, extends `_ItemView` with the extra fields the
  expansion needs.

## Test results

- `flutter test test/features/activity/widgets/import_row_caret_test.dart` — **4 passed**.
- `flutter test test/features/activity/widgets/import_row_expansion_test.dart` — **4 passed**.
- `flutter test test/features/activity/` — **51 passed** (no
  regressions on existing activity tests).
- `dart analyze app/lib/features/activity/ app/lib/core/services/api_client.dart` — clean
  (pre-existing deprecation warnings on `import_history_screen.dart`
  are untouched).
