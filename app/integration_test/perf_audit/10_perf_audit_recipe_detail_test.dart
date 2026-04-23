/// Perf audit — Recipe detail cold-start budget.
///
/// Canonical flow:
///   1. User taps a recipe card.
///   2. recipeProvider(id) fetches the hydrated recipe.
///   3. Assert: exactly one GET /v1/recipes/:id.
///
/// `used_in_meals` + `cooking_history` are lazy tabs that only fetch
/// when the user taps their pane — excluded from the cold-start budget.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/providers/recipe_provider.dart';

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

  test('recipe detail cold-start fires exactly one GET /v1/recipes/:id',
      () async {
    await h.container.read(recipeProvider(fixtureRecipeId).future);

    // :id in the redacted endpoint name — the counter collapses the
    // fixture id via the token-ish heuristic (>=16 chars mixing letters
    // and digits), so the rollup is route-parameterized.
    expect(h.counts['GET /v1/recipes/:id'], 1);
    expect(h.counter.total, 1,
        reason: 'recipe detail fires 1 GET on cold start — '
            'version history + used-in-meals tabs lazy-load separately');

    h.emitCsv(screenName: 'recipe_detail');
  });

  test('recipe detail re-read within TTL is fully cached (zero network)',
      () async {
    await h.container.read(recipeProvider(fixtureRecipeId).future);
    final initialTotal = h.counter.total;

    await h.container.read(recipeProvider(fixtureRecipeId).future);

    expect(h.counter.total, initialTotal,
        reason: 're-read within the 5-min recipeCacheTtl must not fire a new GET');
  });
}
