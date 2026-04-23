# Story ptd-2 — Perf audit harness skeleton + home test

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

ptd-2.5 landed the mock adapter + counter. ptd-2 adds the first concrete
per-screen perf-audit test — **Home** — plus the shared scaffolding
(`test_harness.dart`) every per-screen test under ptd-3a/ptd-3b will
reuse.

## Scope divergence from epic text

The epic says the test should drive "cold start → render → tap recipe
card → back" through the widget tree. In practice, **pumping the full
`HomeScreen` widget requires booting `app.main()`** — which calls
`Firebase.initializeApp()`, `dotenv.load()` from an asset, push-notif
init, Auth0 — none of which are safe on a headless `flutter-tester`
target. The next-cheapest alternative, wiring a partial
`ProviderScope + MaterialApp.router(routerConfig: appRouter)`, still
drags in Firebase + Auth0 via ancillary imports.

**Chosen scope:** read the screen's top-level provider directly via a
`ProviderContainer`. The perf budget's actual contract is *"how many
GETs does this screen's data layer fire on cold start?"* — which is
exactly what reading the provider once measures. UI taps don't add to
the cold-start budget; separate tests would be added if/when an
interaction path legitimately fires additional GETs.

This keeps each per-screen test <1s, hermetic, and independent of
Firebase / Auth0 / dotenv. The cost is that we don't catch
UI-interaction-time regressions — but `epic-perf-frontend-fetch-minimization`
(ffm-6 TTL cache, ffm-7 dedup) already makes those near-impossible.

The scope-divergence is documented in the test-harness file itself so
the next reader doesn't have to reconstruct the rationale.

## Implementation

### New files

- `app/integration_test/perf_audit/test_harness.dart` — shared
  per-screen scaffold. `setUpPerfAuditScreen()` registers a fresh
  `ApiClient` (with the mock adapter + counter from ptd-2.5) plus the
  service layer (`RecipeBookService`, `MealService`, `RecipeService`,
  `CookingLogService`) needed by Home + downstream per-screen tests.
  Seeds `dotenv` via `loadFromString` with placeholder values —
  `ApiClient`'s `BaseOptions` and `AuthService` both read `dotenv.env`,
  so an empty map throws. Leaves `AuthService` unregistered (no
  provider we care about reads it cold-start). Uses
  `getIt.allowReassignment = true` so repeat `setUp` calls replace
  cleanly without racing `getIt.reset()`'s async nature.

  `PerfAuditScreenHarness.emitCsv(screenName)` prints each observed
  endpoint in `PERF_AUDIT_CSV,<screen>,<endpoint>,<count>` format.
  ptd-4's `bin/perf-audit` will grep this sentinel off the test log
  to build the observed-budget snapshot.

- `app/integration_test/perf_audit/08_perf_audit_home_test.dart` — two
  tests:
  1. Cold-start fires exactly 5 GETs (recipe-books, favorites, meals,
     meal-events, cooking-logs), one each. Any duplicate = budget
     violation.
  2. Re-read within the 5-min TTL (ffm-6) fires zero new GETs. This
     pins the session cache's contract into the perf budget.

- Additional fixture files for the endpoints Home hits that need
  a non-default response shape:
  - `tools/perf-audit-fixtures/GET_v1_recipe-books.json`
  - `tools/perf-audit-fixtures/GET_v1_favorites.json`
  - `tools/perf-audit-fixtures/GET_v1_meals.json`
  - `tools/perf-audit-fixtures/GET_v1_meal-events.json`
  - `tools/perf-audit-fixtures/GET_v1_cooking-logs.json`
  Each ships `{items: []}` or equivalent empty-collection shape so
  the home providers complete their fan-out without throwing.

## Acceptance Criteria

- [x] (1) `perf_audit/harness.dart` (ptd-2.5) + `test_harness.dart`
  together provide an observing Dio interceptor shared across
  per-screen tests.
- [x] (2) Reuses ptd-2.5 harness primitives (`installPerfAuditHarness`,
  `PerfAuditRequestCounter`, `PerfAuditMockAdapter`). `helpers.dart`
  UI helpers are not needed at this scope — see scope-divergence.
- [x] (3) `08_perf_audit_home_test.dart` exercises the cold-start
  data-layer flow (read top-level provider once).
- [x] (4) CSV-style per-endpoint count emitted at test end via
  `emitCsv` — sentinel `PERF_AUDIT_CSV,<screen>,<endpoint>,<count>`
  grepped by `bin/perf-audit` (ptd-4).
- [x] (5) Passes locally: `flutter test
  integration_test/perf_audit/08_perf_audit_home_test.dart -d
  flutter-tester` — both tests green.
- [x] (6) Fails cleanly on extra GET: the first assertion
  (`expect(h.counts['GET /v1/recipe-books'], 1)`) flips to `2` if a
  duplicate ever lands, with a descriptive `reason:` — the exact
  failure ptd-5's CI guard is designed to catch.

## QA walkthrough

1. `cd app && flutter test integration_test/perf_audit/08_perf_audit_home_test.dart -d flutter-tester`
2. Both tests green, CSV emitted on stdout:
   ```
   PERF_AUDIT_CSV,home,GET /v1/cooking-logs,1
   PERF_AUDIT_CSV,home,GET /v1/favorites,1
   PERF_AUDIT_CSV,home,GET /v1/meal-events,1
   PERF_AUDIT_CSV,home,GET /v1/meals,1
   PERF_AUDIT_CSV,home,GET /v1/recipe-books,1
   ```
3. Confirm the smoke test (ptd-2.5) still passes independently:
   `flutter test integration_test/perf_audit/00_harness_smoke_test.dart -d flutter-tester`
4. Temporarily add a duplicate `api.getFavorites()` call to
   `home_content_provider.dart`, re-run: the home test fails with
   `expected 1, actual 2` on the favorites assertion.

## Non-goals (deferred)

- **Widget-tree pump.** Epic AC3 says "tap recipe card → back" — we
  skip UI-level assertions in favor of provider-level budget checks.
  If future features grow interaction-time GETs, add a second test
  under the same screen.
- **Full per-screen coverage.** Only Home lands here; ptd-3a/ptd-3b
  add the remaining eight screens using the same `test_harness.dart`.
- **Back-to-back `flutter test` in a single invocation.** The
  flutter-tester device has a race in its log reader that occasionally
  fails when two integration test files load sequentially. Running
  files individually works — `bin/perf-audit` (ptd-4) iterates files
  one at a time, which avoids this.

## File List

- `app/integration_test/perf_audit/test_harness.dart` (new)
- `app/integration_test/perf_audit/08_perf_audit_home_test.dart` (new)
- `tools/perf-audit-fixtures/GET_v1_recipe-books.json` (new)
- `tools/perf-audit-fixtures/GET_v1_favorites.json` (new)
- `tools/perf-audit-fixtures/GET_v1_meals.json` (new)
- `tools/perf-audit-fixtures/GET_v1_meal-events.json` (new)
- `tools/perf-audit-fixtures/GET_v1_cooking-logs.json` (new)
- `app/integration_test/perf_audit/00_harness_smoke_test.dart` (modified — switched the fallback test to a guaranteed-missing path so it passes after ptd-2 adds fixtures for `/v1/recipe-books`)
- `_bmad-output/implementation-artifacts/ptd-2-perf-audit-home.md` (new — this file)
