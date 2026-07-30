import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import '../router/route_redaction.dart';
import 'client_latency_ingest.dart';

/// NavigatorObserver that emits one `route_paint` event per route push
/// or replace (cla-4).
///
/// **Registration:** because this app uses
/// `StatefulShellRoute.indexedStack`, the root-level `GoRouter(observers:
/// ...)` list only fires for routes that target the root Navigator.
/// Branch-internal pushes (a recipe detail inside the Home tab) fire on
/// the branch's own Navigator. Tab swaps (`StatefulNavigationShell.goBranch`)
/// do not fire `didPush` on any Navigator — those are `IndexedStack`
/// index changes.
///
/// We therefore register the same observer on:
///   1. the root `GoRouter(observers: …)`, and
///   2. every `StatefulShellBranch(observers: …)` navigator, and
/// additionally have `ScaffoldWithBottomNav` call
/// [reportTabSwap] on every `onDestinationSelected` so bottom-tab
/// transitions are reported even though the Navigator stacks don't
/// change.
///
/// **Timing:** `didPush` fires when the new route is inserted into the
/// Navigator, **before** the first frame of the new screen paints. We
/// register `addPostFrameCallback` to measure paint completion and
/// emit `duration_ms = paint - t0`.
///
/// **Route name:** we prefer the caller-supplied template (e.g.
/// go_router's `state.fullPath` is already `/recipes/:id`). If the
/// caller passes a concrete URL (tab-swap reporter, or a Navigator with
/// raw `settings.name`), [redactRoute] scrubs UUIDs / long numeric ids.
///
/// **Absent ingest (e2egetit):** [ingestResolver] is nullable on purpose
/// and mirrors the `isRegistered<ClientLatencyIngest>()` guard every
/// other consumer already uses (`api_client`, `jankstats_bridge`,
/// `metrickit_bridge`). Two boot paths legitimately have no ingest
/// singleton: `E2E_MODE=true`, where `main()` skips
/// `_bootstrapClientLatencyIngest()` outright, and the first few frames
/// of a normal boot, where that bootstrap is `unawaited` behind a
/// `PackageInfo.fromPlatform()` probe. Resolving unconditionally threw
/// `Bad state: … ClientLatencyIngest is not registered inside GetIt`
/// out of a scheduler callback and took the whole router down with it.
/// A null resolve drops the event and logs once in debug — it is never
/// silent.
class PerfNavigatorObserver extends NavigatorObserver {
  PerfNavigatorObserver({
    required ClientLatencyIngest? Function() ingestResolver,
    required String? Function() routePathResolver,
    WidgetsBinding? binding,
  })  : _ingestResolver = ingestResolver,
        _routePathResolver = routePathResolver,
        _binding = binding;

  final ClientLatencyIngest? Function() _ingestResolver;
  final String? Function() _routePathResolver;
  final WidgetsBinding? _binding;

  /// Debug-only latch so an unregistered ingest is reported once rather
  /// than on every route push.
  bool _warnedMissingIngest = false;

  WidgetsBinding get _widgetsBinding => _binding ?? WidgetsBinding.instance;

  /// Resolves the ingest singleton, or null when it isn't wired yet.
  ClientLatencyIngest? _ingestOrNull() {
    final ingest = _ingestResolver();
    if (ingest == null && !_warnedMissingIngest) {
      _warnedMissingIngest = true;
      if (kDebugMode) {
        debugPrint(
          'PerfNavigatorObserver: ClientLatencyIngest not registered — '
          'dropping route_paint events (expected under E2E_MODE, and '
          'during the boot window before the ingest bootstrap resolves).',
        );
      }
    }
    return ingest;
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _recordPaint();
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    if (newRoute == null) return;
    _recordPaint();
  }

  /// Public entry-point for non-Navigator transitions. Today called by
  /// `ScaffoldWithBottomNav` on bottom-tab swap — `StatefulShellRoute`
  /// doesn't fire `didPush` for branch changes, so the observer would
  /// otherwise miss them. If [routePath] is null we read through to the
  /// resolver wired at construction (usually `appRouter.state.fullPath`).
  ///
  /// Unlike `didPush`, tab swaps don't carry a meaningful paint duration
  /// (`IndexedStack` keeps every branch mounted), so the emitted event
  /// carries `duration_ms = 0`.
  void reportTabSwap([String? routePath]) {
    final raw = routePath ?? _routePathResolver();
    final redacted = redactRoute(raw);
    if (redacted == null || redacted.isEmpty) return;
    _ingestOrNull()?.enqueue(
      type: ClientLatencyType.routePaint,
      durationMs: 0,
      route: redacted,
    );
  }

  void _recordPaint({String? overridePath}) {
    final stopwatch = Stopwatch()..start();
    _widgetsBinding.addPostFrameCallback((_) {
      stopwatch.stop();
      final raw = overridePath ?? _routePathResolver();
      final redacted = redactRoute(raw);
      if (redacted == null || redacted.isEmpty) return;
      _ingestOrNull()?.enqueue(
        type: ClientLatencyType.routePaint,
        durationMs: stopwatch.elapsedMilliseconds,
        route: redacted,
      );
    });
  }
}
