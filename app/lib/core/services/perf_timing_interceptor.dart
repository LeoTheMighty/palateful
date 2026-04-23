import 'package:dio/dio.dart';

import 'client_latency_ingest.dart';
import '../router/route_redaction.dart';

/// Dio interceptor that emits a `network_request` event per completed
/// call (cla-6).
///
/// **Pinned chain order** (see `api_client.dart`):
///
/// ```
/// [auth, dedup (ffm-7), firebase_httpMetric (cla-11), perf_timing (this)]
/// ```
///
/// `auth` runs first to inject the Authorization header; `dedup`
/// coalesces identical in-flight GETs so we don't double-count;
/// `firebase_httpMetric` wraps the actual wire call for Firebase
/// Performance Monitoring (slot reserved — fills in under cla-11);
/// `perf_timing` sits last so its stopwatch observes the real
/// wall-clock cost the user experienced.
///
/// **Feedback-loop skip.** Every `POST /v1/client-latencies` carries
/// `Options(extra: {'_perf_skip': true, 'no_dedup': true})`. Emitting a
/// `network_request` event for the ingest call itself would create an
/// infinite batch→flush→batch cycle — we short-circuit on `_perf_skip`
/// and never enqueue.
class PerfTimingInterceptor extends Interceptor {
  PerfTimingInterceptor({
    required ClientLatencyIngest? Function() ingestResolver,
  }) : _ingestResolver = ingestResolver;

  final ClientLatencyIngest? Function() _ingestResolver;

  /// Callers opt out by setting `Options(extra: {'_perf_skip': true})`.
  static const escapeHatchKey = '_perf_skip';
  static const _startKey = '_perf_t0_us';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (options.extra[escapeHatchKey] != true) {
      // Record the start wall-clock in microseconds. We avoid Stopwatch
      // in `extra` (Stopwatch is not trivially JSON-serializable) in
      // favor of a raw timestamp the response/error handler diffs.
      options.extra[_startKey] = DateTime.now().microsecondsSinceEpoch;
    }
    return handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    _emit(
      options: response.requestOptions,
      statusCode: response.statusCode ?? 0,
    );
    return handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _emit(
      options: err.requestOptions,
      statusCode: err.response?.statusCode ?? _statusForErrorType(err.type),
    );
    return handler.next(err);
  }

  void _emit({required RequestOptions options, required int statusCode}) {
    if (options.extra[escapeHatchKey] == true) return;
    final startMicros = options.extra[_startKey];
    if (startMicros is! int) return;
    final elapsedMicros =
        DateTime.now().microsecondsSinceEpoch - startMicros;
    final durationMs = (elapsedMicros / 1000).round();
    // Path is template-like for templated endpoints but callers can
    // pass concrete URLs; scrub just in case so raw UUIDs never leak.
    final endpoint = redactRoute(options.path) ?? options.path;
    final ingest = _ingestResolver();
    if (ingest == null) return;
    ingest.enqueue(
      type: ClientLatencyType.networkRequest,
      durationMs: durationMs,
      endpoint: endpoint,
      metricName: options.method,
      extra: {'status_code': statusCode},
    );
  }

  static int _statusForErrorType(DioExceptionType type) {
    switch (type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 408;
      case DioExceptionType.cancel:
        return 499;
      case DioExceptionType.connectionError:
        return 503;
      case DioExceptionType.badCertificate:
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        return 0;
    }
  }
}
