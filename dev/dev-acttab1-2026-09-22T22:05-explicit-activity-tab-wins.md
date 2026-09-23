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

- [ ] **First task, before any design:** a widget test that pushes
      `/activity?tab=imports` from another shell branch and asserts which
      tab renders. It settles reuse-vs-fresh-construction, and its result
      picks the fix. Do not design around the mechanism above until the
      test confirms which one is live — it was inferred from reading, not
      observed.
- [ ] An explicit `?tab=` is honoured on arrival and is not overridden
      afterwards by another instance's count-based auto-switch.
- [ ] The count-based guess still works where it belongs: arriving at
      `/activity` with no `?tab=` picks the busier tab, ties →
      Notifications, as today.
- [ ] A regression test for the cross-instance case: an ActivityScreen
      already mounted without `?tab=` must not pull a newly-pushed
      explicit-tab screen off its tab.
- [ ] `live_import_strip.dart:42-45` uses `ActivityRoutes.hubPath`
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
