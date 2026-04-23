# cla-10b — QA Walkthrough

## What shipped

The `/admin/metrics` screen is now tabbed — **Server** (existing Endpoints
+ Tasks view) and **Client** (new, cla-10b). The Client tab consumes the
four admin GETs shipped in cla-10a (`/v1/admin/metrics/client/routes`,
`/endpoints`, `/jank`, `/sparkline`) and surfaces:

- Four stat cards, each with label + big-number value + aggregate
  sparkline:
  - **Cold-start (peak)** — peak bucket from `app_start` sparkline
  - **Route paint p95 (worst)** — max `p95_ms` across routes rows
  - **Network p95 (worst)** — max `p95_ms` across endpoint rows
  - **Jank build p95 (worst)** — max `build_p95_ms` across jank rows
- Three sortable drilldown tables (Routes, Endpoints, Frame jank)
  reusing the `MetricsTable` + `LatencySparkline` widgets from the
  Server tab so look-and-feel matches.
- Filters: window (1h / 24h / 7d / 30d), platform (All / iOS / Android /
  Web), free-text `app_version`, free-text `route`. All four are
  forwarded on the wire.
- Pull-to-refresh + inline error card w/ retry (same affordance as the
  Server tab).

## Manual QA steps

- [ ] Log in as admin, open `/admin/metrics` — the AppBar now shows
      two tabs: **Server** and **Client**. Default tab is Server
      (no visual regression).
- [ ] Tap **Client** — spinner, then:
      - header row with window + platform `SegmentedButton`s,
      - app_version + route text fields + **Apply** button,
      - 4 stat cards (or stacked column on narrow width),
      - Routes / Endpoints / Frame jank tables.
- [ ] Change window to **1h** — all four endpoints + four sparklines
      re-fetch; the "Last updated Xs ago" label resets.
- [ ] Change platform to **iOS** — same re-fetch, but this time URL
      shows `?platform=ios` in DevTools.
- [ ] Type a partial app_version (e.g. `1.0.55`) → tap **Apply** —
      filter is forwarded, table narrows.
- [ ] Clear the app_version field → tap Apply — filter drops.
- [ ] Kill the API (block `/v1/admin/metrics/client/*` in the browser
      devtools network panel) → pull-to-refresh → the inline error
      card renders with **Retry** and the error detail.
- [ ] Switch back to **Server** tab and the original Endpoints +
      Tasks view still works (no regression from the refactor).
- [ ] Flip back and forth between tabs several times — no re-fetch
      on each tab switch (KeepAlive is on).

## Regression surface

- `test/features/admin/admin_metrics_screen_test.dart` — updated to
  cover the tab shell + still pins the Server tab's endpoint/task row
  rendering + window-change re-query behaviour (4 tests, all green).
- `test/features/admin/admin_client_metrics_tab_test.dart` — new, 10
  tests: initial fetch fan-out across all four endpoints + four
  sparklines, stat card labels, section headers, row→table binding
  for routes/endpoints/jank, worst-row stat aggregation, platform
  filter, app_version filter on Apply, 30d window.
- `dart analyze` clean on the three changed files. Pre-existing
  warnings in other admin files are untouched.

## Known-safe choices (and why)

- **Stat cards use the worst-row p95 as the headline number**, not a
  cross-row aggregate percentile. Backend doesn't ship a "client
  side p95 across everything" scalar and I didn't want to add one —
  operator flow is "find the worst thing, drill in," which this
  matches. Documented in the story.
- **Cold-start uses peak sparkline bucket** because the sparkline is
  the only `app_start` aggregation cla-10a ships; bucket width is
  window/24. Label is "Cold-start (peak)" to signal it isn't a
  textbook p95.
- **Race-condition guard**: `_fetchToken` counter drops late
  responses if a user changes filters mid-flight.
- **AutomaticKeepAliveClientMixin** on both tabs so tab-switching
  doesn't blow away in-flight state or trigger re-fetch.
- **No migration, no backend work** — cla-10a already ships the
  four GETs. This PR is strictly Flutter.

## Backout

- Revert this commit. No migrations, no schema changes, no env flags.
  The four backend endpoints remain available and untouched.
