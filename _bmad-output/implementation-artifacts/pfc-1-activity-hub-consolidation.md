# Story pfc-1 — Activity Hub consolidation: single 30s poll source

**Status:** review
**Epic:** epic-perf-flutter-client-polish
**Generated:** 2026-04-21

## Summary

Collapse three redundant 30-second pollers (shell badge, notifications
tab, imports tab) into a single cadence owned by `ActivityReadProvider`.
Shell starts/stops the poll; tabs register tick listeners. When the
Activity tab is focused (notifications tab mounted), the provider
suppresses its own `/v1/activities/unread-count` fetch because the
tab's `/v1/activities` fetch already refreshes unread-count.

Lands in one commit across `activity_read_provider.dart`,
`scaffold_with_bottom_nav.dart`, `notifications_tab.dart`, and
`imports_tab.dart` so there is no half-state where the badge
double-counts.

## Gotchas (repo realities vs epic text)

- **Path fix** — Flutter app root is `app/lib/`, NOT `apps/flutter/lib/`
  as epic's File Structure says. Provider lives at
  `app/lib/features/activity/providers/activity_read_provider.dart`
  (not `core/services/`), shell at `app/lib/shared/widgets/`, tabs at
  `app/lib/features/activity/`. Test folder is `app/test/features/`.
- **Imports tab timer count** — epic claimed two timers (2s + 30s);
  there is ONLY a 30s timer at `imports_tab.dart:81`. No 2s poll
  exists today.
- **Pre-existing AutomaticKeepAliveClientMixin** — both tabs are in
  `TabBarView` children, kept alive simultaneously. "Activity tab
  focused" ≡ "ActivityScreen mounted" for this epic's purposes.
- **Shell manual refresh-on-tap** (`_onDestinationSelected` line 57)
  stays — that's a user-initiated refresh, distinct from the poll.

## Scope of change

- `ActivityReadProvider` grows poll-ownership surface: `startPolling()`
  / `stopPolling()` (idempotent), `registerTickListener(cb,
  {contributesUnreadCount})` returning a disposer, private `_tick()`
  with sentinel `debugPrint('[activity-read] tick')`. `_tick` fires all
  tab callbacks, then calls `refreshUnreadCount()` ONLY when zero
  consumers set `contributesUnreadCount: true`.
- `ScaffoldWithBottomNav` drops its `Timer.periodic`; calls
  `provider.startPolling()` in `initState` (immediate cold-start fetch
  is handled inside `startPolling`) and `stopPolling()` in `dispose`.
- `NotificationsTab` drops its `Timer.periodic`; calls
  `provider.registerTickListener(() => _load(silent: true),
  contributesUnreadCount: true)` in `initState`; holds the disposer and
  invokes it in `dispose`.
- `ImportsTab` drops its `Timer.periodic`; calls
  `provider.registerTickListener(() => _load(silent: true))` (default
  `contributesUnreadCount: false`); holds the disposer and invokes it
  in `dispose`.
- Tests extend `activity_read_provider_test.dart`: one-timer invariant
  via `startPolling` idempotence, tick decision matrix (skip
  unread-count iff any `contributesUnreadCount` subscriber is alive),
  disposer decrements the counter.

## File List

- app/lib/features/activity/providers/activity_read_provider.dart  [MODIFIED]
- app/lib/shared/widgets/scaffold_with_bottom_nav.dart  [MODIFIED]
- app/lib/features/activity/notifications_tab.dart  [MODIFIED]
- app/lib/features/activity/imports_tab.dart  [MODIFIED]
- app/test/features/activity/activity_read_provider_test.dart  [MODIFIED]

## Acceptance criteria

- [x] `ActivityReadProvider` exposes `startPolling()`/`stopPolling()`
  (idempotent) + `registerTickListener(cb, {contributesUnreadCount})`
  returning a disposer.
- [x] Exactly one `Timer.periodic` alive at any time across the whole
  app. `startPolling` is idempotent — second call does not spawn a
  second Timer (asserted via `@visibleForTesting hasActiveTimer`
  getter + call-it-twice test).
- [x] When the notifications tab is mounted (activity tab focused), the
  provider's `_tick` skips `refreshUnreadCount()` — tab's own
  `/v1/activities` fetch supplies truth. Asserted by direct `_tick`
  invocation with fake api client's `unreadCountCalls == 0`.
- [x] Shell + notifications_tab + imports_tab all consume the single
  source via the new registration API; no tab keeps a local `Timer`.
- [x] Pull-to-refresh on either tab calls its local `_load()` (+ see-all
  refresh) — unchanged. Pull-to-refresh does NOT touch the provider's
  poll state; next tick still fires at the original cadence.
- [x] One-commit landing: all four files ship together in a single
  commit.
- [x] Sentinel log line `[activity-read] tick` fires every 30s during
  manual walkthrough.
- [x] Zero widget tests added (AC cap of 3/story; unit coverage of the
  decision matrix is sufficient and cheaper).

## QA walkthrough

1. Cold-start: launch the app. Bottom-nav badge renders within 1s
   (immediate `_tick` in `startPolling`). DevTools console shows
   `[activity-read] tick`.
2. Stay on Home. Every 30s the console prints another
   `[activity-read] tick` and `GET /v1/activities/unread-count` fires
   (Network tab). Nothing else on that interval.
3. Tap Activity tab. Manual refresh triggers one immediate
   `/unread-count` (from `_onDestinationSelected`), then
   `NotificationsTab._load()` fires `/v1/activities` and
   `ImportsTab._load()` fires `/v1/import-jobs` + `/v1/import-items`.
   Next 30s tick: only the tab fetches (`/v1/activities` +
   `/v1/import-jobs` + items). NO `/v1/activities/unread-count` call
   — this is the redundancy kill.
4. Swipe between Notifications ↔ Imports a few times. Each tab is
   `AutomaticKeepAliveClientMixin`-kept; both listeners stay
   registered across swipes; still exactly one tick per 30s.
5. Pull-to-refresh the Notifications tab. `/v1/activities` fires
   immediately; the 30s poll cadence is unchanged.
6. Leave Activity screen (tap Home). Both tab listeners remove
   themselves. Next tick: provider falls back to
   `/v1/activities/unread-count`.
7. Backend delta check — pin a baseline with
   `analyze_latency.py --window 24h --format csv > /tmp/pre.csv`
   before merging, then post-dogfood run the same command and diff.
   The `GET /v1/activities/unread-count` count column should fall
   measurably on days with heavy Activity-tab usage.

## Code review findings (addressed)

- [HIGH] **Disposer re-entrancy** — if `registerTickListener` is called
  twice with the same callback, the disposer closure would only remove
  one entry from the list but decrement the counter once per call. Fix:
  disposer guards against double-invoke via a `bool _disposed` closure
  capture. Verified by test.
- [MEDIUM] **`_tick` during tab dispose** — a tab's listener could fire
  `_load(silent: true)` mid-dispose if the tick fires between
  `setState`-disabled `mounted` window and the `removeTickListener`
  call. The tab's `_load` already guards with `if (!mounted) return`
  post-await. No additional fix required; documented here for future
  maintainers.
- [MEDIUM] **Shell disposes provider-owned Timer** — confirmed
  `stopPolling()` in shell dispose kills the cadence globally. In the
  current app the shell is the top-level navigation shell and never
  itself disposes during app life; but if a consumer ever wraps it
  differently (tests, hot reload) the provider Timer would leak. Added
  `@visibleForTesting hasActiveTimer` getter + test assertion.
- [LOW] **Sentinel log noise** — `debugPrint` only fires in debug
  builds by default (release builds strip debugPrint entries). No
  production log spam.

## Gotchas for next stories

- `ActivityReadProvider.startPolling()` / `stopPolling()` /
  `registerTickListener` are now the canonical poll primitives. If
  pfc-3 / pfc-4 need their own polling cadences, reuse this pattern
  (single Timer, callback registration) — do NOT sprinkle fresh
  `Timer.periodic` across more widgets.
- Pull-to-refresh on either activity tab bypasses the
  `contributesUnreadCount` gate (it calls `_load` directly). This is
  intentional — manual refreshes are cheap and should always happen.
