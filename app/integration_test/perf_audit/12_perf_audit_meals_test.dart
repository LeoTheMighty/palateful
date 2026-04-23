/// Perf audit — Meals screen cold-start budget.
///
/// Canonical flow:
///   1. User opens the Meals screen.
///   2. mealsAllProvider fetches the cross-book meal list.
///   3. Assert: exactly one GET /v1/meals.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/meals/providers/meals_provider.dart';

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

  test('meals cold-start fires exactly one GET /v1/meals', () async {
    await h.container.read(mealsAllProvider.future);

    expect(h.counts['GET /v1/meals'], 1);
    expect(h.counter.total, 1,
        reason: 'meals cold-start fires 1 GET — one flat list read');

    h.emitCsv(screenName: 'meals');
  });
}
