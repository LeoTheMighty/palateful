/// Perf audit — Books tab cold-start budget.
///
/// Canonical flow:
///   1. User taps Books tab.
///   2. recipeBooksProvider fetches the flat book list.
///   3. Assert: exactly one GET /v1/recipe-books.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipe_books/providers/recipe_books_provider.dart';

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

  test('books tab cold-start fires exactly one GET /v1/recipe-books',
      () async {
    await h.container.read(recipeBooksProvider.future);

    expect(h.counts['GET /v1/recipe-books'], 1);
    expect(h.counter.total, 1,
        reason: 'books tab should fire exactly 1 GET on cold start');

    h.emitCsv(screenName: 'books');
  });

  test('books re-read within TTL is fully cached (zero network)', () async {
    await h.container.read(recipeBooksProvider.future);
    final initialTotal = h.counter.total;

    await h.container.read(recipeBooksProvider.future);

    expect(h.counter.total, initialTotal,
        reason: 're-read within the 10-min TTL must not fire a new GET');
  });
}
