import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/frame_jank_aggregator.dart';
import 'package:palateful/core/services/perf_flags_service.dart';

class _StubAdapter implements HttpClientAdapter {
  final List<RequestOptions> requests = [];
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return ResponseBody.fromBytes(
      utf8.encode(jsonEncode({'success': true, 'data': {'accepted': 0}})),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _StaticFlags implements PerfFlagsService {
  @override
  bool ingestEnabled = true;
  @override
  double samplingRate = 1.0;
  @override
  Future<void> initialize() async {}
  @override
  void dispose() {}
}

ClientLatencyIngest _ingestFor(_StubAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = adapter;
  return ClientLatencyIngest.withDio(
    dio: dio,
    flags: _StaticFlags(),
    platform: ClientLatencyPlatform.ios,
    appVersion: '1.0.0+1',
    flushInterval: const Duration(days: 1),
    flushThreshold: 10000,
    random: Random(0),
  );
}

FrameTiming _fakeTiming({
  required int buildMicros,
  required int rasterMicros,
}) {
  // FrameTiming exposes buildDuration/rasterDuration computed from
  // raw vsync/build/raster timestamps. We seed timestamps that yield
  // the requested durations.
  return FrameTiming(
    vsyncStart: 0,
    buildStart: 0,
    buildFinish: buildMicros,
    rasterStart: buildMicros,
    rasterFinish: buildMicros + rasterMicros,
    rasterFinishWallTime: buildMicros + rasterMicros,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('flush is a no-op on an empty window', () {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => '/home',
    );
    jank.flush();
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('flush emits p95s computed across the window', () {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => '/home',
    );

    // 20 timings: 1..20 ms build, 1..20 ms raster — p95 is the 19th of 20.
    final samples = [
      for (var i = 1; i <= 20; i++)
        _fakeTiming(
          buildMicros: i * 1000,
          rasterMicros: (21 - i) * 1000,
        ),
    ];
    jank.ingestTimingsForTesting(samples);
    jank.flush();

    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('flush carries build + raster p95 + over-budget count in extra', () async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => '/home',
    );
    final samples = [
      _fakeTiming(buildMicros: 1000, rasterMicros: 1000),
      _fakeTiming(buildMicros: 2000, rasterMicros: 2000),
      _fakeTiming(buildMicros: 3000, rasterMicros: 3000),
      // Over 16.6ms budget:
      _fakeTiming(buildMicros: 30000, rasterMicros: 30000),
      _fakeTiming(buildMicros: 40000, rasterMicros: 40000),
    ];
    jank.ingestTimingsForTesting(samples);
    jank.flush();
    await ingest.flushNow();

    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['type'], 'frame_jank_p95');
    expect(event['route'], '/home');
    final extra = event['extra'] as Map<String, dynamic>;
    expect(extra['frames'], 5);
    expect(extra['over_budget_frames'], 4);
    expect(extra['build_p95_ms'], isNotNull);
    expect(extra['raster_p95_ms'], isNotNull);
    ingest.dispose();
  });

  test('flush clears the window so the next cycle starts fresh', () {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => '/home',
    );
    jank.ingestTimingsForTesting([
      _fakeTiming(buildMicros: 5000, rasterMicros: 5000),
    ]);
    jank.flush();
    expect(ingest.queuedEventCount, 1);

    // Second flush with no new samples → no event.
    jank.flush();
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('maxSamples caps the window', () {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => null,
      maxSamples: 5,
    );
    jank.ingestTimingsForTesting([
      for (var i = 1; i <= 20; i++)
        _fakeTiming(buildMicros: i * 1000, rasterMicros: i * 1000),
    ]);
    jank.flush();
    final body = ingest.queuedEventCount;
    expect(body, 1);
    ingest.dispose();
  });

  test('flush with null route omits the field', () async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final jank = FrameJankAggregator(
      ingest: ingest,
      currentRouteResolver: () => null,
    );
    jank.ingestTimingsForTesting([
      _fakeTiming(buildMicros: 5000, rasterMicros: 5000),
    ]);
    jank.flush();
    await ingest.flushNow();
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event.containsKey('route'), isFalse);
    ingest.dispose();
  });
}
