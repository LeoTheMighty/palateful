# Story afh-5: Flutter — empty-state gateway links + pull-to-refresh

Status: done

## Summary

Turns the "You're all caught up" / "All clear — no imports yet" empty
states into gateways instead of dead ends. When lifetime See-all count
is > 0, a muted underlined `See past notifications (N)` /
`See past imports (N)` link renders below the illustration with a
trailing chevron-down glyph; tapping expands the matching See-all
footer and auto-scrolls it into view. Pull-to-refresh on both tabs
now additionally refreshes the See-all count and — if See-all is
expanded — resets the cursor and re-fetches page 1.

## What shipped

- `app/lib/features/activity/widgets/empty_state_gateway_link.dart`
  — NEW. Parameterised widget (`count`, `label`, `onTap`). Returns
  `SizedBox.shrink()` when count == 0. Renders a centred Text ("label
  (N)") with underline + chevron-down, wrapped in a 48dp+ InkWell.
  `Semantics(label: '<label>, <N> items, tap to expand', button: true)`
  for screen readers.
- `app/lib/features/activity/notifications_tab.dart` —
  - Empty-state ListView now reads
    `notificationsSeeAllCountProvider` and mounts the gateway link
    when count > 0.
  - New `_refreshAll()` wraps the active-list `_load()` + count
    refresh + (if expanded) `refreshFromTop()` on the See-all
    provider. Wired into both `RefreshIndicator.onRefresh` sites
    (empty + non-empty branches).
  - New `_expandAndScrollToSeeAll()` sets the expansion state to
    true, kicks off the first-page fetch if needed, then schedules a
    post-frame `Scrollable.position.animateTo(maxScrollExtent, …)`
    so the user lands on the rendered footer rather than having to
    scroll down manually. Used as the gateway link's `onTap`.
  - Empty-state ListView gained a `PageStorageKey` for symmetry.
- `app/lib/features/activity/imports_tab.dart` — same treatment:
  gateway link in the empty-state branch, `_refreshAll()` replaces
  the bare `_load()` callback on both `RefreshIndicator`s,
  `_expandAndScrollToSeeAll()` drives the gateway-link tap.
- `app/test/features/activity/widgets/empty_state_gateway_link_test.dart`
  — NEW. 5 tests: count=0 renders nothing, count>0 renders label +
  chevron, tap fires callback, semantic label encodes the count, tap
  target ≥ 48dp.

## ACs satisfied

- AC1 — widget with the (count, label, onTap) signature + chevron-down
  + underline + 48dp minimum tap target.
- AC2 — wired on `NotificationsTab` empty state with the "See past
  notifications" label and the expand-and-auto-scroll handler.
- AC3 — wired on `ImportsTab` empty state with "See past imports".
- AC4 — `count == 0` → `SizedBox.shrink()`; pure empty state for
  brand-new users.
- AC5 — gateway link sits alongside (not replacing) any first-run
  content the active list would otherwise render; it only shows when
  the active list is itself empty.
- AC6 — pull-to-refresh on both tabs re-fetches active list + count +
  (conditionally) See-all page 1.
- AC7 — `Semantics(label: 'See past … , N items, tap to expand',
  button: true)` + keyboard-focusable InkWell.
- AC8/9/10 — covered by the new widget tests (visibility,
  tap-behavior, tap target, 0-count suppression).

## Known limitations

- The auto-scroll on tap uses `Scrollable.maybeOf(context).position`
  at post-frame — if the ancestor scrollable isn't mounted yet, the
  animate is a no-op. In practice the tab is always mounted before
  the link is tappable; the no-op only applies to hypothetical test
  harnesses without an ancestor scrollable.

## CI

- `flutter analyze lib/features/activity` ✓
- `flutter test test/features/activity/ test/core/router/` ✓
  (120 passed).
