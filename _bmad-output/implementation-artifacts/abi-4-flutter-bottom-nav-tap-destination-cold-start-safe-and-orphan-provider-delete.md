# Story abi-4: Flutter — bottom-nav tap destination + orphan provider delete

Status: ready-for-dev

## Story

As Leo,
I want tapping the Activity tab to land me on whichever side has more to act on,
so that I'm not chasing down a number by switching tabs after I tap.

## Acceptance Criteria

1. New helper `initialTabFromCounts(int notifications, int importsActionable) → ActivityTab` in `activity_tab_provider.dart`: returns `ActivityTab.imports` if `importsActionable > notifications`, else `ActivityTab.notifications` (tie → Notifications).
2. `ActivityScreen` on `initState`:
   - If route has `?tab=` (wire value matches `ActivityTab.fromWire`), use it (current behavior).
   - Else call `initialTabFromCounts` with the latest `ActivityReadProvider.notificationsCount` / `.importsActionableCount`.
3. Cold-start (counts not yet resolved) → `initialTabFromCounts(0, 0)` returns Notifications (safe default). On the first post-frame callback, if counts have resolved AND the user hasn't manually swiped/tapped a tab yet, auto-switch.
4. Manual-override latch: `_userTouchedTab` flag on `_ActivityScreenState` flips true on any `_tabController` change or explicit tab provider set. Once latched, auto-switch is suppressed for the session.
5. Orphan `importsActionableBadgeProvider` is **DELETED** (file removed). Its one call site in `imports_tab.dart` is removed — the server-authoritative count on `ActivityReadProvider.importsActionableCount` supersedes it.
6. Widget test: pump ActivityScreen with `{notifications: 1, imports: 3}` and no `?tab=` → landed on Imports. Same test with `{3, 1}` → Notifications. Tie `{2, 2}` → Notifications.
7. Deep-link test: `?tab=notifications` wins even when imports > notifications.
8. Cold-start test: pump with counts (0, 0), then update to (1, 5) → auto-switches to Imports. Same scenario but user manually taps Notifications first → stays on Notifications.

## Key Files

- Modify: `app/lib/features/activity/providers/activity_tab_provider.dart` (add helper)
- Modify: `app/lib/features/activity/activity_screen.dart` (cold-start + manual-override)
- DELETE: `app/lib/features/activity/providers/imports_actionable_badge_provider.dart`
- Modify: `app/lib/features/activity/imports_tab.dart` (remove orphan set)
- Tests: `app/test/features/activity/providers/activity_tab_provider_test.dart` (new), `app/test/features/activity/activity_screen_test.dart` (extend)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### File List
