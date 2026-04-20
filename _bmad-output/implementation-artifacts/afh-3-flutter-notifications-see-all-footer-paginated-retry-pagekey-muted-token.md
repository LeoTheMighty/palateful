# Story afh-3: Flutter — Notifications See-all footer + paginated provider

Status: done

## Summary

Ships the Notifications tab's See-all footer symmetric to the existing
Imports See-all. Reads the afh-1a cursor-paginated `/v1/activities`
See-all mode + the afh-2 `/v1/activities/see-all-count` endpoint.
Rows render in muted typography via a new shared
`AppColors.mutedOnSurface(scheme)` token; pagination is
cursor-based with a retry-on-failure row; scroll offset persists across
tab switches via a `PageStorageKey` on the Notifications-tab outer
ListView. Swipe-right-to-unarchive is symmetric with the Imports
See-all (optimistic removal + 3s undo + error-path rollback).

## What shipped

- `app/lib/core/theme/app_colors.dart` — added
  `static Color mutedOnSurface(ColorScheme scheme)`. Centralises the
  0.65-alpha-on-onSurface token used by every muted history surface.
- `app/lib/features/activity/widgets/see_all_footer.dart` — swapped its
  `colorScheme.onSurface.withValues(alpha: 0.65)` call to the shared
  token (no raw `withOpacity(0.65)` left in this file).
- `app/lib/core/services/api_client.dart` — three new methods:
  - `listActivitiesSeeAll({cursor, limit=50})` — sends
    `include_archived=true&include_read=true&since_days=` (empty
    string is the afh-1a AC3 null sentinel).
  - `getActivitiesSeeAllCount()` — `/v1/activities/see-all-count`.
  - `getImportItemsSeeAllCount()` — `/v1/import-items/see-all-count`
    (for afh-4).
  - `listImportItemsSeeAll(jobId, {cursor, limit})` — cursor-paginated
    import-items (for afh-4).
- `app/lib/features/activity/providers/see_all_count_provider.dart` —
  NEW. Two notifiers (`NotificationsSeeAllCountNotifier`,
  `ImportsSeeAllCountNotifier`) backing
  `notificationsSeeAllCountProvider` + `importsSeeAllCountProvider`.
  Triple shape `{archived, other, total}` normalises the two backend
  endpoint keys (`read_and_older` vs `read_and_old_completed`).
  `refresh()` is the optimistic-update + tab-poll hook.
- `app/lib/features/activity/providers/notifications_see_all_provider.dart`
  — NEW. Paginated state (`items`, `nextCursor`, `hasLoadedFirstPage`,
  `isLoading`, `hasError`) + `loadNextPage()`, `removeRow(id)`,
  `restoreRow(row)`, `refreshFromTop()`. Separate
  `notificationsSeeAllExpandedProvider` (bool) survives tab switches
  per afh-3 AC10.a.
- `app/lib/features/activity/widgets/notifications_see_all_footer.dart`
  — NEW widget. Collapse toggle via the expansion provider; expanded
  body renders rows as Column children so the Notifications-tab outer
  ListView handles virtualization. Ancestor-scroll listener
  (`Scrollable.maybeOf(context).position`) fires `loadNextPage()` when
  within 200px of maxScrollExtent. Trailing widget is one of
  `CircularProgressIndicator` (next-page in flight), retry row
  ("Couldn't load more. Tap to retry.") on `hasError`, or
  "That's everything. (N total)" muted row on `isEnded`. Swipe-right
  uses `Dismissible` with `_restoreNonce` pattern; optimistic remove →
  POST unarchive → count refresh; failure path restores the row +
  error snackbar.
- `app/lib/features/activity/notifications_tab.dart` — mounts the new
  footer at the tail of the active-rows ListView AND in the
  empty-state ListView. Adds a `PageStorageKey('notifications-tab-list')`
  on the outer ListView (afh-3 AC10.b). Archive/undo flows call
  `notificationsSeeAllCountProvider.notifier.refresh()` so the footer
  label stays in sync.
- `app/test/features/activity/widgets/notifications_see_all_footer_test.dart`
  — NEW. 6 widget tests: count-0 renders nothing; expand loads page 1;
  scroll-to-end fires next page + end-of-list row; failed page shows
  retry row which retries; swipe-right unarchives; re-expand doesn't
  re-fetch.
- `app/test/features/activity/notifications_tab_test.dart` — fake
  extended to mock the two new endpoints so existing tests pass.
- `app/test/features/activity/activity_screen_test.dart` — same fake
  extensions.

## ACs satisfied

- AC1 — widget created, mirrors `SeeAllFooter` shape.
- AC2 — shared `AppColors.mutedOnSurface` token; both footers consume
  it (raw `withOpacity(0.65)` gone in Imports footer too).
- AC3 — label reads from `notificationsSeeAllCountProvider`; refreshed
  after archive/unarchive.
- AC4 — expanded list fetches via `listActivitiesSeeAll` with the
  empty-string `since_days=` null sentinel.
- AC5 — ancestor scroll listener detects within-200px-of-end; trailing
  spinner during fetch; "That's everything. (N total)" on end.
- AC6 — retry row replaces spinner on fetch failure; tap re-fires the
  same cursor.
- AC7 — `_onRowTap` navigates to `action_url` with `context.push`.
- AC8 — swipe-right unarchive with 3s undo snackbar (symmetric to
  Imports).
- AC9 — `total == 0` → `SizedBox.shrink`.
- AC10 — (a) expansion bool in a NotifierProvider; (b) PageStorageKey
  on the outer Notifications-tab ListView (scroll offset persistence).
- AC11 — virtualization is handled by the ancestor ListView.builder.
  Inner footer uses Column children rather than a nested ListView.
  afh-6 will add the 10k-row memory test.
- AC12/13 — widget tests cover count label, expand/load, end-of-list,
  retry-on-failure, swipe-right-unarchive, re-expand cache.
- AC14 — scroll persistence via PageStorageKey covered by the
  Notifications-tab's outer ListView.

## CI

- `flutter analyze lib/features/activity lib/core/theme lib/core/services` ✓
- `flutter test test/features/activity/` ✓ (110 tests passed;
  6 new tests for the footer).
