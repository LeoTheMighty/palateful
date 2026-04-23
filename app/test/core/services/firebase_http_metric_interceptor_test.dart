import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:firebase_performance/firebase_performance.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/core/services/firebase_http_metric_interceptor.dart';

/// Fake implementations that record calls instead of talking to Firebase.
/// The interceptor only touches `newHttpMetric`, so the fake performance
/// instance is minimal.
class _FakeHttpMetric implements HttpMetric {
  _FakeHttpMetric(this.url, this.method);

  final String url;
  final HttpMethod method;

  int startCalls = 0;
  int stopCalls = 0;
  int? _httpResponseCode;
  int? _requestPayloadSize;
  int? _responsePayloadSize;

  @override
  int? get httpResponseCode => _httpResponseCode;
  @override
  set httpResponseCode(int? value) => _httpResponseCode = value;

  @override
  int? get requestPayloadSize => _requestPayloadSize;
  @override
  set requestPayloadSize(int? value) => _requestPayloadSize = value;

  @override
  int? get responsePayloadSize => _responsePayloadSize;
  @override
  set responsePayloadSize(int? value) => _responsePayloadSize = value;

  @override
  String? get responseContentType => null;
  @override
  set responseContentType(String? value) {}

  @override
  Future<void> start() async {
    startCalls++;
  }

  @override
  Future<void> stop() async {
    stopCalls++;
  }

  @override
  void putAttribute(String name, String value) {}
  @override
  void removeAttribute(String name) {}
  @override
  String? getAttribute(String name) => null;
  @override
  Map<String, String> getAttributes() => const {};
}

class _FakePerformance implements FirebasePerformance {
  final List<_FakeHttpMetric> metrics = [];

  @override
  HttpMetric newHttpMetric(String url, HttpMethod method) {
    final metric = _FakeHttpMetric(url, method);
    metrics.add(metric);
    return metric;
  }

  @override
  Trace newTrace(String name) => throw UnimplementedError();

  @override
  Future<bool> isPerformanceCollectionEnabled() async => true;

  @override
  Future<void> setPerformanceCollectionEnabled(bool enabled) async {}

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _ThrowingPerformance implements FirebasePerformance {
  @override
  HttpMetric newHttpMetric(String url, HttpMethod method) {
    throw StateError('Firebase not initialized');
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Adapter that returns a fixed body for any request.
class _CannedAdapter implements HttpClientAdapter {
  _CannedAdapter({this.statusCode = 200});

  final int statusCode;
  final String body = '{}';

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final bytes = Uint8List.fromList(body.codeUnits);
    return ResponseBody.fromBytes(
      bytes,
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
        Headers.contentLengthHeader: ['${bytes.length}'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Dio _dioWith(FirebasePerformance performance, {int statusCode = 200}) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = _CannedAdapter(statusCode: statusCode);
  dio.interceptors.add(FirebaseHttpMetricInterceptor(performance: performance));
  return dio;
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  test('starts + stops a metric for a typical 200', () async {
    final perf = _FakePerformance();
    final dio = _dioWith(perf);
    await dio.get('/v1/health');

    expect(perf.metrics, hasLength(1));
    final m = perf.metrics.single;
    expect(m.startCalls, 1);
    expect(m.stopCalls, 1);
    expect(m.httpResponseCode, 200);
    expect(m.method, HttpMethod.Get);
  });

  test('records the response status on a 4xx error', () async {
    final perf = _FakePerformance();
    final dio = _dioWith(perf, statusCode: 404);

    try {
      await dio.get('/v1/missing');
    } on DioException catch (_) {
      // Expected — default validateStatus flags 4xx as an error.
    }

    expect(perf.metrics, hasLength(1));
    final m = perf.metrics.single;
    expect(m.startCalls, 1);
    expect(m.stopCalls, 1);
    expect(m.httpResponseCode, 404);
  });

  test('skips entirely when _perf_skip is set on the request', () async {
    final perf = _FakePerformance();
    final dio = _dioWith(perf);

    await dio.get(
      '/v1/client-latencies',
      options: Options(extra: {'_perf_skip': true}),
    );

    expect(perf.metrics, isEmpty);
  });

  test('degrades to pass-through when Firebase throws on newHttpMetric',
      () async {
    final perf = _ThrowingPerformance();
    final dio = _dioWith(perf);

    final response = await dio.get('/v1/health');
    expect(response.statusCode, 200);
    // No crash, no metric — the request completed normally.
  });

  test('POST maps to HttpMethod.Post', () async {
    final perf = _FakePerformance();
    final dio = _dioWith(perf);

    await dio.post('/v1/things', data: {'a': 1});
    expect(perf.metrics.single.method, HttpMethod.Post);
  });
}
