import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/scheduler.dart';

import 'client_latency_ingest.dart';

/// Subscribes to `SchedulerBinding.addTimingsCallback` and emits one
/// `frame_jank_p95` event per minute with separate p95s for build-span
/// and raster-span (cla-5).
///
/// Each [FrameTiming] carries two spans of interest:
///   - `buildDuration` — widget/Element build + layout + paint (UI
///     thread).
///   - `rasterDuration` — GPU/raster thread time.
/// 60fps budget is 16.6 ms; jank = frames over budget on either span.
/// We report both p95s so jank attribution can tell whether the UI
/// thread or the GPU is under load.
///
/// The aggregator keeps a rolling window of timings in memory. Every
/// [flushInterval] (default 60s) we compute p95 of each span, the
/// count of over-16.6ms frames in the window, and emit one event. The
/// per-call overhead is a list append; flushing is the actual work
/// (sort + indexing) and happens off the critical path.
///
/// Implementation caveats:
/// - We never hold more than [maxSamples] timings (default 10 000) —
///   a runaway situation where flush never runs should still bound
///   memory. In practice a 60s window at 60fps is ~3 600 samples.
/// - `duration_ms` on the emitted event is set to **build-span p95**
///   (the most common jank axis). Raster-span p95 lives in the
///   `extra` jsonb under `raster_p95_ms` so it's queryable but doesn't
///   double up as a separate event type.
/// - The epic's "per-route" attribution (AC 2) requires a route-
///   resolver; for v1 we attach `route` from the injected resolver,
///   leaving per-route slicing to server-side group-by on the
///   dashboard side. If the resolver returns null the event is still
///   emitted with no route — cold-start jank is valuable even without
///   a route.
class FrameJankAggregator {
  FrameJankAggregator({
    required this.ingest,
    required this.currentRouteResolver,
    this.flushInterval = const Duration(minutes: 1),
    this.maxSamples = 10000,
    SchedulerBinding? schedulerBinding,
  }) : _binding = schedulerBinding;

  final ClientLatencyIngest ingest;
  final String? Function() currentRouteResolver;
  final Duration flushInterval;
  final int maxSamples;
  final SchedulerBinding? _binding;

  static const _budgetMicros = 16666;

  final List<_SpanSample> _buildSamples = [];
  final List<_SpanSample> _rasterSamples = [];

  TimingsCallback? _registeredCallback;
  Timer? _flushTimer;

  SchedulerBinding get _scheduler => _binding ?? SchedulerBinding.instance;

  /// Install the timings callback + periodic flusher. Idempotent —
  /// re-calling unregisters first.
  void start() {
    stop();
    _registeredCallback = _onTimings;
    _scheduler.addTimingsCallback(_registeredCallback!);
    _flushTimer = Timer.periodic(flushInterval, (_) => flush());
  }

  /// Remove the callback and cancel the periodic flush. Pending
  /// samples are preserved — the caller can flush before disposing.
  void stop() {
    final cb = _registeredCallback;
    if (cb != null) {
      _scheduler.removeTimingsCallback(cb);
      _registeredCallback = null;
    }
    _flushTimer?.cancel();
    _flushTimer = null;
  }

  /// Test hook — pump a batch of timings into the aggregator without
  /// touching the real SchedulerBinding.
  void ingestTimingsForTesting(List<FrameTiming> timings) {
    _onTimings(timings);
  }

  /// Aggregate + emit. No-op when the window is empty.
  void flush() {
    if (_buildSamples.isEmpty && _rasterSamples.isEmpty) return;
    final buildP95 = _p95(_buildSamples.map((s) => s.micros).toList());
    final rasterP95 = _p95(_rasterSamples.map((s) => s.micros).toList());
    final over = _buildSamples.where((s) => s.micros > _budgetMicros).length +
        _rasterSamples.where((s) => s.micros > _budgetMicros).length;
    final totalFrames =
        math.max(_buildSamples.length, _rasterSamples.length);
    final route = currentRouteResolver();
    ingest.enqueue(
      type: ClientLatencyType.frameJankP95,
      durationMs: (buildP95 / 1000).round(),
      route: route,
      extra: {
        'build_p95_ms': (buildP95 / 1000).round(),
        'raster_p95_ms': (rasterP95 / 1000).round(),
        'frames': totalFrames,
        'over_budget_frames': over,
      },
    );
    _buildSamples.clear();
    _rasterSamples.clear();
  }

  void _onTimings(List<FrameTiming> timings) {
    for (final t in timings) {
      _buildSamples.add(_SpanSample(t.buildDuration.inMicroseconds));
      _rasterSamples.add(_SpanSample(t.rasterDuration.inMicroseconds));
    }
    // Bounded memory — drop the oldest samples once the window
    // balloons past the hard cap.
    while (_buildSamples.length > maxSamples) {
      _buildSamples.removeAt(0);
    }
    while (_rasterSamples.length > maxSamples) {
      _rasterSamples.removeAt(0);
    }
  }

  static int _p95(List<int> values) {
    if (values.isEmpty) return 0;
    final sorted = [...values]..sort();
    final idx = ((sorted.length - 1) * 0.95).round();
    return sorted[idx];
  }
}

class _SpanSample {
  const _SpanSample(this.micros);
  final int micros;
}
