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
class PerfNavigatorObserver extends NavigatorObserver {
  PerfNavigatorObserver({
    required ClientLatencyIngest Function() ingestResolver,
    required String? Function() routePathResolver,
    WidgetsBinding? binding,
  })  : _ingestResolver = ingestResolver,
        _routePathResolver = routePathResolver,
        _binding = binding;

  final ClientLatencyIngest Function() _ingestResolver;
  final String? Function() _routePathResolver;
  final WidgetsBinding? _binding;

  WidgetsBinding get _widgetsBinding => _binding ?? WidgetsBinding.instance;

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
    _ingestResolver().enqueue(
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
      _ingestResolver().enqueue(
        type: ClientLatencyType.routePaint,
        durationMs: stopwatch.elapsedMilliseconds,
        route: redacted,
      );
    });
  }
}
