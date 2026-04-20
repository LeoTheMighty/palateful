# Story afh-4: Flutter — Imports See-all pagination swap

Status: done

## Summary

Refactors the Imports tab's See-all footer off the ahr-5-era one-shot
`limit=100` fetch onto the afh-1b cursor-paginated
`list_import_jobs` + per-job `list_import_items` pipeline. Count label
reads from `/v1/import-items/see-all-count` via
`importsSeeAllCountProvider` (sibling to the Notifications count
provider introduced in afh-3). Retry-on-failure row reused verbatim
from afh-3. Shares scroll persistence with `ImportsTab`'s outer
`PageStorageKey`.

## What shipped

- `app/lib/features/activity/providers/imports_see_all_provider.dart`
  — NEW. Paginated `SeeAllImportItemView` state keyed on a job-level
  cursor (`nextJobCursor`); each `loadNextPage` call fetches ~50
  archived jobs with cursor, then per-job items in parallel, flattens
  into the accumulated rows. Mirrors the
  `NotificationsSeeAllNotifier` shape.
- `app/lib/features/activity/widgets/see_all_footer.dart` — rewritten
  end-to-end. Now takes no parameters; subscribes to
  `importsSeeAllProvider` + `importsSeeAllCountProvider` +
  `importsSeeAllExpandedProvider`. Ancestor-scroll listener drives
  next-page fetch within 200px of maxScrollExtent. Retry row (`_RetryRow`)
  mirrors the afh-3 one. All `mutedColor` usages go through
  `AppColors.mutedOnSurface(scheme)` — no raw `withValues(alpha:0.65)`
  in this file.
- `app/lib/features/activity/imports_tab.dart` — drops
  `_seeAllCount`, `_completedOver30d`, `_loadSeeAllRows`,
  `_seeAllViewFromRaw`, and the tab-level archived-job count fetch.
  The See-all count is server-side now (refreshed after each poll and
  after archive/undo). `SeeAllFooter()` is mounted parameter-free in
  both the empty-state and non-empty branches. Outer `ListView` gains
  `PageStorageKey('imports-tab-list')` / `'imports-tab-empty-list'`
  for scroll persistence.
- `app/lib/core/services/api_client.dart` —
  `listImportJobs` now accepts `String? cursor` (the server param
  already exists via afh-1b). Dead-code `listImportItemsSeeAll`
  wrapper added in afh-3 removed — we page at the job level so the
  per-job list is the plain non-cursor call.
- `app/test/features/activity/widgets/see_all_footer_test.dart` —
  rewrote the whole suite against the new Riverpod-driven surface.
  5 tests: count=0 shrink, expand loads page 1, scroll triggers
  next-page cursor, retry-on-failure, swipe-right unarchive.
- Updated every `_FakeApiClient` in the activity + router test files
  to accept the new `cursor:` parameter on `listImportJobs` and mock
  the two new see-all-count endpoints:
  `imports_tab_test.dart`, `imports_tab_expansion_flow_test.dart`,
  `import_history_screen_test.dart`, `activity_screen_test.dart`,
  `core/router/import_history_redirect_test.dart`.

## ACs satisfied

- AC1 — hardcoded `limit=100` removed; paginated scroll controller via
  the same ancestor-scroll pattern as afh-3.
- AC2 — count via `importsSeeAllCountProvider` calling
  `/v1/import-items/see-all-count`; field names match afh-2 spec.
- AC3 — 50 jobs per page, cursor-based. Trailing progress indicator
  during fetch. "That's everything. (N total)" row at end. Retry row
  mirrors afh-3 AC6.
- AC4 — rows render as Column children under the ancestor ListView —
  no fixed `itemExtent`. Caret-expand-friendly.
- AC5 — swipe-right-to-unarchive preserved. Optimistic remove + 3s
  undo + count refresh on success.
- AC6 — `PageStorageKey('imports-tab-list')` on the outer ListView
  preserves scroll offset across tab switches.
- AC7 — `AppColors.mutedOnSurface(scheme)` consumed throughout; no
  raw `withOpacity(0.65)` in this file.
- AC8 — no ordering regression: ORDER BY is server-side (afh-1b)
  archived_at DESC NULLS LAST, created_at DESC, id DESC.
- AC9/10/11 — covered by the rewritten widget test suite.

## Scope deviation — documented

- **No cross-job item cursor.** The backend only paginates
  `list_import_items` at the per-job level, so the Imports See-all
  paginates at the JOB level (`listImportJobs(cursor=…, limit=50)`)
  and fetches items per job in parallel. A future refactor could
  introduce a global `GET /v1/import-items` endpoint for a true
  item-level cursor; for afh-4 the job-level cursor is good enough
  (50 jobs × ~1-3 items = bounded page sizes) and matches the
  existing data model.
- **>30d-completed non-archived items** are counted by the server's
  see-all-count endpoint but not rendered in this listing (they
  require a separate filter the job-level endpoint doesn't support).
  Practical impact: the footer label may read "See all (N)" while the
  expanded list shows N-k rows. Documented here; tracked for a
  follow-up if dogfood feedback surfaces it.

## CI

- `flutter analyze lib/features/activity lib/core/services lib/core/theme` ✓
- `flutter test test/features/activity/ test/core/router/` ✓ (115 passed).
