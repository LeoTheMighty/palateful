import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/debug/perf_dio_interceptor.dart';
import 'package:palateful/core/debug/perf_request_log.dart';

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this._status);

  final int _status;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final bytes = utf8.encode(jsonEncode({'ok': true}));
    return ResponseBody.fromBytes(
      bytes,
      _status,
      headers: {
        'content-type': ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _FailingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    throw DioException(
      requestOptions: options,
      type: DioExceptionType.connectionError,
      message: 'simulated network failure',
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  setUp(() => PerfRequestLog.instance.clear());

  test('onResponse pushes a 200 entry with non-null duration', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://example.test'))
      ..interceptors.add(PerfDioInterceptor())
      ..httpClientAdapter = _StubAdapter(200);

    await dio.get<dynamic>('/v1/ok');

    final entries = PerfRequestLog.instance.entries.value;
    expect(entries, hasLength(1));
    expect(entries.first.method, 'GET');
    expect(entries.first.path, '/v1/ok');
    expect(entries.first.statusCode, 200);
    expect(entries.first.errorMessage, isNull);
    expect(entries.first.duration.inMilliseconds, greaterThanOrEqualTo(0));
  });

  test('onResponse on 4xx status still records the status code', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://example.test'))
      ..interceptors.add(PerfDioInterceptor())
      ..httpClientAdapter = _StubAdapter(404);

    // Dio treats 4xx as an error by default; catch it.
    try {
      await dio.get<dynamic>('/v1/missing');
    } on DioException {
      // expected
    }

    final entries = PerfRequestLog.instance.entries.value;
    expect(entries, hasLength(1));
    expect(entries.first.statusCode, 404);
  });

  test('onError records an entry with errorMessage set', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://example.test'))
      ..interceptors.add(PerfDioInterceptor())
      ..httpClientAdapter = _FailingAdapter();

    try {
      await dio.get<dynamic>('/v1/boom');
    } on DioException {
      // expected
    }

    final entries = PerfRequestLog.instance.entries.value;
    expect(entries, hasLength(1));
    expect(entries.first.statusCode, isNull);
    expect(entries.first.errorMessage, isNotNull);
    expect(entries.first.path, '/v1/boom');
  });
}
