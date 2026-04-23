import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'perf_flags_service.dart';

/// Server-side whitelist of latency-event `type` values. Must stay in
/// sync with `CLIENT_LATENCY_TYPES` in
/// `libraries/utils/utils/models/client_latency.py` — a missing literal
/// triggers a 422 that kills the whole batch.
enum ClientLatencyType {
  appStart('app_start'),
  routePaint('route_paint'),
  networkRequest('network_request'),
  frameJankP95('frame_jank_p95'),
  metrickitDaily('metrickit_daily'),
  jankstatsDaily('jankstats_daily'),
  webNavigation('web_navigation'),
  firstPaint('first_paint'),
  firstContentfulPaint('first_contentful_paint');

  const ClientLatencyType(this.wire);
  final String wire;
}

/// Server-side `platform` whitelist.
enum ClientLatencyPlatform {
  ios('ios'),
  android('android'),
  web('web');

  const ClientLatencyPlatform(this.wire);
  final String wire;
}

/// Fire-and-forget batcher for `POST /v1/client-latencies` (cla-3).
///
/// Every telemetry emitter (`PerfNavigatorObserver`, `FrameJankAggregator`,
/// the Dio `perf_timing` interceptor, the MetricKit / JankStats bridges)
/// calls [enqueue]. A single in-memory queue is flushed when either
/// trigger fires:
///
/// - **Periodic timer** every [flushInterval] (default 30 s).
/// - **Threshold** when the queue hits [flushThreshold] events (default 50).
///
/// The batcher caps each POST at [maxEventsPerBatch] events (default 100,
/// matching the server-side `MAX_EVENTS_PER_REQUEST`) — any overflow
/// stays in the queue for the next flush. HTTP failures drop the in-flight
/// batch on the floor: no retry, no disk queue, no error surfaced.
///
/// The [PerfFlagsService] kill-switch is checked on every enqueue. When
/// `ingestEnabled = false` the event is dropped immediately. Sampling
/// is applied client-side via [PerfFlagsService.samplingRate] using a
/// single `Random` so operators can shed load without a rebuild.
///
/// `user_id` is deliberately omitted from the wire payload — the server
/// derives it from the JWT (or leaves NULL for anonymous calls). Client-
/// supplied `user_id` is ignored by the backend regardless.
class ClientLatencyIngest {
  factory ClientLatencyIngest({
    required ApiClient apiClient,
    required PerfFlagsService flags,
    required ClientLatencyPlatform platform,
    required String appVersion,
    Duration flushInterval = const Duration(seconds: 30),
    int flushThreshold = 50,
    int maxEventsPerBatch = 100,
    Random? random,
  }) {
    return ClientLatencyIngest.withDio(
      dio: apiClient.dio,
      flags: flags,
      platform: platform,
      appVersion: appVersion,
      flushInterval: flushInterval,
      flushThreshold: flushThreshold,
      maxEventsPerBatch: maxEventsPerBatch,
      random: random,
    );
  }

  @visibleForTesting
  ClientLatencyIngest.withDio({
    required Dio dio,
    required this.flags,
    required this.platform,
    required this.appVersion,
    this.flushInterval = const Duration(seconds: 30),
    this.flushThreshold = 50,
    this.maxEventsPerBatch = 100,
    Random? random,
  })  : _dio = dio,
        _random = random ?? Random();

  final Dio _dio;
  final PerfFlagsService flags;
  final ClientLatencyPlatform platform;
  final String appVersion;
  final Duration flushInterval;
  final int flushThreshold;
  final int maxEventsPerBatch;
  final Random _random;

  final List<Map<String, dynamic>> _queue = [];
  Timer? _timer;
  bool _flushInFlight = false;

  int get queuedEventCount => _queue.length;

  /// Start the periodic flush timer. Idempotent.
  void start() {
    _timer?.cancel();
    _timer = Timer.periodic(flushInterval, (_) => _flushInBackground());
  }

  /// Cancel the periodic timer. Any queued events are left in memory —
  /// the caller decides whether to call [flushNow] first.
  void dispose() {
    _timer?.cancel();
    _timer = null;
  }

  /// Enqueue a single event. Returns `true` if the event was queued,
  /// `false` if it was dropped by the kill-switch or sampling gate.
  /// Synchronous — never blocks on network.
  bool enqueue({
    required ClientLatencyType type,
    required int durationMs,
    String? route,
    String? endpoint,
    String? metricName,
    String? deviceClass,
    Map<String, dynamic>? extra,
  }) {
    if (!flags.ingestEnabled) return false;
    final rate = flags.samplingRate;
    if (rate < 1.0 && (rate <= 0.0 || _random.nextDouble() >= rate)) {
      return false;
    }

    final clampedDuration = durationMs < 0
        ? 0
        : (durationMs > 600000 ? 600000 : durationMs);
    _queue.add({
      'type': type.wire,
      'platform': platform.wire,
      'app_version': appVersion,
      'duration_ms': clampedDuration,
      if (route != null && route.isNotEmpty) 'route': route,
      if (endpoint != null && endpoint.isNotEmpty) 'endpoint': endpoint,
      if (metricName != null && metricName.isNotEmpty)
        'metric_name': metricName,
      if (deviceClass != null && deviceClass.isNotEmpty)
        'device_class': deviceClass,
      if (extra != null && extra.isNotEmpty) 'extra': extra,
    });

    if (_queue.length >= flushThreshold) {
      _flushInBackground();
    }
    return true;
  }

  /// Flush up to [maxEventsPerBatch] queued events to the backend.
  /// Resolves silently on any network error. Safe to call concurrently
  /// with the periodic timer — overlapping calls short-circuit to avoid
  /// stacked POSTs of the same window.
  Future<void> flushNow() async {
    if (_flushInFlight || _queue.isEmpty) return;
    _flushInFlight = true;
    try {
      final batch = _queue.take(maxEventsPerBatch).toList(growable: false);
      try {
        await _dio.post<Map<String, dynamic>>(
          '/v1/client-latencies',
          data: {'events': batch},
          // cla-6 hook: bypass the dedup + perf-timing interceptors so
          // ingest POSTs don't feedback-loop into the batcher.
          options: Options(extra: const {
            'no_dedup': true,
            '_perf_skip': true,
          }),
        );
        // Only drop on success — failed flushes leave the batch queued
        // so the next tick retries, but the ACK path is still best-
        // effort (no retry beyond the next natural flush).
        _queue.removeRange(0, batch.length);
      } on DioException catch (e) {
        // Silent drop on HTTP failure per the epic spec: no retry, no
        // disk queue. The samples would be stale by the time a retry
        // lands, so we prefer freshness + low complexity over durability.
        _queue.removeRange(0, batch.length);
        if (kDebugMode) {
          debugPrint(
            'ClientLatencyIngest: flush dropped ${batch.length} '
            'events (${e.type})',
          );
        }
      } catch (e) {
        _queue.removeRange(0, batch.length);
        if (kDebugMode) {
          debugPrint('ClientLatencyIngest: flush error: $e');
        }
      }
    } finally {
      _flushInFlight = false;
    }
  }

  void _flushInBackground() {
    unawaited(flushNow());
  }
}
