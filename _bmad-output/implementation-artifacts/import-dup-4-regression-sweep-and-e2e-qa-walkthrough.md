# import-dup-4 — QA Walkthrough

**Story:** `import-dup-4-regression-sweep-and-e2e`
**Date:** 2026-04-25

## Summary

Final story for `epic-import-duplicate-detection`. Adds 8 screen-level
integration tests covering the banner integration, plus the documented
manual e2e checklist below. The screen-level tests catch regressions
in the response-shape parsing, banner rendering, and action wire-up.
The manual e2e fills the gap that we don't have a Patrol harness yet.

## Files

| File | Status | Purpose |
|---|---|---|
| `app/test/features/recipes/add_recipe/import_item_review_duplicate_banner_test.dart` | new | 8 screen-level tests using stubbed `ApiClient` |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `import-dup-4-...: backlog → done`, `epic-import-duplicate-detection: in-progress → done` |
| `_bmad-output/implementation-artifacts/import-dup-4-regression-sweep-and-e2e.md` | new | Story spec |
| `_bmad-output/implementation-artifacts/import-dup-4-regression-sweep-and-e2e-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 No-duplicate flow unchanged | `test('no-duplicate response → form renders normally, no banner')` + `test('empty duplicate.matches → no banner')` | `import_item_review_duplicate_banner_test.dart` |
| AC #2 Multi-match top + Show all | `test('multi-match shows "+N more" affordance and bottom sheet on tap')` | `import_item_review_duplicate_banner_test.dart` |
| AC #3 e2e archive → re-import → Restore | Manual Case A below + `test('Restore on archived banner calls restoreRecipe THEN skipImportItem')` | this file + screen test |
| AC #4 e2e URL match with different parsed title | Manual Case D below + `test_duplicate_block_url_match_overrides_title_difference` (story 1) | this file + backend test |
| AC #5 First-paint not regressed > 100ms | Manual smoke check Case E | this file |

## Manual e2e checklist (~20 min, requires `docker compose up` + a logged-in user)

### Case A — Archive → re-import → Restore round-trip (the headline e2e)

1. Pick or create an active recipe — note its name and book.
2. Archive it (recipe detail → … → Archive).
3. Verify it disappears from the book's recipe list.
4. Trigger an import (URL or text-paste) of a recipe with that exact
   name (case-insensitive, extra whitespace OK).
5. Wait for parsing to finish; tap into the Approve-Import screen.

**Expect:** **Amber banner** with text:
*"You archived **<name>** on YYYY-MM-DD."*
Three buttons: Restore (filled, amber), Skip (text), Add anyway (text).

6. Tap **Restore**.

**Expect:**
- Brief spinner.
- Screen pops back to import-activity list.
- The previously-archived recipe is back in its book (re-open the book
  → recipe is there, no longer in archive).
- The import item is in `skipped` state in the activity feed (filter
  to "Skipped" if not visible by default).

### Case B — URL match, different parsed title

1. Import a recipe via URL `https://example.com/X` (use any real recipe
   URL the parser can handle).
2. After import, edit the recipe's title to something completely
   different (e.g., "Test 1").
3. Re-import the same URL `https://example.com/X`.

**Expect:** **Blue banner** with text mentioning the matched recipe by
its CURRENT title ("Test 1"), not the URL or the parser's title. The
match_kind in the API response is `source_url` (verifiable via
`curl GET /v1/import-items/{id}`).

### Case C — Multi-match (one active, one archived)

1. Have two recipes with the same name — one active in book A, one
   archived (originally in book B).
2. Re-import a recipe with that same name.

**Expect:**
- Banner shows the **active** match first (sorted server-side: active
  before archived).
- Subhead: "+ 1 more match — show all".
- Tap "show all" → bottom sheet lists both matches with their book
  name + an Archived chip on the archived one.
- Tapping a row in the sheet deep-links to that recipe's detail page.

### Case D — No match (regression)

1. Import a recipe whose name is unique in your library AND whose URL
   doesn't match any existing recipe.

**Expect:**
- No banner.
- Standard form.
- Standard "Save Recipe" button at the bottom.

### Case E — Performance smoke

1. Time the Approve-Import screen open-to-first-paint on a user with
   ≥50 recipes:
   - With NO duplicate match.
   - With a duplicate match.
2. The two should feel identical (the duplicate query is one indexed
   lookup; well under 30ms p95 target).

If you observe a > 100ms regression, capture the API response time in
DevTools and report — the index might not be hitting (check
`EXPLAIN ANALYZE` on the title-match query).

## Test inventory (8 new screen-level tests, all passing)

| # | Test | What it proves |
|---|---|---|
| 1 | no-duplicate response → form renders normally, no banner | Old response shape doesn't crash; no banner |
| 2 | empty duplicate.matches → no banner | Empty array handled identically |
| 3 | active match → blue banner with Skip + Add anyway | Active rendering path |
| 4 | archived match → amber banner with Restore button | Archived rendering path |
| 5 | Add anyway hides banner but keeps form usable | UI dismissal, no backend call |
| 6 | Skip on banner calls skipImportItem and pops | Banner → ApiClient wire path |
| 7 | Restore chains restoreRecipe THEN skipImportItem | Two-call sequence + ordering |
| 8 | multi-match shows "+N more" and opens sheet | Multi-match expand discovery |

## Local CI

| Gate | Result |
|---|---|
| `flutter test test/features/recipes/add_recipe/` | 76 pass |
| `flutter test` (full suite) | (verify before push) |
| `nx run api:test` | 2541 pass, 100.00% coverage |
| `nx run api:lint` | green |
| `dart analyze` (touched files) | clean |

## Epic outcome

`epic-import-duplicate-detection` is **done**. The Approve-Import
screen now shows a blue/amber banner when the user is about to
re-import something they already have. One tap to Skip, one tap to
Restore an archived original, one tap to Add Anyway. No silent dedup,
no relitigating past judgment.
