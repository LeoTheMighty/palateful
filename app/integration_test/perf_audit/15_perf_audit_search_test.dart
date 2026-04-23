/// Perf audit — Search screen cold-start budget.
///
/// Canonical flow:
///   1. User taps Search tab.
///   2. Screen renders with no query → zero GETs (cold invariant).
///   3. User types a query → one GET /v1/search.
///
/// Search has no FutureProvider — the `SearchScreen` StatefulWidget
/// calls `apiClient.search()` directly from its debounce handler. We
/// exercise the equivalent path via the harness's apiClient.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'test_harness.dart';

void main() {
  String resolveFixtureDir() {
    final candidates = <String>[
      '${Directory.current.path}/../tools/perf-audit-fixtures',
      '${Directory.current.path}/tools/perf-audit-fixtures',
    ];
    for (final c in candidates) {
      if (Directory(c).existsSync()) return c;
    }
    return '../tools/perf-audit-fixtures';
  }

  late PerfAuditScreenHarness h;

  setUp(() {
    h = setUpPerfAuditScreen(fixtureDir: resolveFixtureDir());
  });

  tearDown(() {
    h.dispose();
  });

  test('search cold-start with no query fires zero GETs', () async {
    // Screen paints an empty search field. No debounce fires. Any
    // regression that adds a prefetch-on-paint would trip this.
    expect(h.counter.total, 0,
        reason: 'search cold-start with no query must fire zero GETs');
  });

  test('search with a query fires exactly one GET /v1/search', () async {
    await h.apiClient.search('test query');

    expect(h.counts['GET /v1/search'], 1);
    expect(h.counter.total, 1,
        reason: 'single debounced query fires exactly 1 GET');

    h.emitCsv(screenName: 'search');
  });
}
