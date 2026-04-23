/// Perf audit — Home screen cold-start budget.
///
/// Canonical flow:
///   1. User lands on Home.
///   2. homeContentProvider fans out the data layer.
///   3. Assert: one GET per logical endpoint; no duplicates.
///
/// Scope divergence: the epic text says "cold start → render → tap
/// recipe card → back". We read the provider directly instead of
/// pumping the widget tree — see `ptd-2-perf-audit-home.md` for the
/// full rationale.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/home/providers/home_content_provider.dart';

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

  test('home cold-start fires the expected GETs without duplicates', () async {
    // Cold-start: one read of the screen's top-level provider.
    await h.container.read(homeContentProvider.future);

    // Exactly one hit per logical endpoint. Any duplicate here = budget
    // violation that ptd-4/ptd-5 would flag on CI.
    expect(h.counts['GET /v1/recipe-books'], 1,
        reason: 'recipe-books listed once for the home grid');
    expect(h.counts['GET /v1/favorites'], 1,
        reason: 'favorites fetched once for the favorites carousel');
    expect(h.counts['GET /v1/meals'], 1,
        reason: 'meals?scope=home fetched once for the grid');
    expect(h.counts['GET /v1/meal-events'], 1,
        reason: "today's meal-event fetched once for the banner");
    expect(h.counts['GET /v1/cooking-logs'], 1,
        reason: 'recently-cooked fetched once for the cooking-log row');

    // Total matches the sum of the five canonical GETs — any extra
    // fetch would show up here first.
    expect(h.counter.total, 5,
        reason: 'home should fire exactly 5 GETs on cold start');

    h.emitCsv(screenName: 'home');
  });

  test('home second read within TTL is fully cached (zero network)',
      () async {
    // ffm-6 guarantee: session-cache TTL on homeContentProvider = 5 min.
    // Within that window, a re-read against the same container should
    // return the cached value without firing any new GETs.
    await h.container.read(homeContentProvider.future);
    final initialTotal = h.counter.total;

    await h.container.read(homeContentProvider.future);

    expect(h.counter.total, initialTotal,
        reason: 're-read within TTL must not fire a single new GET');
  });
}
