# Story ptd-1 — Debug perf overlay (kDebugMode-only request log)

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

Epic goal: make perf measurable and regressions catchable at PR time. ptd-1
is the developer-facing half — a floating overlay in debug builds that lists
recent HTTP requests so Leo can self-audit a flow in the simulator without
opening Chrome DevTools.

The epic soft-depends on `cla-6` (shared Dio interceptor from
epic-perf-client-analytics). `cla-6` is still backlog, so this story ships
a small local interceptor (~40 LOC) that is drop-in-replaceable when cla-6
lands. The local interceptor attaches to the existing `ApiClient._dio`
instance at boot under `if (kDebugMode)`.

## Scope divergence from epic text

The epic says "long-press on the Profile avatar". Palateful has no avatar
widget — the rightmost `NavigationDestination` in
`scaffold_with_bottom_nav.dart` is a plain `Icon(Icons.person_outline)`,
and tablets/web use a `NavigationRail` on the left. Wrapping a specific
`NavigationDestination` with a `GestureDetector` fights the framework's
tap-arbitration in NavigationBar and would be fragile.

**Chosen hit-zone:** a 64×64 translucent `GestureDetector` anchored to the
**top-right corner** of the screen, installed via `MaterialApp.builder`.
Works on every top-level screen across mobile/tablet/web regardless of nav
layout. `HitTestBehavior.translucent` + no `onTap` = taps pass through to
underlying UI; only long-press fires the overlay toggle. This is called
out in the commit message so the reviewer has one place to challenge.

## Implementation

### New files

- `app/lib/core/debug/perf_request_log.dart` — singleton ring buffer (100-entry capacity). `ValueNotifier<List<PerfRequestEntry>>` for reactive updates. Zero cost in release (never instantiated — nothing pushes).
- `app/lib/core/debug/perf_dio_interceptor.dart` — Dio `Interceptor` that stamps `onRequest`, measures `onResponse`/`onError` elapsed ms, pushes an entry to `PerfRequestLog.instance`. File is only imported from `main.dart` under `if (kDebugMode)`, so release tree-shakes it out.
- `app/lib/core/debug/perf_overlay.dart` — `PerfOverlay` widget wrapping its `child` in a `Stack`: (a) the child, (b) a 64×64 top-right hit-zone `GestureDetector` with `onLongPress: _toggle`, (c) a toggleable panel (50% of screen height) showing entries via `ValueListenableBuilder`. In release (`!kDebugMode`) the widget returns `child` unwrapped — zero overhead.

### Modified files

- `app/lib/main.dart` — under `if (kDebugMode)`, attach `PerfDioInterceptor` to `getIt<ApiClient>().dio.interceptors`. In `PalatefulApp.build`, pass `builder: (context, child) => PerfOverlay(child: child ...)` to `MaterialApp.router` under the same gate.

### New tests

- `app/test/core/debug/perf_request_log_test.dart` — ring-buffer add, overflow, ordering (newest first), clear.
- `app/test/core/debug/perf_overlay_test.dart` — pump the overlay wrapping a dummy Scaffold; confirm panel not visible by default, long-press at top-right toggles panel on, close button toggles off. Confirms tap passes through to the underlying Scaffold (no button-click eaten).
- `app/test/core/debug/perf_dio_interceptor_test.dart` — wire a Dio with a `MockAdapter`, hit it, confirm a `PerfRequestEntry` lands in the log with the expected method/path/status/duration.

## Acceptance Criteria

- [x] (1) `perf_overlay.dart` renders under `kDebugMode` only — returns `child` unwrapped in release.
- [x] (2) Long-press on the top-right 64×64 hit-zone toggles panel visibility from any top-level screen (installed via `MaterialApp.builder`, so every route is covered).
- [x] (3) Panel shows method + path + status + duration; scrollable; last 100 retained (display 20 at a time ≈ 1 screen height).
- [x] (4) Panel updates in real time via `ValueListenableBuilder` subscribed to `PerfRequestLog.entries`.
- [x] (5) Release-build tree-shake: the `perf_overlay.dart` / `perf_dio_interceptor.dart` / `perf_request_log.dart` modules are behind `if (kDebugMode)` gates in `main.dart`; Dart compiler eliminates them in release mode.
- [x] (6) Unit tests cover: ring buffer, interceptor → log plumbing, overlay toggle.

## QA walkthrough

1. `cd app && flutter run -d <simulator>` (debug build).
2. Sign in. Land on Home.
3. Long-press the top-right corner (any of the 64×64 region). Panel appears, showing the `GET /v1/recipe-books`, `GET /v1/favorites`, etc. that home just fired. Each row shows status (color-coded: green 2xx, orange 4xx, red 5xx / network error), method, `{ms}`, path.
4. Tap the close (×) icon → panel hides, underlying Home UI still reachable.
5. Navigate to Activity tab; long-press top-right → same panel, showing the `/v1/activities` calls just fired. Real-time update confirmed.
6. Long-press again while panel is open → panel toggles off (no double-visible state).
7. Run `flutter run --release`: long-press does nothing, no overlay widget in tree. Confirm via `flutter devtools → Widget Inspector` that `PerfOverlay` is not in the widget tree.

## Non-goals (deferred)

- No export / share button — overlay is read-only, screenshot for bug reports.
- No filter / search — 100 entries fits on one scrollable panel; good enough for single-flow auditing.
- No body/response inspection — just the metadata. Add if/when needed.
- No hit-zone customization — hardcoded top-right. If Leo wants to move it, one line in `perf_overlay.dart`.

## File List

- `app/lib/core/debug/perf_request_log.dart` (new)
- `app/lib/core/debug/perf_dio_interceptor.dart` (new)
- `app/lib/core/debug/perf_overlay.dart` (new)
- `app/lib/main.dart` (modified — install interceptor + overlay under kDebugMode)
- `app/test/core/debug/perf_request_log_test.dart` (new)
- `app/test/core/debug/perf_dio_interceptor_test.dart` (new)
- `app/test/core/debug/perf_overlay_test.dart` (new)
