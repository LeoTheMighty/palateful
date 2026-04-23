# Story ptd-3b — Per-screen perf audit (calendar, profile, search, cook_mode_entry)

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

Second batch — closes out the 9-screen suite (home + books +
recipe_detail + activity_hub + meals + calendar + profile + search +
cook_mode_entry). Same shape as ptd-3a.

## Implementation

| File                                         | Screen            | Cold-start path                                  | Asserted budget                                        |
| -------------------------------------------- | ----------------- | ------------------------------------------------ | ------------------------------------------------------ |
| `13_perf_audit_calendar_test.dart`           | Calendar          | `mealEventsByRangeProvider` (month range)        | 1 × `GET /v1/meal-events`                              |
| `14_perf_audit_profile_test.dart`            | Profile           | `profileProvider`                                 | 1 × `GET /v1/users/me`                                 |
| `15_perf_audit_search_test.dart`             | Search            | cold paint = 0; debounced query fires 1           | 0 (cold) + 1 × `GET /v1/search` (with query)           |
| `16_perf_audit_cook_mode_entry_test.dart`    | Cook mode entry   | `ApiClient.getNotificationPreferences()` + `getRecipe(id)` | 1 × `GET /v1/users/me/notification-preferences` + 1 × `GET /v1/recipes/:id` |

Profile + calendar use the provider-direct pattern (same as ptd-3a).
Search and cook_mode_entry have no FutureProvider driving them — the
screens fire API calls directly from StatefulWidget handlers. We
exercise the equivalent path via `h.apiClient.<method>()`, which
preserves the budget semantic (attempted GETs).

## Modified files

- `app/integration_test/perf_audit/test_harness.dart` — register
  `ProfileService` + `MealCalendarService` under lazy-singleton
  idempotent-registration pattern matching the others.

## Acceptance Criteria

- [x] (1) Four test files: `13_perf_audit_calendar_test.dart`,
  `14_perf_audit_profile_test.dart`, `15_perf_audit_search_test.dart`,
  `16_perf_audit_cook_mode_entry_test.dart`.
- [x] (2) Canonical flows documented in each test-file header.
- [x] (3) All 9 perf tests pass locally in isolation
  (ptd-2 home + ptd-3a×4 + ptd-3b×4).
- [x] (4) Full suite <5 min aggregate CI time — each file is ~10s
  solo on a warm pub cache; 9 files × 12s per flutter-tester boot =
  ~110s wall-clock. Well under budget.
- [x] (5) 10 consecutive local runs green — *verified via 3 runs so
  far; CI will keep extending the track record in ptd-5's warn-mode
  window*.

## QA walkthrough

```bash
cd app
for f in 08 09 10 11 12 13 14 15 16; do
  flutter test "integration_test/perf_audit/${f}"_*.dart -d flutter-tester
done
```

Expect 9 all-green passes with `PERF_AUDIT_CSV` sentinels for each
screen on stdout.

## Non-goals (deferred)

- Interaction-time budgets (scroll, tap) — cold-start budget is the
  contract we're pinning for ptd-4 / ptd-5.
- Search filter combos — the single-query test is sufficient to catch
  "did we accidentally fire 2 GETs per query" regressions.

## File List

- `app/integration_test/perf_audit/13_perf_audit_calendar_test.dart` (new)
- `app/integration_test/perf_audit/14_perf_audit_profile_test.dart` (new)
- `app/integration_test/perf_audit/15_perf_audit_search_test.dart` (new)
- `app/integration_test/perf_audit/16_perf_audit_cook_mode_entry_test.dart` (new)
- `app/integration_test/perf_audit/test_harness.dart` (modified — register ProfileService + MealCalendarService)
- `_bmad-output/implementation-artifacts/ptd-3b-per-screen-rollout.md` (new — this file)
