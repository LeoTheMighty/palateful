import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:get_it/get_it.dart';

import 'client_latency_ingest.dart';

/// cla-7: Dart side of the iOS MetricKit → `metrickit_daily` pipeline.
///
/// Subscribes to `com.palateful.metrickit` (an `EventChannel` — push from
/// native, lossy-OK, stream-semantic) and converts each payload into a
/// single [ClientLatencyIngest.enqueue] call with `type = metrickit_daily`
/// and the full payload in `extra`.
///
/// Release-build only (AppDelegate gates the Swift side with `#if !DEBUG`
/// so no events reach this bridge in dev — we don't need a second gate
/// here, but `start()` is still a no-op on non-iOS for hygiene).
///
/// `GetIt.I.isRegistered<ClientLatencyIngest>()` is checked on every
/// event — the ingest service isn't registered in kE2EMode (main.dart
/// guard), and the Swift buffer can deliver one late payload after
/// reaching the Dart side, so a missing registration must be a silent
/// no-op instead of a crash.
class MetricKitBridge {
  MetricKitBridge({
    EventChannel? channel,
    GetIt? locator,
  })  : _channel = channel ?? const EventChannel('com.palateful.metrickit'),
        _locator = locator ?? GetIt.I;

  final EventChannel _channel;
  final GetIt _locator;

  StreamSubscription<dynamic>? _subscription;

  /// Start listening. Idempotent; no-op on non-iOS platforms.
  void start() {
    if (defaultTargetPlatform != TargetPlatform.iOS) return;
    _subscription?.cancel();
    _subscription = _channel.receiveBroadcastStream().listen(
      _handleEvent,
      onError: (Object e, StackTrace s) {
        // Bridge errors are informational; we don't retry or surface to
        // the user. The ingest service is fire-and-forget by design.
        if (kDebugMode) {
          debugPrint('MetricKitBridge stream error: $e');
        }
      },
      cancelOnError: false,
    );
  }

  /// Cancel the subscription. Safe to call multiple times.
  Future<void> dispose() async {
    await _subscription?.cancel();
    _subscription = null;
  }

  @visibleForTesting
  void handleEventForTest(Object? event) => _handleEvent(event);

  void _handleEvent(Object? event) {
    if (event is! Map) return;
    final Map<Object?, Object?> raw = event.cast<Object?, Object?>();

    // Duration: cumulative CPU time over the MetricKit window (~24h).
    // Falls back to 0 if absent so the event still lands — the full
    // payload in `extra` carries the real data regardless.
    final cpuMs = _asInt(raw['cpu_time_ms']) ?? 0;

    final extra = <String, dynamic>{};
    for (final key in const [
      'launch_time_ms',
      'hang_time_ms',
      'scroll_hitch_ratio',
      'cpu_time_ms',
      'disk_write_kb',
      'cellular_upload_kb',
      'memory_peak_mb',
      'raw_payload',
      'payload_truncated',
      'payload_bytes',
    ]) {
      final value = raw[key];
      if (value != null) {
        extra[key] = value;
      }
    }

    if (!_locator.isRegistered<ClientLatencyIngest>()) return;
    final ingest = _locator<ClientLatencyIngest>();
    ingest.enqueue(
      type: ClientLatencyType.metrickitDaily,
      durationMs: cpuMs,
      extra: extra.isEmpty ? null : extra,
    );
  }

  int? _asInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return null;
  }
}
