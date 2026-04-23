import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';

/// ffm-7 — Dio interceptor that coalesces identical in-flight GET
/// requests into a single upstream round-trip.
///
/// Also keeps the last successful response in a micro-cache for
/// [microCacheWindow] (default 300ms) so a second identical caller
/// arriving moments after the upstream completes doesn't re-fetch.
///
/// Out of scope:
/// - Writes (POST/PUT/PATCH/DELETE) always pass through.
/// - Callers passing `Options(extra: {'no_dedup': true})` opt out
///   (telemetry pipelines, admin tools).
///
/// CancelToken semantics:
/// - The FIRST caller's [CancelToken] drives the upstream fetch
///   (standard Dio behavior — the interceptor never swaps it out).
/// - A SECONDARY (coalesced) caller awaits the shared completer. If
///   that caller's token is cancelled, only THEIR Future rejects;
///   the upstream keeps running for the remaining subscribers.
/// - If the FIRST caller cancels, the upstream tears down and ALL
///   coalesced subscribers see the cancel. This is a recognized
///   trade-off for implementation simplicity — Dio's Future semantics
///   make it impossible to honor a first-caller cancel without also
///   cancelling the upstream.
///
/// Dedup key — `method + path + sorted-query + SHA256(Authorization)`.
/// Hashing the header (rather than parsing the JWT subject) avoids
/// pulling in a JWT decoder and still separates sessions correctly:
/// an auth-switch mid-session produces a different hash, so callers
/// on the new identity don't coalesce against the old identity's
/// in-flight or cached response.
class RequestDedupInterceptor extends Interceptor {
  RequestDedupInterceptor({
    this.microCacheWindow = const Duration(milliseconds: 300),
  });

  final Duration microCacheWindow;

  /// Callers escape dedup entirely by setting this flag in their
  /// `Options(extra: {...})`. Used by telemetry/admin callers where
  /// independent semantics matter.
  static const escapeHatchKey = 'no_dedup';

  /// Keys every active or recently-completed entry.
  final Map<String, _DedupEntry> _entries = {};

  // ─── Interceptor overrides ─────────────────────────────────────

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (options.extra[escapeHatchKey] == true) {
      return handler.next(options);
    }
    if (!_isDedupableMethod(options.method)) {
      return handler.next(options);
    }

    final key = dedupKey(options);
    final existing = _entries[key];

    if (existing != null) {
      // Join an ongoing upstream (in-flight OR micro-cached).
      existing.subscriberCount += 1;
      try {
        final upstream = await _awaitWithCallerCancel(existing, options);
        return handler.resolve(_cloneForCaller(upstream, options));
      } on DioException catch (e) {
        return handler.reject(e);
      } catch (e, st) {
        return handler.reject(
          DioException(
            requestOptions: options,
            error: e,
            stackTrace: st,
            type: DioExceptionType.unknown,
          ),
        );
      } finally {
        existing.subscriberCount -= 1;
      }
    }

    // First caller — create the entry and forward upstream. We do
    // NOT swap the caller's cancelToken (see class-doc tradeoff).
    // Dio drives the upstream with whatever token the caller passed;
    // if they cancel, the upstream tears down for everyone.
    final entry = _DedupEntry();
    entry.subscriberCount = 1;
    _entries[key] = entry;
    // If no secondary caller coalesces onto this entry, the
    // completer's result/error is never awaited. Mark the Future as
    // ignored so Dart's unhandled-async-error reporter doesn't fire
    // on the error path (happy path doesn't emit an error).
    entry.completer.future.ignore();
    return handler.next(options);
  }

  /// Wait for the shared completer, but race the caller's own
  /// [CancelToken] so a cancel on the secondary caller's side rejects
  /// ONLY that caller's Future without affecting the upstream.
  Future<Response> _awaitWithCallerCancel(
    _DedupEntry entry,
    RequestOptions options,
  ) {
    final cancelToken = options.cancelToken;
    if (cancelToken == null) {
      return entry.completer.future;
    }
    final cancelled = Completer<Response>();
    cancelToken.whenCancel.then((_) {
      if (!cancelled.isCompleted) {
        cancelled.completeError(
          DioException.requestCancelled(
            requestOptions: options,
            reason: cancelToken.cancelError?.error,
          ),
        );
      }
    });
    return Future.any([entry.completer.future, cancelled.future]);
  }

  @override
  void onResponse(
    Response response,
    ResponseInterceptorHandler handler,
  ) {
    final key = _entryKeyFor(response.requestOptions);
    final entry = key != null ? _entries[key] : null;
    if (entry != null && !entry.completer.isCompleted) {
      entry.completer.complete(response);
      _scheduleMicroCacheEviction(key!);
    }
    return handler.next(response);
  }

  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    final key = _entryKeyFor(err.requestOptions);
    final entry = key != null ? _entries[key] : null;
    if (entry != null && !entry.completer.isCompleted) {
      entry.completer.completeError(err);
      // Don't micro-cache errors — every retry should have a fresh
      // chance.
      _entries.remove(key);
    }
    return handler.next(err);
  }

  // ─── Internals ────────────────────────────────────────────────

  static bool _isDedupableMethod(String method) =>
      method.toUpperCase() == 'GET';

  /// Visible-for-testing: compute the dedup key for an options bag.
  static String dedupKey(RequestOptions options) {
    final sortedQuery = List<MapEntry<String, Object?>>.from(
      options.queryParameters.entries,
    )..sort((a, b) => a.key.compareTo(b.key));
    final queryStr = sortedQuery
        .map((e) => '${e.key}=${_stringifyQueryValue(e.value)}')
        .join('&');
    final auth = (options.headers['Authorization'] as Object?)?.toString() ?? '';
    final authDigest = sha256.convert(utf8.encode(auth)).toString();
    return '${options.method.toUpperCase()} ${options.path}?$queryStr #$authDigest';
  }

  static String _stringifyQueryValue(Object? value) {
    if (value is Iterable) {
      final list = value.map((v) => v.toString()).toList()..sort();
      return list.join(',');
    }
    return value?.toString() ?? '';
  }

  String? _entryKeyFor(RequestOptions options) {
    if (options.extra[escapeHatchKey] == true) return null;
    if (!_isDedupableMethod(options.method)) return null;
    final key = dedupKey(options);
    return _entries.containsKey(key) ? key : null;
  }

  void _scheduleMicroCacheEviction(String key) {
    if (microCacheWindow == Duration.zero) {
      _entries.remove(key);
      return;
    }
    Timer(microCacheWindow, () {
      _entries.remove(key);
    });
  }

  /// Clone the upstream response with the caller's own options so the
  /// caller's request-id / extra / path match their invocation.
  Response _cloneForCaller(Response upstream, RequestOptions callerOptions) {
    return Response(
      data: upstream.data,
      headers: upstream.headers,
      requestOptions: callerOptions,
      statusCode: upstream.statusCode,
      statusMessage: upstream.statusMessage,
      isRedirect: upstream.isRedirect,
      redirects: upstream.redirects,
      extra: Map<String, dynamic>.from(upstream.extra),
    );
  }

  /// Visible-for-testing: force-drop an entry (timers or completer
  /// survival in unit tests).
  void debugClear() {
    _entries.clear();
  }

  /// Visible-for-testing: snapshot of how many keyed entries are
  /// currently retained.
  int get debugActiveEntryCount => _entries.length;
}

class _DedupEntry {
  _DedupEntry();

  final Completer<Response> completer = Completer<Response>();
  int subscriberCount = 0;
}
