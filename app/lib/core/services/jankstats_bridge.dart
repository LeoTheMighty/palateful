import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:get_it/get_it.dart';

import 'client_latency_ingest.dart';

/// cla-8: Dart side of the Android JankStats → `jankstats_daily` pipeline.
///
/// Subscribes to `com.palateful.jankstats` (an `EventChannel`, push from
/// native, lossy-OK). Each payload is a per-minute aggregate from the
/// Kotlin side and lands as a single `ClientLatencyIngest.enqueue` with
/// `type=jankstats_daily` and `extra=` the full mapped dict.
///
/// Release-build only — Kotlin `MainActivity` gates the bridge behind
/// `BuildConfig.DEBUG` so the EventChannel simply delivers no events in
/// dev builds. The Dart bridge can still start unconditionally on
/// Android without a second gate.
///
/// GetIt `isRegistered<ClientLatencyIngest>()` guard — kE2EMode skips
/// the ingest singleton, and a late first-minute flush can race the
/// bridge subscription on real devices too.
class JankStatsBridge {
  JankStatsBridge({
    EventChannel? channel,
    GetIt? locator,
  })  : _channel = channel ?? const EventChannel('com.palateful.jankstats'),
        _locator = locator ?? GetIt.I;

  final EventChannel _channel;
  final GetIt _locator;

  StreamSubscription<dynamic>? _subscription;

  /// Start listening. Idempotent; no-op on non-Android platforms.
  void start() {
    if (defaultTargetPlatform != TargetPlatform.android) return;
    _subscription?.cancel();
    _subscription = _channel.receiveBroadcastStream().listen(
      _handleEvent,
      onError: (Object e, StackTrace s) {
        if (kDebugMode) {
          debugPrint('JankStatsBridge stream error: $e');
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

    // Duration: total accumulated jank time in the window. A zero
    // duration still ships the event — the counters in `extra` are
    // the interesting data.
    final jankMs = _asInt(raw['total_jank_duration_ms']) ?? 0;

    final extra = <String, dynamic>{};
    for (final key in const [
      'jank_frame_count',
      'total_frame_count',
      'total_jank_duration_ms',
      'max_jank_duration_ms',
    ]) {
      final value = raw[key];
      if (value != null) {
        extra[key] = value;
      }
    }

    if (!_locator.isRegistered<ClientLatencyIngest>()) return;
    final ingest = _locator<ClientLatencyIngest>();
    ingest.enqueue(
      type: ClientLatencyType.jankstatsDaily,
      durationMs: jankMs,
      extra: extra.isEmpty ? null : extra,
    );
  }

  int? _asInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return null;
  }
}
