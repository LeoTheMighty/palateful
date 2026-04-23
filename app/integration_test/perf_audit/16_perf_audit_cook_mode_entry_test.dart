/// Perf audit — Cook mode entry cold-start budget.
///
/// Canonical flow:
///   1. User taps "Cook" on a recipe card.
///   2. CookModeScreen.initState fires two GETs:
///      - notification-preferences (decides whether to auto-enable OS
///        alerts on timer start)
///      - recipes/:id (hydrates the steps / ingredients UI)
///   3. Assert: exactly 2 GETs.
///
/// No FutureProvider — CookModeScreen is a ConsumerStatefulWidget that
/// fires the reads directly from initState. We exercise the equivalent
/// path via the harness's apiClient.
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

  const fixtureRecipeId = 'perf-audit-recipe-1';

  late PerfAuditScreenHarness h;

  setUp(() {
    h = setUpPerfAuditScreen(fixtureDir: resolveFixtureDir());
  });

  tearDown(() {
    h.dispose();
  });

  test('cook mode entry fires exactly 2 GETs on cold start', () async {
    // Parallel fires in the real screen — we pipe them through
    // Future.wait so any sequential-dependent regression doesn't
    // mask an extra request.
    await Future.wait([
      h.apiClient.getNotificationPreferences(),
      h.apiClient.getRecipe(fixtureRecipeId),
    ]);

    expect(
      h.counts['GET /v1/users/me/notification-preferences'],
      1,
      reason: 'notification preferences fetched once to gate OS alerts',
    );
    expect(
      h.counts['GET /v1/recipes/:id'],
      1,
      reason: 'recipe hydrated once for the cook-mode step UI',
    );
    expect(h.counter.total, 2,
        reason: 'cook mode entry fires exactly 2 GETs on cold start');

    h.emitCsv(screenName: 'cook_mode_entry');
  });
}
