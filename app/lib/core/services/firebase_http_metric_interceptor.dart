import 'package:dio/dio.dart';
import 'package:firebase_performance/firebase_performance.dart';

/// cla-11: Dio interceptor that mirrors every HTTP request into a
/// Firebase Performance `HttpMetric` so the Firebase console shows
/// app-observed network latency as a secondary source of truth.
///
/// Slots into the cla-6 pinned chain between `dedup` and `perf_timing`:
///
///   `[auth, dedup, firebase_http_metric, perf_timing]`
///
/// - Auth first — adds the Authorization header used by dedup key hashing.
/// - Dedup before firebase — a coalesced (not-actually-sent) request
///   shouldn't produce a Firebase trace.
/// - Firebase before perf_timing — Firebase wraps the wire-call; our own
///   `perf_timing` runs last so it measures real wall-clock including
///   any Firebase overhead.
///
/// Requests carrying `Options.extra['_perf_skip'] == true` bypass both
/// this interceptor and `perf_timing` (set by `ClientLatencyIngest` on
/// its own POSTs to avoid a feedback loop).
///
/// Defensive by design: if Firebase Performance is unavailable (web
/// build tree-shake fallout per AC3, uninitialized at call time, or
/// collection disabled by the operator at runtime) the interceptor
/// degrades to a pass-through rather than crashing the request. The
/// `metric` is stashed on `Options.extra['_fb_metric']` so `onResponse`
/// and `onError` can stop it; absence is treated as "no metric started,
/// nothing to stop."
class FirebaseHttpMetricInterceptor extends Interceptor {
  FirebaseHttpMetricInterceptor({FirebasePerformance? performance})
      : _performance = performance ?? FirebasePerformance.instance;

  final FirebasePerformance _performance;

  static const _extraKey = '_fb_metric';

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (options.extra['_perf_skip'] == true) {
      return handler.next(options);
    }
    try {
      final method = _mapMethod(options.method);
      if (method == null) return handler.next(options);
      final metric = _performance.newHttpMetric(options.uri.toString(), method);
      await metric.start();
      final reqLen = options.headers[Headers.contentLengthHeader];
      if (reqLen is String) {
        final parsed = int.tryParse(reqLen);
        if (parsed != null && parsed > 0) metric.requestPayloadSize = parsed;
      } else if (reqLen is int && reqLen > 0) {
        metric.requestPayloadSize = reqLen;
      }
      options.extra[_extraKey] = metric;
    } catch (_) {
      // Firebase unavailable / initialization race / web tree-shake —
      // pass through without a trace. Never fail the request.
    }
    handler.next(options);
  }

  @override
  Future<void> onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) async {
    await _stop(
      response.requestOptions,
      statusCode: response.statusCode,
      responseSize: _responseSize(response),
    );
    handler.next(response);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    await _stop(
      err.requestOptions,
      statusCode: err.response?.statusCode,
      responseSize: err.response == null ? null : _responseSize(err.response!),
    );
    handler.next(err);
  }

  Future<void> _stop(
    RequestOptions options, {
    int? statusCode,
    int? responseSize,
  }) async {
    final metric = options.extra[_extraKey];
    if (metric is! HttpMetric) return;
    try {
      if (statusCode != null) metric.httpResponseCode = statusCode;
      if (responseSize != null && responseSize > 0) {
        metric.responsePayloadSize = responseSize;
      }
      await metric.stop();
    } catch (_) {
      // Suppress — a failed stop() doesn't affect the user-visible
      // response and the metric is disposed by GC regardless.
    } finally {
      options.extra.remove(_extraKey);
    }
  }

  HttpMethod? _mapMethod(String method) {
    switch (method.toUpperCase()) {
      case 'GET':
        return HttpMethod.Get;
      case 'POST':
        return HttpMethod.Post;
      case 'PUT':
        return HttpMethod.Put;
      case 'DELETE':
        return HttpMethod.Delete;
      case 'PATCH':
        return HttpMethod.Patch;
      case 'HEAD':
        return HttpMethod.Head;
      case 'OPTIONS':
        return HttpMethod.Options;
      case 'TRACE':
        return HttpMethod.Trace;
      case 'CONNECT':
        return HttpMethod.Connect;
    }
    return null;
  }

  int? _responseSize(Response<dynamic> response) {
    final len = response.headers.value(Headers.contentLengthHeader);
    if (len == null) return null;
    return int.tryParse(len);
  }
}
