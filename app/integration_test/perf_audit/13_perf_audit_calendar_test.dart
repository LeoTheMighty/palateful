/// Perf audit — Calendar screen cold-start budget.
///
/// Canonical flow:
///   1. User opens the Calendar tab.
///   2. `mealEventsByRangeProvider` fetches the currently-visible month.
///   3. Assert: exactly one GET /v1/meal-events.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/calendar/providers/meal_events_provider.dart';

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

  test('calendar cold-start fires exactly one GET /v1/meal-events', () async {
    final now = DateTime.now();
    final key = MealEventsRangeKey(
      start: DateTime(now.year, now.month, 1),
      end: DateTime(now.year, now.month + 1, 1),
    );

    await h.container.read(mealEventsByRangeProvider(key).future);

    expect(h.counts['GET /v1/meal-events'], 1);
    expect(h.counter.total, 1,
        reason: 'calendar visible range fires 1 GET on cold start');

    h.emitCsv(screenName: 'calendar');
  });
}
