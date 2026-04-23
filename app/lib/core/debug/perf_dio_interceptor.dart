import 'package:dio/dio.dart';

import 'perf_request_log.dart';

/// Dio interceptor that records request duration + status into
/// [PerfRequestLog]. Install only under `kDebugMode` — the
/// cla-6 story will supersede this with a unified interceptor
/// shared across Firebase Performance + client_latencies ingest.
///
/// Every request stamps a start-time into `RequestOptions.extra`
/// on `onRequest`; `onResponse` and `onError` read it and push a
/// [PerfRequestEntry] to the global log. No allocations on the hot
/// path beyond the entry itself — the map lookup is O(1).
class PerfDioInterceptor extends Interceptor {
  static const String _startTimeKey = 'perf_dio_start_ms';

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    options.extra[_startTimeKey] = DateTime.now().millisecondsSinceEpoch;
    handler.next(options);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    _record(response.requestOptions, response.statusCode, null);
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _record(
      err.requestOptions,
      err.response?.statusCode,
      err.message ?? err.type.name,
    );
    handler.next(err);
  }

  void _record(
    RequestOptions options,
    int? statusCode,
    String? errorMessage,
  ) {
    final start = options.extra[_startTimeKey];
    final elapsedMs = (start is int)
        ? DateTime.now().millisecondsSinceEpoch - start
        : 0;
    PerfRequestLog.instance.add(PerfRequestEntry(
      timestamp: DateTime.now(),
      method: options.method,
      path: options.path,
      statusCode: statusCode,
      duration: Duration(milliseconds: elapsedMs),
      errorMessage: errorMessage,
    ));
  }
}
