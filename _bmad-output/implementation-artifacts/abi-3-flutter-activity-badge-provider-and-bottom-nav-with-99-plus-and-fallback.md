# Story abi-3: Flutter — badge reads structured payload + 99+ + old-client fallback

Status: ready-for-dev

## Story

As Leo,
I want the bell in the bottom nav to match what's actually in the Activity tabs,
so that I can trust the number and not go hunting for phantom items.

## Acceptance Criteria

1. `ActivityReadProvider` parses the new `{notifications, imports_actionable, count}` payload and exposes two new `ValueNotifier<int>` fields: `notificationsCount` and `importsActionableCount`. The existing `unreadCount` stays as the derived sum (kept wired for readers).
2. `structuredCountsAvailable` (bool `ValueNotifier`) flips true when the server returns both `notifications` and `imports_actionable`; stays false on old `{count}`-only responses. Per-tab badges observe this to show/hide.
3. Bottom-nav badge reads `notifications + imports_actionable`. Badge text renders `"99+"` above 99. `Semantics(label: "N unread items")` uses the exact count so screen readers aren't truncated.
4. Old-client fallback: when the response has only `{count}`, the bottom-nav badge still renders `count`; per-tab badges hide. A `debugPrint` warns once: `"badge: old payload shape detected, per-tab badges suppressed"`.
5. Existing widget tests for bottom-nav badge continue passing. New test: `{notifications: 50, imports_actionable: 80}` → badge `"99+"`, Semantic label `"130 unread items"`. Old-client test: only `{count: 7}` → badge `"7"`, `structuredCountsAvailable == false`.
6. No flicker regression: the refresh poll still debounces at the existing cadence (30s). A 100ms micro-debounce on `setUnreadCount` is added for same-value no-ops (already in place).

## Key Files

- Modify: `app/lib/features/activity/providers/activity_read_provider.dart`
- Modify: `app/lib/shared/widgets/scaffold_with_bottom_nav.dart`
- Tests: `app/test/features/activity/activity_read_provider_test.dart`, `app/test/shared/widgets/scaffold_with_bottom_nav_test.dart` (new)

## Dev Notes

- Keep the existing `ValueNotifier<int> unreadCount` wired as the derived sum so older callers don't break.
- Use `ChangeNotifier`/plural `ValueNotifier`s rather than introducing Riverpod just for this — the existing provider is `getIt`-registered + ValueNotifier-based.
- 99+ label with correct Semantics is the load-bearing accessibility AC.
