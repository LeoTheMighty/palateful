# Story ptd-3a — Per-screen perf audit (books, recipe_detail, activity_hub, meals)

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

First batch of 4 per-screen perf-audit tests built on the ptd-2
scaffold (`test_harness.dart` + mock Dio adapter + request counter).
Each test reads the screen's canonical top-level provider and asserts
the number of GETs that fire on cold start.

The same scope-divergence note applies as ptd-2: we read the provider
directly rather than pumping the widget tree, because full `app.main()`
boot isn't compatible with flutter-tester.

## Implementation

### New tests (one per screen)

| File                                      | Screen        | Cold-start provider                                  | Asserted budget                       |
| ----------------------------------------- | ------------- | ----------------------------------------------------- | ------------------------------------- |
| `09_perf_audit_books_test.dart`           | Books         | `recipeBooksProvider`                                 | 1 × `GET /v1/recipe-books`            |
| `10_perf_audit_recipe_detail_test.dart`   | Recipe detail | `recipeProvider(id)` (family)                         | 1 × `GET /v1/recipes/:id`             |
| `11_perf_audit_activity_hub_test.dart`    | Activity Hub  | `activityTabProvider` + `notificationsSeeAllProvider.loadNextPage()` | 0 (shell) then 1 × `GET /v1/activities` |
| `12_perf_audit_meals_test.dart`           | Meals         | `mealsAllProvider`                                    | 1 × `GET /v1/meals`                   |

Each test:
- Uses the shared `PerfAuditScreenHarness` from ptd-2.
- Emits the standard `PERF_AUDIT_CSV,<screen>,<endpoint>,<count>`
  sentinel so ptd-4's `bin/perf-audit` can parse the observed counts.
- Where the provider has a session-cache TTL (books: 10 min via ffm-6,
  recipe detail: 5 min), includes a "re-read within TTL fires zero new
  GETs" regression pin — catches accidental cache removal.

Activity Hub's test is slightly broader than the single-provider
pattern:
1. Reading the shell `activityTabProvider` (pure state) must fire
   zero GETs — catches any accidental speculative prefetch in the
   shell.
2. Notifications cold-paginate fires exactly 1 GET.
3. A second `loadNextPage()` at end-of-list short-circuits — pins the
   `nextCursor == null` guard so a regression that removes it gets a
   red build.

### New fixtures

- `tools/perf-audit-fixtures/GET_v1_activities.json` —
  `{items: [], next_cursor: null}` so the paginator short-circuits
  at end-of-list.
- `tools/perf-audit-fixtures/GET_v1_recipes_perf-audit-recipe-1.json`
  — the recipe-detail provider expects a `Map` response, and the
  default `[]` fallback crashes the cast. Fixture has the minimum
  shape (id, title, ingredients, steps).

### Modified files

- `app/integration_test/perf_audit/test_harness.dart` — register
  `AuthService` in `setUpPerfAuditScreen` (needed by `recipeProvider`
  which reads `getIt<AuthService>().isAdmin` to decide whether to
  pass `?debug=true`). `AuthService()` constructor only reads the
  dotenv placeholders we already seed, so no network at construction.

## Acceptance Criteria

- [x] (1) Four test files under `app/integration_test/perf_audit/`:
  `09_perf_audit_books_test.dart`, `10_perf_audit_recipe_detail_test.dart`,
  `11_perf_audit_activity_hub_test.dart`, `12_perf_audit_meals_test.dart`.
- [x] (2) Canonical flow documented in each test-file's header
  comment.
- [x] (3) All five tests (incl. ptd-2's home) pass locally in
  isolation with `flutter test integration_test/perf_audit/<file> -d
  flutter-tester`.
- [x] (4) Each runtime <30s (actual: ~10s each on a warm pub cache).
- [x] (5) No flaky tests — each has been run 3x in a row green.
  Note: back-to-back runs in a *single* `flutter test` invocation
  flake on flutter-tester's log reader (known limitation — ptd-4's
  `bin/perf-audit` iterates files individually).

## QA walkthrough

```bash
cd app
for f in 08 09 10 11 12; do
  flutter test "integration_test/perf_audit/${f}"_*.dart -d flutter-tester
done
```

All 5 files green. CSV sentinels printed:
```
PERF_AUDIT_CSV,home,GET /v1/recipe-books,1
PERF_AUDIT_CSV,books,GET /v1/recipe-books,1
PERF_AUDIT_CSV,recipe_detail,GET /v1/recipes/:id,1
PERF_AUDIT_CSV,activity_hub,GET /v1/activities,1
PERF_AUDIT_CSV,meals,GET /v1/meals,1
```

## Non-goals (deferred to ptd-3b / ptd-4 / ptd-5)

- Calendar, profile, search, cook_mode_entry tests (ptd-3b).
- Budget YAML + capture/assert `bin/perf-audit` wrapper (ptd-4).
- CI integration (ptd-5).
- Interaction-time perf (scroll, tap) — cold-start budget only.

## File List

- `app/integration_test/perf_audit/09_perf_audit_books_test.dart` (new)
- `app/integration_test/perf_audit/10_perf_audit_recipe_detail_test.dart` (new)
- `app/integration_test/perf_audit/11_perf_audit_activity_hub_test.dart` (new)
- `app/integration_test/perf_audit/12_perf_audit_meals_test.dart` (new)
- `tools/perf-audit-fixtures/GET_v1_activities.json` (new)
- `tools/perf-audit-fixtures/GET_v1_recipes_perf-audit-recipe-1.json` (new)
- `app/integration_test/perf_audit/test_harness.dart` (modified — register AuthService)
- `_bmad-output/implementation-artifacts/ptd-3a-per-screen-rollout.md` (new — this file)
