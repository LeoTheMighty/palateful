import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'api_client.dart';

/// Client-latency kill-switch reader (cla-1c).
///
/// Hits `GET /v1/flags/perf` on boot, caches the answer in memory for
/// 5 minutes, and re-fetches periodically so operator flips on ECS env
/// vars propagate without a client rebuild.
///
/// **Fail-open by design.** If the initial fetch errors or exceeds
/// [fetchTimeout] (default 500 ms), we treat the pipeline as on at
/// sampling 1.0 — the backend is the final authority on rate-limit
/// and shedding, so the client must not silence itself just because a
/// boot-time request was slow. Every telemetry emitter (`cla-3`'s
/// `ClientLatencyIngest.enqueue`, the Dio `perf_timing` interceptor,
/// the `PerfNavigatorObserver`) calls [ingestEnabled] immediately
/// before enqueueing.
class PerfFlagsService {
  PerfFlagsService(
    ApiClient apiClient, {
    Duration fetchTimeout = const Duration(milliseconds: 500),
    Duration refreshInterval = const Duration(minutes: 5),
  }) : this.withDio(
          apiClient.dio,
          fetchTimeout: fetchTimeout,
          refreshInterval: refreshInterval,
        );

  @visibleForTesting
  PerfFlagsService.withDio(
    this._dio, {
    Duration fetchTimeout = const Duration(milliseconds: 500),
    Duration refreshInterval = const Duration(minutes: 5),
  })  : _fetchTimeout = fetchTimeout,
        _refreshInterval = refreshInterval;

  final Dio _dio;
  final Duration _fetchTimeout;
  final Duration _refreshInterval;

  bool _ingestEnabled = true;
  double _samplingRate = 1.0;
  Timer? _refreshTimer;

  /// Whether the ingest pipeline is live. Defaults to `true` until the
  /// first successful fetch completes — fail-open contract.
  bool get ingestEnabled => _ingestEnabled;

  /// Fraction of events to keep before batching. `1.0` = no sampling.
  double get samplingRate => _samplingRate;

  /// One-shot boot fetch + schedule the 5-minute refresh loop. The
  /// future resolves within [_fetchTimeout] even if the endpoint
  /// stalls; on error/timeout we keep the default-on values and
  /// proceed. Safe to call before auth is resolved: the endpoint is
  /// unauthed.
  Future<void> initialize() async {
    await _fetch();
    _refreshTimer?.cancel();
    _refreshTimer = Timer.periodic(_refreshInterval, (_) => _fetch());
  }

  /// Stop the background refresh loop. Tests call this in `tearDown`
  /// so the pumped timer does not leak across cases.
  void dispose() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  Future<void> _fetch() async {
    try {
      final response = await _dio
          .get<Map<String, dynamic>>('/v1/flags/perf')
          .timeout(_fetchTimeout);
      final data = response.data;
      if (data == null) return;
      final enabled = data['ingest_enabled'];
      final rate = data['sampling_rate'];
      if (enabled is bool) {
        _ingestEnabled = enabled;
      }
      if (rate is num) {
        final parsed = rate.toDouble();
        if (parsed >= 0.0 && parsed <= 1.0) {
          _samplingRate = parsed;
        }
      }
    } on TimeoutException {
      // Fail-open: keep whatever we had (defaults on first call).
      if (kDebugMode) debugPrint('PerfFlagsService: fetch timed out');
    } on DioException catch (e) {
      if (kDebugMode) {
        debugPrint('PerfFlagsService: fetch failed (${e.type})');
      }
    } catch (e) {
      if (kDebugMode) debugPrint('PerfFlagsService: fetch error: $e');
    }
  }
}
