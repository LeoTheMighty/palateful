# Story ahr-2: Flutter — `ActivityScreen` two-tab shell + routing

**Status:** done
**Epic:** epic-activity-hub-redesign

## Goal
Replace the filter-chip/secret-redirect pattern on `/activity` with an
explicit two-tab shell (Notifications | Imports) on a single route.
This story ships the shell + routing rewrite only; the two tab bodies
are implemented in ahr-3 (Notifications) and ahr-4 (Imports).

## Scope (from epic)

- `ActivityTab` enum + `activityTabProvider` (`NotifierProvider` — Riverpod
  3.0-dev does not export `StateProvider`).
- `ActivityScreen` rewritten as `ConsumerStatefulWidget` with a `TabBar`
  + `TabBarView`. Controller ↔ provider sync both directions, guarded by
  `indexIsChanging` (swipe mid-animation) and a reentrancy flag.
- `?tab=<notifications|imports>` canonical deep-link; legacy
  `?filter=imports` rewritten to `?tab=imports` at the router level.
  When both are present, `tab` wins (router `redirect` callback returns
  early if `tab` is set).
- `/activity/import-history` nested route replaced with a router-level
  `redirect: → /activity?tab=imports` so stale in-app nav *and* cold-start
  push payloads resolve to the shell.
- Notifications tab body: preserves the existing chronological feed
  logic (moved into `_NotificationsTabBody` inside the shell file).
  `AutomaticKeepAliveClientMixin` keeps loaded state across tab swipes.
  Archive/swipe-to-archive wired in ahr-3.
- Imports tab body: temporarily renders the legacy
  `ImportHistoryScreen` in `embedded: true` mode (skips its own
  `Scaffold`/`AppBar` so the parent shell's app bar is the only chrome).
  ahr-4 replaces this with the color-sectioned layout.

## Contract decisions

- The old `/activity/import-history` widget file is NOT deleted yet
  (ahr-7 removes it). It gains an `embedded` flag used only by the new
  Imports tab body. The `Clear all failed` action hidden in embedded
  mode — ahr-4's richer layout folds that action into the per-section
  chrome.
- `activityTabProvider` is app-scoped (not `autoDispose`). Cold-start
  default is `ActivityTab.notifications`. The provider is seeded from
  the route's `?tab=` query param in `initState` via a post-frame
  callback so the first render matches the deep-link intent.
- The existing `activity_filter_chips.dart` + `ActivityFilter` enum
  are no longer used by the screen; deleting them is deferred to a
  follow-up clean-up so we don't fan out broken imports across a
  build.
- `@Deprecated` on `ImportHistoryScreen` is deferred to ahr-7 — placing
  it here cascades `deprecated_member_use_from_same_package` warnings
  across the class's own `State<ImportHistoryScreen>` generic, which
  hits a Flutter/Dart analyzer quirk that can't be cleanly suppressed
  from inside the same file.

## File List

- `app/lib/features/activity/providers/activity_tab_provider.dart` — new
- `app/lib/features/activity/activity_screen.dart` — major rewrite
- `app/lib/features/activity/import_history_screen.dart` — modified
  (added `embedded` flag; skip `Scaffold`/`AppBar` when embedded)
- `app/lib/core/router/app_router.dart` — modified (new
  `?tab=`/`?filter=` redirect; removed nested `/import-history` builder;
  import cleaned up)
- `app/test/features/activity/activity_screen_test.dart` — modified
  (Riverpod `ProviderScope`, new shell tests, `BatchParserService`
  registered for the embedded Imports tab body)

## Notes

- Flutter analyze on `activity/` + `core/router/` is clean except for
  two pre-existing warnings in `import_history_screen.dart`
  (`_errorDetail` unused + error_banner unused) that predate this
  story.
- All 26 tests in `test/features/activity/` pass.
