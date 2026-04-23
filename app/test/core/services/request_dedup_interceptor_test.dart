import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/request_dedup_interceptor.dart';

/// ffm-7 — RequestDedupInterceptor regression tests.
///
/// We assemble a real `Dio` with an in-memory HTTP adapter so we can
/// count upstream round-trips directly rather than mocking Dio's
/// private APIs. Each test installs the interceptor + a counting
/// adapter.

class _CountingAdapter implements HttpClientAdapter {
  int fetchCount = 0;
  Duration latency;
  bool throwNetworkError = false;

  _CountingAdapter({
    this.latency = const Duration(milliseconds: 20),
  });

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    fetchCount++;
    // Honor CancelToken-backed cancelFuture so the upstream really
    // aborts when all dedup subscribers bail.
    var cancelled = false;
    cancelFuture?.then((_) {
      cancelled = true;
    });
    await Future<void>.delayed(latency);
    if (cancelled) {
      throw DioException.requestCancelled(
        requestOptions: options,
        reason: 'test-cancelled',
      );
    }
    if (throwNetworkError) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'test-network-error',
      );
    }
    final str = '{"hit":$fetchCount,"path":"${options.path}"}';
    return ResponseBody.fromString(
      str,
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }
}

Dio _makeDio({
  required _CountingAdapter adapter,
  required RequestDedupInterceptor interceptor,
  String? authHeader,
}) {
  final dio = Dio(BaseOptions(
    baseUrl: 'http://example.test',
    headers: {
      if (authHeader != null) 'Authorization': authHeader,
      'Content-Type': 'application/json',
    },
  ));
  dio.httpClientAdapter = adapter;
  dio.interceptors.add(interceptor);
  return dio;
}

void main() {
  group('RequestDedupInterceptor — coalescing', () {
    test('two identical GETs in flight share one upstream round-trip',
        () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 50),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      final f1 = dio.get('/v1/recipe-books');
      final f2 = dio.get('/v1/recipe-books');
      final results = await Future.wait([f1, f2]);

      expect(adapter.fetchCount, 1,
          reason: 'identical in-flight GETs must coalesce');
      expect(results[0].data, equals(results[1].data));
    });

    test('micro-cache returns the cached response to callers arriving '
        'after completion (within 300ms window)', () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 15),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      await dio.get('/v1/recipe-books');
      // Wait less than 300ms so the micro-cache is still warm.
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await dio.get('/v1/recipe-books');
      expect(adapter.fetchCount, 1);
    });

    test('call arriving AFTER the 300ms micro-cache expires re-fetches',
        () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 10),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(
          microCacheWindow: const Duration(milliseconds: 50),
        ),
      );

      await dio.get('/v1/recipe-books');
      // Let micro-cache expire.
      await Future<void>.delayed(const Duration(milliseconds: 100));
      await dio.get('/v1/recipe-books');
      expect(adapter.fetchCount, 2);
    });

    test('different query params → separate round-trips', () async {
      final adapter = _CountingAdapter();
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      await Future.wait([
        dio.get('/v1/recipe-books', queryParameters: {'limit': 10}),
        dio.get('/v1/recipe-books', queryParameters: {'limit': 20}),
      ]);
      expect(adapter.fetchCount, 2);
    });

    test(
        'query params in different insertion order → SAME key '
        '(sorted normalization)', () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 30),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      final f1 = dio.get('/v1/items', queryParameters: {'a': 1, 'b': 2});
      final f2 = dio.get('/v1/items', queryParameters: {'b': 2, 'a': 1});
      await Future.wait([f1, f2]);
      expect(adapter.fetchCount, 1);
    });
  });

  group('RequestDedupInterceptor — auth isolation', () {
    test('auth-switch mid-session produces a different key', () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 30),
      );
      final interceptor = RequestDedupInterceptor();
      final dioUserA =
          _makeDio(adapter: adapter, interceptor: interceptor, authHeader: 'Bearer A');
      final dioUserB =
          _makeDio(adapter: adapter, interceptor: interceptor, authHeader: 'Bearer B');

      // Concurrent in-flight on the same PATH but different auth ->
      // two round-trips. User B must NOT see User A's response.
      await Future.wait([
        dioUserA.get('/v1/users/me'),
        dioUserB.get('/v1/users/me'),
      ]);
      expect(
        adapter.fetchCount,
        2,
        reason: 'different Authorization headers produce different keys '
            '— never coalesce across identities',
      );
    });
  });

  group('RequestDedupInterceptor — writes pass through', () {
    test('POST is never coalesced', () async {
      final adapter = _CountingAdapter();
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      await Future.wait([
        dio.post('/v1/recipe-books', data: {'name': 'A'}),
        dio.post('/v1/recipe-books', data: {'name': 'A'}),
      ]);
      expect(adapter.fetchCount, 2);
    });

    test('PUT, PATCH, DELETE all pass through', () async {
      final adapter = _CountingAdapter();
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      await Future.wait([
        dio.put('/v1/x', data: {}),
        dio.put('/v1/x', data: {}),
        dio.patch('/v1/y', data: {}),
        dio.patch('/v1/y', data: {}),
        dio.delete('/v1/z'),
        dio.delete('/v1/z'),
      ]);
      expect(adapter.fetchCount, 6);
    });
  });

  group('RequestDedupInterceptor — escape hatch', () {
    test(
        'Options(extra: {no_dedup: true}) bypasses the interceptor',
        () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 30),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      await Future.wait([
        dio.get(
          '/v1/client-latencies',
          options:
              Options(extra: {RequestDedupInterceptor.escapeHatchKey: true}),
        ),
        dio.get(
          '/v1/client-latencies',
          options:
              Options(extra: {RequestDedupInterceptor.escapeHatchKey: true}),
        ),
      ]);
      expect(adapter.fetchCount, 2);
    });
  });

  group('RequestDedupInterceptor — errors', () {
    test(
        'all coalesced callers see the same DioException when the '
        'upstream fails', () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 30),
      )..throwNetworkError = true;
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      Object? errA;
      Object? errB;
      final fA = () async {
        try {
          await dio.get('/v1/recipe-books');
        } catch (e) {
          errA = e;
        }
      }();
      final fB = () async {
        try {
          await dio.get('/v1/recipe-books');
        } catch (e) {
          errB = e;
        }
      }();
      await Future.wait([fA, fB]);

      expect(adapter.fetchCount, 1);
      expect(errA, isA<DioException>());
      expect(errB, isA<DioException>());
    });

    test('errors are NOT micro-cached (next call refetches)', () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 10),
      )..throwNetworkError = true;
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      try {
        await dio.get('/v1/x');
      } catch (_) {
        // expected
      }
      adapter.throwNetworkError = false;
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await dio.get('/v1/x');
      expect(adapter.fetchCount, 2);
    });
  });

  group('RequestDedupInterceptor — CancelToken handling', () {
    test(
        'secondary caller cancels → ONLY that caller rejects; '
        'first caller completes successfully',
        () async {
      final adapter = _CountingAdapter(
        latency: const Duration(milliseconds: 80),
      );
      final dio = _makeDio(
        adapter: adapter,
        interceptor: RequestDedupInterceptor(),
      );

      // Fire A first (the upstream owner), then B a tick later so
      // B is guaranteed to be the coalesced secondary caller.
      final tokenA = CancelToken();
      final fA = dio.get('/v1/recipe-books', cancelToken: tokenA);
      await Future<void>.delayed(const Duration(milliseconds: 5));
      final tokenB = CancelToken();
      Object? errB;
      Response<dynamic>? respB;
      final fB = () async {
        try {
          respB = await dio.get('/v1/recipe-books', cancelToken: tokenB);
        } catch (e) {
          errB = e;
        }
      }();
      await Future<void>.delayed(const Duration(milliseconds: 5));
      tokenB.cancel();

      final respA = await fA;
      await fB;
      expect(respA.statusCode, 200,
          reason: 'secondary cancel must not affect the upstream');
      expect(respB, isNull,
          reason: 'B observed cancel before resolution → no response');
      expect(errB, isA<DioException>());
      expect(adapter.fetchCount, 1);
    });
  });

  group('RequestDedupInterceptor — dedupKey', () {
    test('Authorization header is SHA256-hashed, not stored raw', () {
      final options = RequestOptions(
        path: '/v1/me',
        method: 'GET',
        headers: {'Authorization': 'Bearer very-long-jwt.with.sensitive.bits'},
      );
      final key = RequestDedupInterceptor.dedupKey(options);
      expect(
        key.contains('very-long-jwt'),
        isFalse,
        reason: 'raw token must not appear in the key',
      );
    });

    test('multi-value query param is sorted before joining', () {
      final a = RequestOptions(
        path: '/v1/x',
        method: 'GET',
        queryParameters: {
          'ids': ['c', 'a', 'b'],
        },
      );
      final b = RequestOptions(
        path: '/v1/x',
        method: 'GET',
        queryParameters: {
          'ids': ['b', 'c', 'a'],
        },
      );
      expect(
        RequestDedupInterceptor.dedupKey(a),
        equals(RequestDedupInterceptor.dedupKey(b)),
      );
    });
  });
}
