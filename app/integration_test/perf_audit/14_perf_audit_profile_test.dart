/// Perf audit — Profile tab cold-start budget.
///
/// Canonical flow:
///   1. User taps Profile tab.
///   2. profileProvider fetches the signed-in user blob.
///   3. Assert: exactly one GET /v1/users/me.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/profile/providers/profile_provider.dart';

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

  test('profile cold-start fires exactly one GET /v1/users/me', () async {
    await h.container.read(profileProvider.future);

    expect(h.counts['GET /v1/users/me'], 1);
    expect(h.counter.total, 1,
        reason: 'profile cold-start fires 1 GET — the user blob');

    h.emitCsv(screenName: 'profile');
  });

  test('profile re-read within TTL is fully cached (zero network)', () async {
    await h.container.read(profileProvider.future);
    final initialTotal = h.counter.total;

    await h.container.read(profileProvider.future);

    expect(h.counter.total, initialTotal,
        reason: 're-read within 10-min ffm-6 TTL must not fire a new GET');
  });
}
