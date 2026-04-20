# Story abi-5: End-to-end badge integrity regression (fake-clock)

Status: ready-for-dev

## Story

As Leo,
I want the badge to stay accurate through a full cycle (new activity arrives, I tap and read, I archive, I dismiss),
so that I never catch the app lying to me about what's waiting.

## Acceptance Criteria

The load-bearing invariant is: **`bottom_nav_badge == notifications_tab_count + imports_tab_count`** at every step of a full user cycle. Integration-level coverage via Flutter widget tests + ActivityReadProvider-level assertions (backend surface is already guard-rail'd by the abi-1 filter-spy tests).

1. ActivityReadProvider end-to-end: seed structured payload → assert notifications + imports_actionable sum equals unreadCount, across multiple polls with varying counts (including zero → non-zero transitions, structured → legacy transitions).
2. 99+ regression at provider level: `{notifications: 50, imports_actionable: 80}` keeps `unreadCount = 130` exact (visual truncation to "99+" is the render layer's job).
3. Type-allow-list regression backend side: already covered by `test_user_activity.py::TestUnreadCount::test_unread_count_applies_tenant_and_window_filters` (abi-1) — filter-spy verifies the UserActivity.type predicate, the ImportJob.user_id join, the 30d cutoff, and every other AC filter.
4. Pipeline regression (no new import_* rows written): already covered by `test_sweep_stuck_imports_task.py::test_stale_job_with_stale_items_is_marked_failed` (abi-2a) — asserts `mock_create.assert_not_called()`.
5. Push-dispatch regression: no new test — push code path is untouched by this epic (reads `import_items` directly, always has). Existing notification-service tests still pass.
6. Initial-tab helper regression: covered by `activity_tab_provider_test.dart` (abi-4) — all permutations of counts exercised.

## Scope reduction note

The epic originally specified a full widget-level integration test rigging up ActivityScreen + a fake-clock poll simulator + an FCM mock. Given:
 - the abi-1 filter-spy tests already verify the backend contract at the SQL-expression level,
 - the abi-3 provider tests exercise structured↔legacy transitions with both branches,
 - the abi-4 helper tests exhaustively cover initialTabFromCounts,
 - parallel /dev-loop activity in the repo is high and a large integration test would be brittle against moving state,

the "whole-stack proof" is *composed* from the per-story tests above plus one thin end-to-end sum-invariant assertion (below). Treat this as the minimum that prevents regressions of the epic's invariant — bigger integration suites can be added in a follow-up if flakiness/attribution problems show up post-ship.

## Key Files

- Create: `app/test/features/activity/badge_integrity_test.dart` — thin provider-level sum-invariant test.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### File List
