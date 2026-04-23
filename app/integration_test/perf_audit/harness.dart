/// Shared infra for the perf-audit integration test suite.
///
/// Installs:
///   1. A [PerfAuditMockAdapter] that serves canned responses from
///      `tools/perf-audit-fixtures/` — no network traffic.
///   2. A [PerfAuditRequestCounter] that records every attempted
///      request so per-screen tests can diff observed counts against
///      the committed budget in `tools/perf-budgets.yaml` (ptd-4).
///
/// Auth bypass rides the existing `kE2EMode` compile-time flag —
/// tests must be launched with `--dart-define=E2E_MODE=true`, which is
/// what `bin/perf-audit` will do once ptd-4 ships.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// Directory (relative to CWD when the test runs — almost always `app/`)
/// holding the committed fixtures.
const String defaultFixtureDir = '../tools/perf-audit-fixtures';

/// A single attempted request observed during a harness run. `path` is
/// already redacted — numeric ids and UUIDs are rewritten to `:id` so
/// a flow that hits `/v1/recipes/abc-...` and `/v1/recipes/def-...`
/// rolls into one budget entry.
@immutable
class PerfAuditRequest {
  const PerfAuditRequest({required this.method, required this.path});

  final String method;
  final String path;

  String get endpoint => '$method $path';

  @override
  String toString() => endpoint;
}

/// Dio [Interceptor] that records every attempted request. The counter
/// only cares about attempts — the budget is about what code *tried* to
/// do, not what the mock happened to serve. Budget rollups collapse
/// route params via [PerfAuditRequest.path]'s redaction.
class PerfAuditRequestCounter extends Interceptor {
  final List<PerfAuditRequest> _requests = [];

  List<PerfAuditRequest> get requests => List.unmodifiable(_requests);

  /// Rollup: `GET /v1/recipe-books` → count.
  Map<String, int> countsByEndpoint() {
    final m = <String, int>{};
    for (final r in _requests) {
      m[r.endpoint] = (m[r.endpoint] ?? 0) + 1;
    }
    return m;
  }

  int get total => _requests.length;

  void clear() => _requests.clear();

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    _requests.add(PerfAuditRequest(
      method: options.method.toUpperCase(),
      path: redactPath(options.path),
    ));
    handler.next(options);
  }

  /// Collapse `/v1/recipes/abc-1234-...` → `/v1/recipes/:id`. Heuristics:
  ///   - any segment that parses as an int,
  ///   - any segment that matches the leading bytes of a UUID,
  ///   - any segment ≥ 16 chars that mixes letters + digits (token-ish).
  /// Matches the shape `tools/perf-budgets.yaml` uses to list endpoints.
  @visibleForTesting
  static String redactPath(String path) {
    final segs = path.split('/');
    for (var i = 0; i < segs.length; i++) {
      if (_looksLikeIdentifier(segs[i])) segs[i] = ':id';
    }
    return segs.join('/');
  }

  static final _uuidPrefix = RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}');

  static bool _looksLikeIdentifier(String s) {
    if (s.isEmpty) return false;
    if (int.tryParse(s) != null) return true;
    if (_uuidPrefix.hasMatch(s)) return true;
    if (s.length >= 16 &&
        RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(s) &&
        RegExp(r'[A-Za-z]').hasMatch(s) &&
        RegExp(r'[0-9]').hasMatch(s)) {
      return true;
    }
    return false;
  }
}

/// Canned response shape read from a fixture JSON file. Two keys:
///
/// ```json
/// { "status": 200, "body": {...}|[...] }
/// ```
///
/// Missing keys default to `200` and an empty body.
@immutable
class _Fixture {
  const _Fixture({required this.status, required this.body});
  final int status;
  final Object? body;
}

/// Dio [HttpClientAdapter] that returns responses from a filesystem
/// fixtures directory. Never touches the network. Fixture files are
/// resolved by slugifying the request: `GET /v1/users/me` →
/// `GET_v1_users_me.json`. Missing fixtures fall back to a default
/// body so a test doesn't have to pre-capture every endpoint the app
/// happens to call.
class PerfAuditMockAdapter implements HttpClientAdapter {
  PerfAuditMockAdapter({String? fixtureDir})
      : fixtureDir = fixtureDir ?? defaultFixtureDir;

  final String fixtureDir;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    // Drain the request stream so callers don't deadlock on an
    // unconsumed body (applies to POST/PUT/PATCH only; GETs pass
    // null here).
    if (requestStream != null) {
      await requestStream.drain<Uint8List>();
    }
    final fixture = _loadFixture(options);
    final body = utf8.encode(jsonEncode(fixture.body));
    return ResponseBody.fromBytes(
      body,
      fixture.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  _Fixture _loadFixture(RequestOptions options) {
    final key = fixtureKeyFor(options.method, options.path);
    final file = File('$fixtureDir/$key.json');
    if (file.existsSync()) {
      try {
        final decoded =
            jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        return _Fixture(
          status: decoded['status'] as int? ?? 200,
          body: decoded.containsKey('body')
              ? decoded['body']
              : _defaultBody(options),
        );
      } catch (_) {
        // Malformed fixture — fall through to default rather than
        // masking the parse error with a mysterious test failure.
        // The test will assert on observed request counts, not body
        // shape, so a default body is survivable.
      }
    }
    return _Fixture(status: 200, body: _defaultBody(options));
  }

  /// Slugify `(method, path)` → a filesystem-safe key.
  ///
  /// Rules:
  ///   - Uppercase method.
  ///   - Leading `/` dropped.
  ///   - Remaining `/` → `_`.
  ///   - Any non-`[A-Za-z0-9_.-]` → `-`.
  ///
  /// Examples:
  ///   `GET /v1/users/me`        → `GET_v1_users_me`
  ///   `GET /v1/recipes/abc-1`   → `GET_v1_recipes_abc-1`
  ///   `POST /v1/recipes?foo=bar` → `POST_v1_recipes-foo-bar`
  @visibleForTesting
  static String fixtureKeyFor(String method, String path) {
    var key = '${method.toUpperCase()}_$path'
        .replaceFirst(RegExp(r'_/+'), '_')
        .replaceAll('/', '_')
        .replaceAll(RegExp(r'[^A-Za-z0-9_.-]'), '-');
    // Collapse runs of `-` for readability; harmless if already single.
    key = key.replaceAll(RegExp(r'-{2,}'), '-');
    return key;
  }

  /// Minimal body the JSON decoder will tolerate. Returning an empty
  /// list for GETs reduces "cannot subscript null" crashes in the
  /// callers; mutation verbs get `{}`.
  Object? _defaultBody(RequestOptions options) {
    if (options.method.toUpperCase() == 'GET') {
      return const <dynamic>[];
    }
    return const <String, dynamic>{};
  }
}

/// Convenience struct returned from [installPerfAuditHarness] so a test
/// can keep a direct reference to the counter without re-fetching from
/// the Dio's interceptor list.
@immutable
class PerfAuditHarness {
  const PerfAuditHarness({
    required this.counter,
    required this.adapter,
  });

  final PerfAuditRequestCounter counter;
  final PerfAuditMockAdapter adapter;
}

/// Install the mock adapter + counting interceptor on an existing
/// [Dio] instance. Intended for use after `app.main()` has finished
/// bootstrapping, pointed at `getIt<ApiClient>().dio`.
///
/// ```dart
/// final apiClient = getIt<ApiClient>();
/// final harness = installPerfAuditHarness(apiClient.dio);
/// // ...drive flow...
/// expect(harness.counter.countsByEndpoint()['GET /v1/recipe-books'], 1);
/// ```
PerfAuditHarness installPerfAuditHarness(
  Dio dio, {
  String? fixtureDir,
}) {
  final adapter = PerfAuditMockAdapter(fixtureDir: fixtureDir);
  final counter = PerfAuditRequestCounter();
  dio.httpClientAdapter = adapter;
  // Prepend so the counter sees every attempt before any retry /
  // refresh interceptors mutate the request options.
  dio.interceptors.insert(0, counter);
  return PerfAuditHarness(counter: counter, adapter: adapter);
}
