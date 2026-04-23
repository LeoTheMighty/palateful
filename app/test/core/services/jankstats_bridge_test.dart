import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';

import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/jankstats_bridge.dart';
import 'package:palateful/core/services/perf_flags_service.dart';

class _CapturingIngest extends ClientLatencyIngest {
  _CapturingIngest()
      : super.withDio(
          dio: Dio(),
          flags: _ForcedOnFlags(),
          platform: ClientLatencyPlatform.android,
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

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  setUp(() {
    if (GetIt.I.isRegistered<ClientLatencyIngest>()) {
      GetIt.I.unregister<ClientLatencyIngest>();
    }
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  JankStatsBridge makeBridge() =>
      JankStatsBridge(channel: const EventChannel('com.palateful.jankstats'));

  test('skips when ClientLatencyIngest is not registered', () {
    final bridge = makeBridge();
    bridge.handleEventForTest(<Object?, Object?>{
      'jank_frame_count': 2,
      'total_frame_count': 100,
      'total_jank_duration_ms': 60,
      'max_jank_duration_ms': 42,
    });
    expect(GetIt.I.isRegistered<ClientLatencyIngest>(), isFalse);
  });

  test('maps a per-minute payload into jankstats_daily with jank-duration durationMs',
      () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest(<Object?, Object?>{
      'jank_frame_count': 3,
      'total_frame_count': 1800,
      'total_jank_duration_ms': 240,
      'max_jank_duration_ms': 110,
    });

    expect(ingest.captured, hasLength(1));
    final event = ingest.captured.single;
    expect(event['type'], ClientLatencyType.jankstatsDaily);
    expect(event['durationMs'], 240);
    final extra = event['extra'] as Map<String, dynamic>;
    expect(extra['jank_frame_count'], 3);
    expect(extra['total_frame_count'], 1800);
    expect(extra['total_jank_duration_ms'], 240);
    expect(extra['max_jank_duration_ms'], 110);
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

  test('durationMs defaults to 0 when total_jank_duration_ms is missing', () {
    final ingest = _CapturingIngest();
    GetIt.I.registerSingleton<ClientLatencyIngest>(ingest);
    final bridge = makeBridge();

    bridge.handleEventForTest(<Object?, Object?>{
      'jank_frame_count': 0,
      'total_frame_count': 3600,
    });

    expect(ingest.captured.single['durationMs'], 0);
  });

  test('start() is a no-op on non-Android platforms', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    final bridge = makeBridge();
    bridge.start();
    expect(() => bridge.dispose(), returnsNormally);
  });
}
