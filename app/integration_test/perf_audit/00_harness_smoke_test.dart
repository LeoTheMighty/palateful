/// Smoke test for the perf-audit harness plumbing. Proves the mock
/// adapter + counting interceptor work end-to-end on an isolated Dio
/// without booting the full app. ptd-2's home test layers on top.
library;

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'harness.dart';

void main() {
  // Some harnesses invoke `flutter test` with the app/ directory as
  // CWD, others hand us the repo root. Try both; fall back to the
  // default the adapter uses (relative to CWD).
  String resolveFixtureDir() {
    final candidates = <String>[
      '${Directory.current.path}/../tools/perf-audit-fixtures',
      '${Directory.current.path}/tools/perf-audit-fixtures',
      defaultFixtureDir,
    ];
    for (final c in candidates) {
      if (Directory(c).existsSync()) return c;
    }
    return defaultFixtureDir;
  }

  Dio freshDio() => Dio(BaseOptions(baseUrl: 'http://mock.invalid'));

  test('mock adapter serves a committed fixture', () async {
    final dio = freshDio();
    final harness =
        installPerfAuditHarness(dio, fixtureDir: resolveFixtureDir());

    final response = await dio.get<Map<String, dynamic>>('/v1/users/me');

    expect(response.statusCode, 200);
    expect(response.data, isA<Map<String, dynamic>>());
    expect(response.data!['has_completed_onboarding'], true);
    expect(response.data!['default_recipe_book_id'], 'perf-audit-book-1');
    expect(harness.counter.total, 1);
  });

  test('mock adapter falls back to default empty list for missing GET', () async {
    final dio = freshDio();
    final harness =
        installPerfAuditHarness(dio, fixtureDir: resolveFixtureDir());

    // Pick an endpoint that definitely has no committed fixture so
    // the default-body fallback fires.
    final response = await dio.get('/v1/this-endpoint-never-has-a-fixture');

    expect(response.statusCode, 200);
    expect(response.data, isEmpty);
    expect(
      harness.counter.countsByEndpoint()[
          'GET /v1/this-endpoint-never-has-a-fixture'],
      1,
    );
  });

  test('counter redacts UUIDs and numeric ids to :id', () async {
    final dio = freshDio();
    final harness =
        installPerfAuditHarness(dio, fixtureDir: resolveFixtureDir());

    // Two detail fetches with different UUIDs + one with numeric id
    // should all roll into one budget entry.
    await dio.get('/v1/recipes/abcdef12-3456-7890-abcd-ef1234567890');
    await dio.get('/v1/recipes/deadbeef-1234-5678-90ab-cdef12345678');
    await dio.get('/v1/meals/42');

    expect(
      harness.counter.countsByEndpoint()['GET /v1/recipes/:id'],
      2,
      reason: 'both UUID detail fetches should roll into one budget entry',
    );
    expect(
      harness.counter.countsByEndpoint()['GET /v1/meals/:id'],
      1,
      reason: 'numeric id segment should redact to :id',
    );
  });

  test('counter.clear() resets observed requests', () async {
    final dio = freshDio();
    final harness =
        installPerfAuditHarness(dio, fixtureDir: resolveFixtureDir());

    await dio.get('/v1/users/me');
    expect(harness.counter.total, 1);

    harness.counter.clear();
    expect(harness.counter.total, 0);
    expect(harness.counter.countsByEndpoint(), isEmpty);
  });

  test('fixtureKeyFor slugifies method + path into a filesystem-safe key', () {
    expect(
      PerfAuditMockAdapter.fixtureKeyFor('GET', '/v1/users/me'),
      'GET_v1_users_me',
    );
    expect(
      PerfAuditMockAdapter.fixtureKeyFor('post', '/v1/recipes'),
      'POST_v1_recipes',
    );
    expect(
      PerfAuditMockAdapter.fixtureKeyFor('GET', '/v1/recipes/abc-1'),
      'GET_v1_recipes_abc-1',
    );
  });

  test('redactPath leaves stable segments intact', () {
    expect(
      PerfAuditRequestCounter.redactPath('/v1/recipe-books'),
      '/v1/recipe-books',
    );
    expect(
      PerfAuditRequestCounter.redactPath('/v1/users/me'),
      '/v1/users/me',
    );
    expect(
      PerfAuditRequestCounter.redactPath(
          '/v1/recipes/abcdef12-3456-7890-abcd-ef1234567890/steps'),
      '/v1/recipes/:id/steps',
    );
    expect(
      PerfAuditRequestCounter.redactPath('/v1/meals/100'),
      '/v1/meals/:id',
    );
  });
}
