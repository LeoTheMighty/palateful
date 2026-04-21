# QA walkthrough — pfc-1 activity-hub consolidation

Pre-dogfood sanity check that three 30s pollers have collapsed into one
source without breaking the badge, notifications-tab content, or
imports-tab content.

## 1. One-timer invariant (DevTools console)

- [ ] Launch debug build. On cold start, console prints
      `[activity-read] tick` exactly once within ~1s
      (`startPolling()`'s immediate `_tick`).
- [ ] Stay on Home. Every 30s the console prints another
      `[activity-read] tick`. Not 2. Not 3. One.
- [ ] Hot-reload the app. Console printouts continue at 30s cadence
      with no duplication (shell disposes + reinitializes, no double-
      Timer leak).

## 2. Zero-redundant-fetch on activity tab

- [ ] Switch to Activity tab. In DevTools Network, the immediate
      paint fires: `GET /v1/activities/unread-count` (from
      `_onDestinationSelected`), `GET /v1/activities`, `GET
      /v1/import-jobs`, + N `GET /v1/import-items/:id`.
- [ ] Wait 30s on the Activity tab. Network shows:
      `GET /v1/activities`, `GET /v1/import-jobs`, + N
      `GET /v1/import-items/:id`. There is **NO**
      `GET /v1/activities/unread-count`. This is the redundancy kill.
- [ ] Swipe to Imports ↔ Notifications a few times. Cadence remains
      30s; listener registration is idempotent across tab switches
      (both are `AutomaticKeepAliveClientMixin`).

## 3. Badge integrity during + after activity focus

- [ ] Open the app on Home. Note the badge count (if any).
- [ ] Switch to Activity → Notifications. Swipe an unread. Return to
      Home. Badge count reduces by the number swiped (fired by
      notifications_tab's downstream `refreshUnreadCount`).
- [ ] On Home again, wait 30s. Next tick: provider's `refreshUnreadCount`
      fires. Badge reconciles to server truth.

## 4. Pull-to-refresh doesn't break cadence

- [ ] On Activity → Notifications, pull-to-refresh. Immediate
      `GET /v1/activities` fires. Wait 30s. Next tick still fires
      `/v1/activities` at the original cadence (pull-to-refresh
      doesn't reset the Timer; this is intentional).

## 5. Backend delta check (after ~24h dogfood)

```
# Pre-pfc-1 baseline (captured before deploy):
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
  --window 24h --format csv > /tmp/pre.csv

# Post-pfc-1:
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
  --window 24h --format csv > /tmp/post.csv

diff <(grep unread-count /tmp/pre.csv) <(grep unread-count /tmp/post.csv)
```

- [ ] `GET /v1/activities/unread-count` request count in the 24h
      window should fall measurably (heaviest on days with sustained
      Activity-tab usage). Exact delta depends on user behavior; the
      AC is "measurable" not "50%".

## 6. Regression sweep

- [ ] Shell badge still updates after:
  - Marking an item read on Activity tab.
  - Archiving a notification via swipe.
  - Archiving an import item via swipe.
  - Tapping a notification tile (action-URL navigation).
- [ ] iOS push arrival bumps the badge on next tick (no regression
      against the push-diag epic).
- [ ] No `Timer` / `Stream` leak warnings in DevTools after 2min of
      idle-on-Home.
