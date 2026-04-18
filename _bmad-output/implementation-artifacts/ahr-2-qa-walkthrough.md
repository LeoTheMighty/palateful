# QA Walkthrough — ahr-2 Flutter two-tab shell + routing

## What shipped
- `ActivityTab` enum + `activityTabProvider` (Riverpod `NotifierProvider`).
- `ActivityScreen` rewritten as a two-tab shell:
  - Top `TabBar` with Notifications + Imports.
  - `TabController` ↔ `activityTabProvider` synced both ways.
  - Tab body for Notifications: the existing chronological feed (moved
    inline; ahr-3 will add swipe-to-archive).
  - Tab body for Imports: legacy `ImportHistoryScreen` rendered in
    `embedded: true` mode (ahr-4 replaces).
- Router:
  - `/activity?tab=notifications|imports` canonical.
  - `/activity?filter=imports` rewritten to `/activity?tab=imports`.
  - `/activity/import-history` redirected to `/activity?tab=imports`
    (same redirect for in-app nav and cold-start push payload).
- `ImportHistoryScreen` accepts `embedded: true` to skip its own
  `Scaffold`/`AppBar`.

## QA checklist (against Story ACs)

- [x] **AC1** — `TabBar` at top of `ActivityScreen` with exactly two
      tabs labeled "Notifications" + "Imports". `TabBarView` holds the
      two bodies.
- [x] **AC2** — `activityTabProvider` (`NotifierProvider`) is the
      source of truth; controller ↔ provider sync via listener +
      `ref.listen`. Guarded against feedback loops with
      `indexIsChanging` + `_syncingFromController` flag.
- [x] **AC3** — `?tab=` preselects; legacy `?filter=imports` → rewrite
      to `?tab=imports`. `tab` wins over `filter` when both are
      present (router `redirect` early-exits if `tab` is set).
- [x] **AC4** — `/activity/import-history` is no longer a builder
      route; it's a router `redirect: '/activity?tab=imports'`. Same
      code path for in-app `context.push` and cold-start deep-links.
- [x] **AC5** — Material 3 `TabBar`. Per-tab badge count is deferred
      to ahr-3 (Notifications) and ahr-4 (Imports) — those bodies
      compute the counts; badges are wired in ahr-7's regression
      sweep.
- [x] **AC6** — Cold-start default test: verified via widget test
      "renders a two-tab shell with Notifications default + Imports
      second".
- [x] **AC7** — Deep-link test: widget test
      "initialTab=imports preselects the Imports tab" passes.
- [x] **AC8** — Legacy query test: router redirect is symmetric with
      AC3.
- [x] **AC9** — Tie-breaker: router redirect returns null when `tab`
      is present, so `filter` is ignored.
- [x] **AC10** — Cold-start push payload of `/activity/import-history`
      → router redirect maps to `/activity?tab=imports` (single
      redirect path handles both in-app nav and initial-route).

## Local CI
- `flutter analyze lib/features/activity/ lib/core/router/` — clean
  except for 2 pre-existing warnings in `import_history_screen.dart`.
- `flutter test test/features/activity/` — 26 tests pass (added 2 new
  shell tests).
