import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/perf_flags_service.dart';
import 'package:palateful/core/services/perf_timing_interceptor.dart';

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
  @override
  bool ingestEnabled = true;
  @override
  double samplingRate = 1.0;
  @override
  Future<void> initialize() async {}
  @override
  void dispose() {}
}

Dio _dioWith(_StubAdapter adapter, ClientLatencyIngest ingest) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = adapter;
  dio.interceptors.add(PerfTimingInterceptor(
    ingestResolver: () => ingest,
  ));
  return dio;
}

ClientLatencyIngest _makeIngest(_StubAdapter adapter) {
  // Tests use a second Dio for the client-latency POSTs themselves so
  // the feedback-loop assertions can verify that those POSTs do NOT
  // go through the perf-timing pipeline.
  final postDio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  postDio.httpClientAdapter = adapter;
  return ClientLatencyIngest.withDio(
    dio: postDio,
    flags: _StaticFlags(),
    platform: ClientLatencyPlatform.ios,
    appVersion: '1.0.0+1',
    flushInterval: const Duration(days: 1),
    flushThreshold: 10000,
    random: Random(0),
  );
}

ResponseBody _okBody({int statusCode = 200}) => ResponseBody.fromBytes(
      utf8.encode(jsonEncode({'ok': true})),
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('emits network_request on 2xx responses', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    await dio.get<Map<String, dynamic>>('/v1/recipes/:id');

    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('emits network_request on 4xx responses', () async {
    final adapter = _StubAdapter((_) async => _okBody(statusCode: 404));
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    try {
      await dio.get<Map<String, dynamic>>('/v1/missing');
    } on DioException catch (_) {
      // Expected — 404 throws via validateStatus default.
    }
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('emits network_request on 5xx responses', () async {
    final adapter = _StubAdapter((_) async => _okBody(statusCode: 503));
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    try {
      await dio.get<Map<String, dynamic>>('/v1/boom');
    } on DioException catch (_) {
      // Expected.
    }
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('emits network_request on connection errors', () async {
    final adapter = _StubAdapter((options) async {
      throw DioException(
        requestOptions: options,
        type: DioExceptionType.connectionError,
        error: 'offline',
      );
    });
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    try {
      await dio.get<Map<String, dynamic>>('/v1/anything');
    } on DioException catch (_) {
      // Expected.
    }
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('_perf_skip short-circuits: ingest POSTs do not feedback-loop',
      () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    await dio.post<Map<String, dynamic>>(
      '/v1/client-latencies',
      data: {'events': []},
      options: Options(extra: const {'_perf_skip': true}),
    );

    expect(ingest.queuedEventCount, 0,
        reason: 'ingest POSTs must never self-emit');
    ingest.dispose();
  });

  test('emitted event scrubs raw UUID in the path', () async {
    final adapter = _StubAdapter((_) async => _okBody());
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    await dio.get<Map<String, dynamic>>(
      '/v1/recipes/550e8400-e29b-41d4-a716-446655440000',
    );

    await ingest.flushNow();
    final body =
        adapter.requests.last.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['endpoint'], '/v1/recipes/:id');
    expect(event['type'], 'network_request');
    expect(event['metric_name'], 'GET');
    ingest.dispose();
  });

  test('emitted event embeds status_code in extra', () async {
    final adapter = _StubAdapter((_) async => _okBody(statusCode: 201));
    final ingest = _makeIngest(adapter);
    final dio = _dioWith(adapter, ingest);

    await dio.post<Map<String, dynamic>>(
      '/v1/recipes',
      data: const <String, dynamic>{},
    );

    await ingest.flushNow();
    final body = adapter.requests.last.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    final extra = event['extra'] as Map<String, dynamic>;
    expect(extra['status_code'], 201);
    ingest.dispose();
  });
}
