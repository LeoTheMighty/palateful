import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/perf_flags_service.dart';

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this._handler);

  final Future<ResponseBody> Function(RequestOptions) _handler;
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return _handler(options);
  }

  @override
  void close({bool force = false}) {}
}

class _StaticFlags implements PerfFlagsService {
  _StaticFlags({this.ingestEnabled = true, this.samplingRate = 1.0});

  @override
  bool ingestEnabled;
  @override
  double samplingRate;

  @override
  Future<void> initialize() async {}

  @override
  void dispose() {}
}

ResponseBody _okBody() => ResponseBody.fromBytes(
      utf8.encode(jsonEncode({'success': true, 'data': {'accepted': 0}})),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

Dio _dioWith(_StubAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = adapter;
  return dio;
}

ClientLatencyIngest _ingest({
  required _StubAdapter adapter,
  PerfFlagsService? flags,
  Duration flushInterval = const Duration(days: 1),
  int flushThreshold = 50,
  int maxEventsPerBatch = 100,
  Random? random,
}) {
  return ClientLatencyIngest.withDio(
    dio: _dioWith(adapter),
    flags: flags ?? _StaticFlags(),
    platform: ClientLatencyPlatform.ios,
    appVersion: '1.2.3+45',
    flushInterval: flushInterval,
    flushThreshold: flushThreshold,
    maxEventsPerBatch: maxEventsPerBatch,
    random: random,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('enqueue respects the kill-switch flag and drops events', () {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(
      adapter: adapter,
      flags: _StaticFlags(ingestEnabled: false),
    );
    final accepted = ingest.enqueue(
      type: ClientLatencyType.appStart,
      durationMs: 500,
    );
    expect(accepted, isFalse);
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('enqueue applies client-side sampling via the injected Random', () {
    // samplingRate = 0.25, Random always returns 0.5 → dropped.
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(
      adapter: adapter,
      flags: _StaticFlags(samplingRate: 0.25),
      random: _FixedRandom(0.5),
    );
    final accepted = ingest.enqueue(
      type: ClientLatencyType.routePaint,
      durationMs: 100,
      route: '/recipes/:id',
    );
    expect(accepted, isFalse);
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('enqueue passes through when sampling roll is under the rate', () {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(
      adapter: adapter,
      flags: _StaticFlags(samplingRate: 0.75),
      random: _FixedRandom(0.1),
    );
    final accepted = ingest.enqueue(
      type: ClientLatencyType.routePaint,
      durationMs: 100,
    );
    expect(accepted, isTrue);
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('threshold flush POSTs immediately on the 50th event', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(adapter: adapter, flushThreshold: 3);
    for (var i = 0; i < 3; i++) {
      ingest.enqueue(
        type: ClientLatencyType.routePaint,
        durationMs: 100 + i,
        route: '/home',
      );
    }
    // `_flushInBackground` schedules `flushNow()` via `unawaited`;
    // poll for queue drain instead of a bare 20ms sleep so slow CI
    // runners don't flake on microtask scheduling. GitHub Actions
    // Linux runners occasionally need >500 ms to drain the first
    // microtask chain (observed on CI run 24846026037), so budget
    // 2s — still fast on a laptop, survives CI oversubscription.
    for (var i = 0; i < 200; i++) {
      if (ingest.queuedEventCount == 0 && adapter.requests.isNotEmpty) {
        break;
      }
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    expect(adapter.requests, hasLength(1));
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('flushNow caps a single POST at maxEventsPerBatch', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(
      adapter: adapter,
      maxEventsPerBatch: 4,
    );
    for (var i = 0; i < 10; i++) {
      ingest.enqueue(
        type: ClientLatencyType.networkRequest,
        durationMs: 10 + i,
      );
    }
    await ingest.flushNow();
    expect(adapter.requests, hasLength(1));
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final events = body['events'] as List;
    expect(events.length, 4);
    expect(ingest.queuedEventCount, 6);
    ingest.dispose();
  });

  test('flushNow drops the batch silently on HTTP failure', () async {
    final adapter = _StubAdapter((_) async => ResponseBody.fromBytes(
          utf8.encode(jsonEncode({'error': 'boom'})),
          500,
        ));
    final ingest = _ingest(adapter: adapter);
    ingest.enqueue(
      type: ClientLatencyType.appStart,
      durationMs: 1500,
    );
    await ingest.flushNow();
    expect(adapter.requests, hasLength(1));
    // Event is dropped — no retry, no disk queue.
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('flushNow marks requests with no_dedup + _perf_skip', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(adapter: adapter);
    ingest.enqueue(
      type: ClientLatencyType.appStart,
      durationMs: 1500,
    );
    await ingest.flushNow();
    expect(adapter.requests, hasLength(1));
    final extras = adapter.requests.first.extra;
    expect(extras['no_dedup'], isTrue);
    expect(extras['_perf_skip'], isTrue);
    ingest.dispose();
  });

  test('wire payload strips empty-string optional fields', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(adapter: adapter);
    ingest.enqueue(
      type: ClientLatencyType.routePaint,
      durationMs: 180,
      route: '/home',
      endpoint: '',
      metricName: null,
    );
    await ingest.flushNow();
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['route'], '/home');
    expect(event.containsKey('endpoint'), isFalse,
        reason: 'empty-string endpoint is dropped');
    expect(event.containsKey('metric_name'), isFalse);
    ingest.dispose();
  });

  test('periodic flush ticks POST queued events', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(
      adapter: adapter,
      flushInterval: const Duration(milliseconds: 40),
    );
    ingest.start();
    ingest.enqueue(
      type: ClientLatencyType.appStart,
      durationMs: 1200,
    );
    await Future<void>.delayed(const Duration(milliseconds: 120));
    expect(adapter.requests.length, greaterThanOrEqualTo(1));
    final before = adapter.requests.length;
    ingest.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 120));
    expect(adapter.requests.length, before,
        reason: 'dispose cancels the periodic flush');
  });

  test('duration_ms clamped to [0, 10 minutes]', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(adapter: adapter);
    ingest.enqueue(type: ClientLatencyType.appStart, durationMs: -100);
    ingest.enqueue(
      type: ClientLatencyType.appStart,
      durationMs: 60 * 60 * 1000, // 1 hour — over cap
    );
    await ingest.flushNow();
    expect(adapter.requests, hasLength(1));
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final events = (body['events'] as List).cast<Map<String, dynamic>>();
    expect(events[0]['duration_ms'], 0);
    expect(events[1]['duration_ms'], 10 * 60 * 1000);
    ingest.dispose();
  });

  test('event payload carries type + platform + app_version + no user_id',
      () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _ingest(adapter: adapter);
    ingest.enqueue(
      type: ClientLatencyType.networkRequest,
      durationMs: 42,
      endpoint: '/v1/recipe-books',
    );
    await ingest.flushNow();
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['type'], 'network_request');
    expect(event['platform'], 'ios');
    expect(event['app_version'], '1.2.3+45');
    expect(event['endpoint'], '/v1/recipe-books');
    expect(event.containsKey('user_id'), isFalse);
    ingest.dispose();
  });
}

class _FixedRandom implements Random {
  _FixedRandom(this._next);
  final double _next;

  @override
  double nextDouble() => _next;

  @override
  bool nextBool() => false;

  @override
  int nextInt(int max) => 0;
}
