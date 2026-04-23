import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';

import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/metrickit_bridge.dart';
import 'package:palateful/core/services/perf_flags_service.dart';

/// Captures every enqueue for inspection. Minimal — no flush, no
/// network — because the bridge is tested purely on its mapping logic.
class _CapturingIngest extends ClientLatencyIngest {
  _CapturingIngest()
      : super.withDio(
          dio: Dio(),
          flags: _ForcedOnFlags(),
          platform: ClientLatencyPlatform.ios,
          appVersion: '1.0.0+1',
        );

  final List<Map<String, Object?>> captured = [];

  @override
  bool enqueue({
    required ClientLatencyType type,
    required int durationMs,
    String? route,
    String? endpoint,
    String? metricName,
    String? deviceClass,
    Map<String, dynamic>? extra,
  }) {
    captured.add({
      'type': type,
      'durationMs': durationMs,
      'route': route,
      'endpoint': endpoint,
      'metricName': metricName,
      'deviceClass': deviceClass,
      'extra': extra,
    });
    return true;
  }
}

class _ForcedOnFlags implements PerfFlagsService {
  @override
  bool get ingestEnabled => true;

  @override
  double get samplingRate => 1.0;

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Wraps an EventChannel so tests can inject synthetic platform events
/// by invoking the real handler that Flutter's
/// `defaultBinaryMessenger.setMockStreamHandler`-style plumbing exposes
/// via `receiveBroadcastStream()`. We bypass the channel entirely and
/// drive `handleEventForTest` directly — more reliable than trying to
/// simulate the platform stream.
void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  setUp(() {
    if (GetIt.I.isRegistered<ClientLatencyIngest>()) {
      GetIt.I.unregister<ClientLatencyIngest>();
    }
    // Force the platform to iOS so `start()` would subscribe — even
    // though we don't call it in these tests.
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  MetricKitBridge makeBridge() =>
      MetricKitBridge(channel: const EventChannel('com.palateful.metrickit'));

  test('skips when ClientLatencyIngest is not registered (kE2EMode guard)',
      () {
    final bridge = makeBridge();
    // Non-null event payload; should be silently dropped because GetIt
    // doesn't have the ingest singleton.
    bridge.handleEventForTest(<Object?, Object?>{
      'cpu_time_ms': 12345,
    });
    // No registration, no throw.
    expect(GetIt.I.isRegistered<ClientLatencyIngest>(), isFalse);
  });

  test('maps a typical payload into metrickit_daily with cpu_time_ms duration',
      () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest(<Object?, Object?>{
      'launch_time_ms': 820,
      'hang_time_ms': 120,
      'scroll_hitch_ratio': 0.003,
      'cpu_time_ms': 154000,
      'disk_write_kb': 2048,
      'cellular_upload_kb': 560,
      'memory_peak_mb': 210,
      'raw_payload': {'a': 1, 'b': 'x'},
    });

    expect(ingest.captured, hasLength(1));
    final event = ingest.captured.single;
    expect(event['type'], ClientLatencyType.metrickitDaily);
    expect(event['durationMs'], 154000);
    expect(event['route'], isNull);
    final extra = event['extra'] as Map<String, dynamic>;
    expect(extra['launch_time_ms'], 820);
    expect(extra['hang_time_ms'], 120);
    expect(extra['scroll_hitch_ratio'], 0.003);
    expect(extra['cpu_time_ms'], 154000);
    expect(extra['disk_write_kb'], 2048);
    expect(extra['cellular_upload_kb'], 560);
    expect(extra['memory_peak_mb'], 210);
    expect(extra['raw_payload'], isA<Map>());
  });

  test('silently drops non-map payloads', () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest('not a map');
    bridge.handleEventForTest(42);
    bridge.handleEventForTest(null);

    expect(ingest.captured, isEmpty);
  });

  test('forwards payload_truncated flag when Swift side trims raw_payload',
      () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest(<Object?, Object?>{
      'cpu_time_ms': 8000,
      'payload_truncated': true,
      'payload_bytes': 1_250_000,
    });

    final extra = ingest.captured.single['extra'] as Map<String, dynamic>;
    expect(extra['payload_truncated'], isTrue);
    expect(extra['payload_bytes'], 1_250_000);
    expect(extra.containsKey('raw_payload'), isFalse);
  });

  test('durationMs defaults to 0 when cpu_time_ms is missing', () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest(<Object?, Object?>{'memory_peak_mb': 180});

    expect(ingest.captured.single['durationMs'], 0);
  });

  test('start() is a no-op on non-iOS platforms', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final bridge = makeBridge();
    bridge.start();
    // No exception, no subscription to teardown — just confirm dispose
    // returns without error.
    expect(() => bridge.dispose(), returnsNormally);
  });
}
