# rp-5 — Central failure-copy + grep guard + E2E sweep

**Status**: done
**Epic**: epic-reactive-migration-books-profile-pantry-and-polish

## What shipped

Closes AC rp-5 #1–#7. The `mutation_failure_copy.dart` map now has an
entry for every `MutationType` enum value across all four reactive
epics. A unit test enumerates `MutationType.values` and fails the
build if a new case lands without copy. An end-to-end sweep exercises
one mutation per feature through `showMutationFailureSnackbar` and
asserts the expected copy renders. A CI grep guard
(`tools/no-silent-catch-check.sh`) blocks any PR where a feature-
service catch block silently swallows an exception.

## Files

### New

- `app/test/core/state/mutation_failure_copy_test.dart` —
  enumeration + 320px-safe title length check + title format
  regression. Catches every new MutationType missing copy at CI.
- `app/test/core/state/mutation_failure_copy_e2e_test.dart` —
  7 representative mutations (recipes, books, profile, pantry,
  cooking log, shopping, imports) pumped through the central
  Snackbar helper; asserts `"Couldn't <verb> <noun>"` + Retry
  renders for each.
- `tools/no-silent-catch-check.sh` — CI grep guard. Portable
  POSIX-ish shell (no ripgrep, no bash-4 associative arrays). Scans
  every `app/lib/features/**/services/*.dart` catch block; requires
  `rethrow` / `throw` / `showMutationFailureSnackbar(` /
  `emitMutation(` / `ErrorReporter.report(` OR allowlist entry.
  Runtime: <1s across 13 service files.
- `tools/silent-catch-allowlist.txt` — 5 legitimate recovery paths:
  - `recipe_book_sync_service.dart:156` — malformed WS frame recovery.
  - `feedback_cache_service.dart:38/53/64` — SharedPreferences
    best-effort queue ops.
  - `session_alias_map.dart:101` — fall back to hardcoded seed.

### Modified

- `app/lib/core/state/mutation_failure_copy.dart` — full catalog of
  MutationType + copy entries for every epic's mutations.
- `.github/workflows/ci.yml` — new "No silent catches (rp-5 grep
  guard)" step between `flutter analyze` and `flutter test`.
- `CLAUDE.md` — "Key References" entry for
  `app/lib/core/state/README.md` and `tools/no-silent-catch-check.sh`.
- `app/test/features/profile/export_collection_test.dart` —
  registers `ProfileService` in the test harness (rp-2 refactor
  fallout); updates the failure-copy expectation to the new
  central Snackbar copy (`"Couldn't export recipes"`).

## QA walkthrough

### Regression (CI-guarded)

- [x] `mutation_failure_copy_test.dart` — enumeration green (every
  MutationType has a copy entry, every title ≤ 40 chars).
- [x] `mutation_failure_copy_e2e_test.dart` — 7 representative
  mutations all render expected copy + Retry.
- [x] `bash tools/no-silent-catch-check.sh` — scanned 13 service
  files, clean.
- [x] `flutter test test/features/profile/` — 41 tests green.
- [x] `flutter test test/features/recipe_books/` + pantry / recipes
  / shopping_cart / core — no regressions (329 tests across epic's
  touched areas; 4 pre-existing failures fixed).

### Manual dogfood (dogfood-proof step 6)

1. Any mutation failure (e.g. archive book + airplane mode).
   - [ ] Central Snackbar appears with `"Couldn't <verb> <noun>"`
     copy matching the verb/noun map.
   - [ ] Tap Retry → mutation re-invokes.
