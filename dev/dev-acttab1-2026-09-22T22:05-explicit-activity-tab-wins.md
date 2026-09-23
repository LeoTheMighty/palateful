---
hash: acttab1
type: dev
created: 2026-09-22T22:05:00-06:00
title: an explicit ?tab= wins over the count-based guess (tapping "imports in progress" lands on Notifications)
from: dev/dev-impvis1-2026-09-22T22:00-imports-tab-shows-every-in-flight-import.md
status: in-progress
owner: /devx-c2872fff
branch: feat/dev-acttab1
---

## Goal

Second half of Leo's report: tapping the "1 import in progress" strip
*"goes to the empty notification tab again"*. The strip pushes
`/activity?tab=imports`
(`app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart:42-45`),
which the router maps correctly
(`app/lib/core/router/app_router.dart:704-719`) — and the app still shows
Notifications.

**The mechanism is visible statically; that it is Leo's instance is not.**
`app/lib/features/activity/activity_screen.dart:50-84`: an ActivityScreen
built WITHOUT `?tab=` registers listeners on the two counts that call
`setTab(initialTabFromCounts(...))`, and a tie resolves to Notifications
(`app/lib/features/activity/providers/activity_tab_provider.dart:41-47`).
`activityTabProvider` is app-scoped and drives *every* mounted
ActivityScreen through `ref.listen`
(`app/lib/features/activity/activity_screen.dart:131-133`). A pending
**parser batch** contributes 0 to `imports_actionable` — that counts
ImportItems only
(`libraries/utils/utils/models/import_item.py:24-30`) — so tapping a strip
that exists *because* of a parser batch is exactly the case where the
count that decides the tab is zero.

Unconfirmed and load-bearing: whether `push('/activity?tab=imports')` from
another shell branch builds a fresh ActivityScreen (honouring
`initialTab`) or reuses the Activity branch's existing state under
`StatefulShellRoute.indexedStack`
(`app/lib/core/router/app_router.dart:641-645`). `ActivityScreen` has no
`didUpdateWidget`, so if the state is reused, `initialTab` is **ignored
outright** — a different bug with a different fix.

## Acceptance criteria

- [x] **First task, before any design:** a widget test that pushes
      `/activity?tab=imports` from another shell branch and asserts which
      tab renders. It settles reuse-vs-fresh-construction, and its result
      picks the fix. Do not design around the mechanism above until the
      test confirms which one is live — it was inferred from reading, not
      observed.
- [x] An explicit `?tab=` is honoured on arrival and is not overridden
      afterwards by another instance's count-based auto-switch.
- [x] The count-based guess still works where it belongs: arriving at
      `/activity` with no `?tab=` picks the busier tab, ties →
      Notifications, as today.
- [x] A regression test for the cross-instance case: an ActivityScreen
      already mounted without `?tab=` must not pull a newly-pushed
      explicit-tab screen off its tab.
- [x] `live_import_strip.dart:42-45` uses `ActivityRoutes.hubPath`
      (`app/lib/core/router/activity_routes.dart:12`) instead of the
      hard-coded literal, as does
      `app/lib/features/home/widgets/batch_import_status_widget.dart:91`.

## Technical notes

- `_userTouchedTab` (`activity_screen.dart:105`) already latches against
  the auto-switch after a manual swipe. An explicit route tab arguably
  deserves the same latch — but confirm with the test first; if the screen
  is being reused, the latch is not where the bug is.
- `ActivityTab.fromWire` falls back to `notifications` for anything
  unrecognised (`activity_tab_provider.dart:20-28`), so a typo'd `?tab=`
  is indistinguishable from none. Worth a log line at minimum.
- Nothing in `app/test` asserts the *rendered* tab after a push;
  `app/test/core/router/import_history_redirect_test.dart:142-182` only
  asserts the redirect location string.

## Status log
- 2026-09-22T22:05 — filed from the scoping pass on Leo's report, split out of impvis1 so the tab-selection defect is not fixed by accident inside a data-source change. Blocked-by: —.
- 2026-09-23T01:20 — claimed for /devx (hand-claim: main is a serialized deploy lane, claim commit lands on feat/dev-acttab1). Base: 0cffbe11, which includes impvis1 (#56) — so the Imports tab now has something to render when the tab selection is right, which is what makes this half testable end to end.
- 2026-09-23T01:40 — phase 2: spec ACs direct; 5 ACs; workstream=none.
- 2026-09-23T01:55 — first task done, and it ruled a suspect OUT. `app/test/core/router/activity_tab_push_test.dart` measures go_router on a minimal StatefulShellRoute.indexedStack: pushing `/activity?tab=imports` from another branch BUILDS A FRESH screen and delivers the parameter, even when the branch was already visited without a tab (recorded sequence `[null, imports, null]` — the tab-less route rebuilds behind the new one in the IndexedStack, which is why asserting on "the last build" first reported the opposite). So router reuse is not the bug, and `ActivityScreen` having no `didUpdateWidget` does not matter here.
- 2026-09-23T02:05 — the real mechanism, reproduced in `activity_screen_tab_override_test.dart`: the spec's inferred cause was right. A screen mounted WITHOUT `?tab=` keeps count listeners alive; when they resolve it calls `setTab` on the app-scoped provider, and every other mounted screen follows — including one just routed to an explicit tab. With the reported counts (a pending parser batch contributes 0 to `imports_actionable`) the explicit-Imports screen is dragged to Notifications. Test failed before the fix, passes after.
- 2026-09-23T02:10 — phase 3: the latch lives WITH the shared state, not per screen — `setTab` (deliberate: a route's `?tab=` or a user swipe) latches out `suggestTab` (the count-based guess). A per-screen flag cannot fix a fight over app-scoped state. Trade-off pinned by its own test: after any deliberate choice the cold-start guess stops firing for the session, on every screen. Also replaced the three hard-coded `'/activity?tab=imports'` literals with `ActivityRoutes.hubPath`.
- 2026-09-23T02:15 — phase 5: flutter test 1683 passed, flutter analyze 0 errors.
- 2026-09-23T02:45 — phase 4: read-only adversarial review; 10 findings (1 HIGH, 3 MED, 6 LOW); all fixed or recorded. **The HIGH was mine and it was the ugly kind: two of my six tests were vacuous.** Re-pumping `_wrap(ActivityScreen(...))` with different constructor args does NOT remount — same runtimeType, null keys, so `canUpdate` is true, the State is reused and `initState` never runs again. The "session-wide latch" test therefore never mounted a second screen and passed identically pre-fix, while its commit message claimed it pinned the trade-off. Rewritten to mount both screens in one tree under distinct keys, and asserted on the PROVIDER rather than the second screen's TabBar — every screen follows the shared provider by design, so the second screen moving proves nothing about the guess.
- 2026-09-23T02:50 — two reachable ways the latch re-created the original symptom, both closed: (a) an **unrecognised** `?tab=` latched, because `fromWire` maps `?tab=improts` and `?tab=` to notifications — a truncated deep link or stale push payload could pin a session to Notifications forever; now only `tryFromWire`-recognised values latch. (b) The latch outlived **sign-out**: one process, one container, never invalidated, so user B inherited user A's latch and lost the count-based pick entirely; `ActivityTabNotifier.reset()` is now called from the profile logout path.
- 2026-09-23T02:55 — third fix, a pre-existing bug the review surfaced: the count listeners were never one-shot. They live as long as the screen, and the bottom-nav instance lives as long as the process, so the "cold-start fallback" could throw a user mid-scroll from Imports to Notifications twenty minutes in. Now dropped after the first resolve. Also stopped a programmatic `animateTo` settling from setting `_userTouchedTab`, which made that flag read "the user swiped" when nobody had.
- 2026-09-23T03:00 — RED verified per test, by simulating each defect in turn rather than assuming: latch disabled → the bug test and the trade-off test fail; one-shot removed → the one-shot test fails; `fromWire` restored for the latch decision → the typo test fails. Each new test fails against the specific defect it guards.
- 2026-09-23T03:05 — phase 5 (re-run): flutter test 1685 passed, flutter analyze 0 errors.
