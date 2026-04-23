/// Perf audit — Activity Hub (notifications tab) cold-start budget.
///
/// Canonical flow:
///   1. User taps the Activity tab.
///   2. activityTabProvider reads (no fetch — shell state only).
///   3. Notifications tab's `loadNextPage()` fires once to hydrate
///      the See-all paginator.
///   4. Assert: exactly one GET /v1/activities.
///
/// Imports tab + badge count providers are exercised by their own
/// tests / widgets and not part of the cold-start notifications
/// budget — they only fetch when their sub-widget renders.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/providers/notifications_see_all_provider.dart';
import 'package:palateful/features/activity/providers/activity_tab_provider.dart';

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

  test('activity shell read fires zero GETs (tab state only)', () async {
    // Tab provider is a pure state Notifier — reading it must not
    // trigger any network activity. Guarantees the shell doesn't
    // regress into speculative prefetches.
    h.container.read(activityTabProvider);
    expect(h.counter.total, 0,
        reason: 'activity shell tab-state read must be network-free');
  });

  test(
      'activity notifications cold-paginate fires exactly one GET /v1/activities',
      () async {
    // First page of the notifications see-all paginator.
    await h.container
        .read(notificationsSeeAllProvider.notifier)
        .loadNextPage();

    expect(h.counts['GET /v1/activities'], 1);
    expect(h.counter.total, 1,
        reason: 'first-page hydrate fires exactly 1 GET');

    h.emitCsv(screenName: 'activity_hub');
  });

  test('activity notifications second load at end-of-list is a no-op',
      () async {
    // After the first page returns with next_cursor: null (fixture
    // shape), a second loadNextPage() must short-circuit.
    final notifier = h.container.read(notificationsSeeAllProvider.notifier);
    await notifier.loadNextPage();
    final initialTotal = h.counter.total;

    await notifier.loadNextPage();

    expect(h.counter.total, initialTotal,
        reason: 'end-of-list short-circuit must not fire a new GET');
  });
}
