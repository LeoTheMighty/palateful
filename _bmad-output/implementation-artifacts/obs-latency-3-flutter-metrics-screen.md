# Story obs-latency-3: Flutter admin metrics screen

**Status:** in-progress
**Epic:** epic-observability-latency

## Goal
Give Leo a one-tap path from "the app feels slow" to a concrete
endpoint/task to investigate. `/admin/metrics` renders a window selector
(1h / 24h / 7d, defaulted to 24h) + two sortable tables (endpoints,
tasks) with p50/p95/p99 + a 24-bucket sparkline per row. The existing
admin dashboard gains a "Metrics" card and two new top-stat tiles
("Overall p95 (24h)" + "Slowest endpoint").

## Scope
- New route `/admin/metrics` (gated by existing `isAdminProvider` guard).
- New screen `AdminMetricsScreen` with:
  - Window selector (`SegmentedButton<WindowOption>`).
  - Header "Last updated Xs ago" tick counter that resets on refresh.
  - Endpoints section + Tasks section, each a `MetricsTable` rendered in
    a `ListView.builder` for virtualization.
  - Pull-to-refresh reloads both sections.
  - Empty state, error state, shimmer-ish loading state follow the
    admin-errors-screen pattern.
- New widgets:
  - `LatencySparkline` — `CustomPainter` polyline within a 60×20 dp box.
  - `MetricsTable` — sortable columns, a `SparklineCell` per row.
- `AdminDashboardScreen` gets "Overall p95" + "Slowest endpoint" top
  stats (rendered alongside existing tiles) + a new "Metrics" nav tile.
- `ApiClient` gets `getEndpointMetrics(window)` and `getTaskMetrics(window)`.

## File List
- `app/lib/core/router/app_router.dart` — new `/admin/metrics` entry
- `app/lib/core/services/api_client.dart` — two new methods
- `app/lib/features/admin/admin_dashboard_screen.dart` — p95 tile,
  slowest-endpoint tile, metrics nav card
- `app/lib/features/admin/admin_metrics_screen.dart` — new
- `app/lib/features/admin/widgets/latency_sparkline.dart` — new
- `app/lib/features/admin/widgets/metrics_table.dart` — new
- `app/test/features/admin/admin_metrics_screen_test.dart` — new widget test

## Notes
- Kept the data model as plain Dart classes, matching the project
  convention (no freezed anywhere in the admin surface today). Instances
  build via `fromJson` constructors.
- Sparkline normalizes to the row's own max value so small numbers
  (e.g. 3 ms health checks) are still readable on the 20 dp canvas;
  all-zero buckets render as a flat baseline.
- `SegmentedButton` is 3.17+; the app is already on 3.19 (see pubspec).

## QA walkthrough
See `_bmad-output/implementation-artifacts/obs-latency-3-qa-walkthrough.md`.
