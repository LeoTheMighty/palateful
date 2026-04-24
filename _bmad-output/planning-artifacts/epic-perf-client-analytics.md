<!-- refined via party-mode 2026-04-23 -->

# Epic: Performance — Client-Side Analytics

## Overview

`epic-observability-latency` (2026-04-18) shipped server-side p50/p95/p99 via two Postgres tables (`request_latencies`, `task_latencies`), the `services/api/scripts/analyze_latency.py` ops script, and an admin metrics page. What's missing is the client side. Today when the user says "the app feels slow," the only evidence is server-side latency — which doesn't capture cold-start, route-transition, client-observed network latency, frame jank, or OS-level hang/scroll events.

User explicitly asked (2026-04-23): "Is there an easy way to track 'time to first paint'? What do people use on iOS where Lighthouse doesn't apply?"

Answer: no single mobile Lighthouse exists. The standard pattern is **fleet telemetry + deep-dive tooling + OS-level aggregates**. This epic ships all three:

- **Custom pipeline** — a `client_latencies` table + batched `POST /v1/client-latencies` endpoint that mirrors the server-side pattern. Route-paint, cold-start, frame-jank, and client-observed network timings flow into a new Client tab on `/admin/metrics`.
- **Firebase Performance Monitoring** — zero-config secondary source of truth, free, uses the Firebase app already wired for Crashlytics + FCM. Auto-captures app-start + HTTP + screen-rendering. Sampled; treated as a cross-check for the custom numbers.
- **OS-level telemetry** — iOS MetricKit (`MXMetricManagerSubscriber`) and Android JankStats (`androidx.metrics:metrics-performance`) deliver daily aggregate payloads from real field devices: hang rate, launch duration, scroll hitches, memory warnings, battery. Flutter cannot surface these on its own.

Web gets Navigation Timing API + PerformanceObserver in place of MetricKit (the native equivalent), bridged through `dart:html` to the same ingest endpoint.

**Primary source of truth is the custom pipeline.** Firebase is secondary. If the numbers disagree by >20%, we investigate — but our operator response comes from the custom dashboard we control.

## Goal

- An admin opens `/admin/metrics` → clicks the Client tab → sees cold-start p50/p95, per-route paint latency p50/p95, network-request p50/p95 (client-observed), and frame-jank p95 — filtered by platform (ios/android/web), app version, and route.
- An iOS-specific hang-rate number is available within 7 days of a rollout, sourced from MetricKit. Equivalent for Android via JankStats. Equivalent for web via Navigation Timing.
- `analyze_latency.py --section all` prints server + client tables side-by-side so "is it backend or frontend?" is a single command.
- Firebase Performance dashboard is live as a secondary cross-check; numbers agree with the custom pipeline within 20%.
- Zero new AWS resources; Postgres write volume stays within the existing `t4g.small` budget.

## End-User Flow

*Primary user here is Leo as admin/operator.*

1. Leo ships a release with a perf-regression concern. He waits 24 hours.
2. He opens the admin dashboard → Metrics → Client tab.
3. He sees the Client tab's table: Home screen route-paint p95 jumped from 320ms to 1100ms in the last 24 hours. Platform filter: iOS only. He drills in.
4. The sparkline shows the regression started at release time — not before.
5. He opens `analyze_latency.py --regression-hunt --section all` on his terminal. The output shows Home's server-side p95 is unchanged; the jump is entirely client-side. Root cause is in Flutter code, not backend.
6. He cross-references Firebase Performance's Screen Rendering dashboard — same pattern. He's confident the custom number isn't a measurement artifact.
7. Next day, he sees MetricKit's daily payload arrive. iOS hang rate is elevated — same release window. He now has three independent confirmations of an iOS-specific Flutter regression.
8. He ships a fix. 48 hours later, all three sources show the metric recovering. He closes the incident.

**Secondary user is the app user** — zero visible behavior change. No popups, no opt-in flow (telemetry is anonymous-to-cohort; `user_id` is derived from JWT and not displayed). Battery impact: negligible (batched 30s flush; MetricKit + JankStats are OS-scheduled with zero active CPU cost).

## Frontend Changes

### Flutter (shared across platforms)

- **New** `app/lib/core/services/client_latency_ingest.dart` — batched queue + periodic flush (30s or 50 events) + POST to `/v1/client-latencies`. Fire-and-forget: failed flushes drop events; no retry, no disk queue.
- **New** `app/lib/core/services/perf_navigator_observer.dart` — `NavigatorObserver` subclass. On `didPush`, record `t0`; schedule `addPostFrameCallback` inside the new route's first build frame; compute `dur = t_paint - t0`; enqueue `route_paint` event with redacted route name (`/recipes/:id/edit` not `/recipes/abc123/edit`).
- **Modify** `app/lib/main.dart` — capture `t0 = DateTime.now()` at top of `main()`; after `runApp(...)` await `WidgetsBinding.instance.endOfFrame`; enqueue one `app_start` event. Wire `PerfNavigatorObserver` into `MaterialApp.router`.
- **Modify** existing Dio interceptor (or add sibling) — record `onRequest` timestamp on `options.extra['_perf_t0']`; on `onResponse` / `onError` compute duration and enqueue `network_request` event with path-param-redacted endpoint + status code.
- **New** `app/lib/core/services/frame_jank_aggregator.dart` — `SchedulerBinding.instance.addTimingsCallback((timings) {...})`; rolling 60-second window; emits one `frame_jank_p95` event per minute per active-route (build-span p95, raster-span p95, dropped-frame count).
- **Add** `pubspec.yaml` dep `firebase_performance: ^0.10.0+11` (latest compatible). Wire on the Dio interceptor: `FirebasePerformance.instance.httpMetric(url, method)` around every request (auto-captures url, method, status, payload sizes). Screen rendering auto-captured by Firebase with no extra code once initialized.

### iOS (Swift) — MetricKit

- **New** `app/ios/Runner/MetricKitReceiver.swift` — implements `MXMetricManagerSubscriber`. Registers on AppDelegate `didFinishLaunchingWithOptions`. Receives daily `MXMetricPayload` arrays; serializes to JSON; forwards via Flutter MethodChannel `com.palateful.metrickit` → Dart handler → `ClientLatencyIngest` enqueue as `metrickit_daily` events.
- **Modify** `app/ios/Runner/AppDelegate.swift` — instantiate `MetricKitReceiver` on launch.
- Fields captured (subset of `MXMetricPayload`): launch-time p95, hang-rate ms, scroll-hitch rate, memory-warning count, cellular-upload-kb, disk-write-kb, cpu-time-s.

### Android (Kotlin) — JankStats

- **Modify** `app/android/app/build.gradle` — add `androidx.metrics:metrics-performance:1.0.0-beta01`.
- **New** `app/android/app/src/main/kotlin/com/palateful/app/JankStatsBridge.kt` — `JankStats.createAndTrack(window) { frameData -> ... }`; batches per-minute dropped-frame counts; platform-channel-forwards to Dart.
- **Modify** `MainActivity.kt` — instantiate `JankStatsBridge` in `onCreate`.

### Flutter Web — Navigation Timing

- **New** `app/lib/core/services/web_perf_bridge.dart` — `kIsWeb`-gated; calls `dart:html` `window.performance.getEntriesByType('navigation')` on first frame → emits `web_navigation` event with `fetchStart`, `domContentLoadedEventEnd`, `loadEventEnd`; registers `PerformanceObserver` for `paint` entries → emits `first_paint` + `first_contentful_paint`.

### Admin dashboard

- **New** `app/lib/features/admin/metrics_client_tab.dart` — mirrors the existing server-side metrics tab layout. Four stat cards (cold-start p95, route-paint p95, network p95, jank p95). Drilldown tables per-route + per-endpoint + per-platform. Sparklines per metric. Filters: platform, app_version, route, window (1h/24h/7d/30d).

## Backend Changes

- **New migration** `services/migrator/versions/<timestamp>_client_latencies_table.py` — creates `client_latencies` with columns mirroring `request_latencies` plus `type` (enum), `route` (varchar), `endpoint` (varchar nullable), `metric_name` (varchar nullable), `platform` (enum `ios`|`android`|`web`), `app_version` (varchar), `device_class` (varchar nullable), `user_id` (UUID nullable), `created_at` (timestamptz), `duration_ms` (int), `extra` (jsonb for OS-specific payloads). Partial indexes on `(route, created_at)`, `(platform, created_at)`, `(type, created_at)`.
- **New endpoint** `POST /v1/client-latencies` — `services/api/src/api/v1/client_latency/ingest.py` — Endpoint-class pattern. Request body: `{events: ClientLatencyEvent[]}` capped at 100 events (413 beyond). `user_id` derived from JWT, not body. Sync bulk insert. Response: `{accepted: int}`. Tests pin 100-event cap + 413 overflow + user_id derivation.
- **Modify** `services/api/scripts/analyze_latency.py` — add `--section client` and `--section all`. `client` mode reads `client_latencies`, groups by `(type, route|endpoint)`, emits p50/p95/p99 + sample count. `all` mode prints server (endpoints + tasks) and client sections consecutively. `--regression-hunt` extends to client section with the same 1.5× baseline rule.
- **New aggregation endpoints** for the admin dashboard:
  - `GET /v1/admin/metrics/client/routes?window=24h&platform=ios` — per-route p50/p95/p99 table.
  - `GET /v1/admin/metrics/client/endpoints?window=24h&platform=ios` — per-endpoint client-observed network stats.
  - `GET /v1/admin/metrics/client/jank?window=24h&platform=ios` — build-span + raster-span p95 per route.
  - `GET /v1/admin/metrics/client/sparkline?metric=route_paint&route=/home&window=7d` — time-bucketed aggregate for the chart.
  - All endpoints reuse the `is_admin` guard already in place.
- **Nightly prune** — extend existing `services/api/src/jobs/prune_latencies.py` (from `obs-latency-4`) to also prune `client_latencies` past 30 days. Same retention policy.

## Infrastructure Changes

- **No AWS resources added.** `client_latencies` lives on the existing Postgres instance (sized post-`pim-3` upgrade). Write volume estimate: ~500 events/session × 50 active users × ~5 sessions/day = ~125k rows/day — well within existing headroom.
- **Firebase**: enable Performance Monitoring in the existing Firebase project (console click-to-enable; no terraform). Cost: free within our volume (500k events/day threshold for free tier).
- **No new CI workflows** (regression guard lives in the debug-tooling epic).
- **MetricKit + JankStats are release-build only.** Debug/profile builds skip the receiver hookup so dev traces stay clean.
- **Rollout**: Flutter wiring ships behind a feature flag `CLIENT_LATENCY_INGEST_ENABLED` (default on in release, off in debug). Kill-switch via ECS env var on the backend — if the DB floods, we set it to `false` at the client via a `/v1/flags/perf` endpoint lookup (future — not in v1).

## Design Principles (refined via party-mode 2026-04-23)

- **Primary = custom pipeline; Firebase = cross-check only.** Never read Firebase during incident response. Operator muscle memory is the custom dashboard.
- **Privacy by construction + defense-in-depth.** Route names are redacted client-side before ingest AND server-side rejected (422) if any event's `route` matches a raw UUID/int-id pattern. `user_id` server-derived from JWT, never trusted from body. Shared helper at `services/api/src/utils/route_redaction.py`.
- **Fire-and-forget client, synchronous server.** Batched drops on failure, no retry, no disk queue. Server writes sync; no task queue. Load math: 125k rows/day ÷ 86400s ≈ 1.5 rows/s avg; single-round-trip 100-row inserts are sub-10ms.
- **Mirror the server-side pattern where possible, diverge where required.** Table shape mirrors `request_latencies` + adds `platform`, `app_version`, `device_class`, `extra jsonb`. The `extra` column is required, not optional — MetricKit, JankStats, and web Navigation Timing all ship platform-specific blobs that shouldn't clutter top-level columns.
- **Zero user-visible behavior change.** No toasts, no spinners, no slow-screen warnings. `firebase_performance` is scoped to HTTP + app-start only (auto screen-rendering traces disabled via manifest/plist flags).
- **Release builds only for OS-level telemetry.** MetricKit + JankStats skip the receiver wiring in debug/profile builds so dev traces stay clean.
- **Kill-switch from day one.** `GET /v1/flags/perf` ships in v1 (not deferred); Flutter checks on app-start, 5-min cache, default-on if endpoint errors. If the DB floods, we flip it without a client rebuild.
- **`go_router` observers on every branch Navigator**, not just the root. `StatefulShellRoute.goBranch` does NOT fire top-level `didPush` — we'll miss the most common nav pattern (bottom-tab swaps) without per-branch registration.
- **Dio interceptor ordering is pinned + tested.** `[auth, dedup, firebase_httpMetric, perf_timing]`. Auth first (token), dedup before perf so coalesced requests aren't double-counted, Firebase wraps the wire-call, perf-timing last to observe real wall clock. Client-latency POSTs carry `Options(extra: {'no_dedup': true, '_perf_skip': true})` to avoid feedback loops.
- **EventChannel, not MethodChannel, for MetricKit + JankStats.** Push-from-native, stream-semantic, lossy-OK matches EventChannel's contract. MethodChannel only for the initial subscribe handshake.
- **No AWS cost growth.** Postgres only. `extra jsonb` absorbs platform variance without new tables. Aligns with NFR29 ($50/mo cap).
- **Coverage non-negotiable.** `services/api` pins 100%. Every new endpoint + every branch in the redaction helper tests in the same PR.

## File Structure

```
# Flutter — cross-platform
app/pubspec.yaml                                                      (modify — add firebase_performance)
app/lib/main.dart                                                     (modify — cold-start timing + observer wiring)
app/lib/core/services/client_latency_ingest.dart                      (new — batched queue + flush)
app/lib/core/services/perf_navigator_observer.dart                    (new — NavigatorObserver subclass)
app/lib/core/services/frame_jank_aggregator.dart                      (new — SchedulerBinding.addTimingsCallback)
app/lib/core/services/api_client.dart                                 (modify — Dio interceptor extends to emit network_request + Firebase httpMetric)
app/lib/core/services/web_perf_bridge.dart                            (new — Navigation Timing bridge, kIsWeb only)
app/lib/core/services/metrickit_bridge.dart                           (new — Dart side of iOS MethodChannel)
app/lib/core/services/jankstats_bridge.dart                           (new — Dart side of Android MethodChannel)

# iOS native
app/ios/Runner/MetricKitReceiver.swift                                (new)
app/ios/Runner/AppDelegate.swift                                      (modify — instantiate receiver)

# Android native
app/android/app/build.gradle                                          (modify — metrics-performance dep)
app/android/app/src/main/kotlin/com/palateful/app/JankStatsBridge.kt  (new)
app/android/app/src/main/kotlin/com/palateful/app/MainActivity.kt     (modify — instantiate bridge)

# Backend
services/migrator/versions/<timestamp>_client_latencies_table.py      (new — Alembic migration)
services/api/src/db/models/client_latency.py                          (new — SQLAlchemy model)
services/api/src/api/v1/client_latency/ingest.py                      (new — Endpoint-class POST)
services/api/src/api/v1/admin/metrics_client.py                       (new — GET aggregation endpoints)
services/api/src/routers/v1/client_latency_router.py                  (new — mount)
services/api/src/routers/v1/admin_metrics_router.py                   (modify — add client sub-routes)
services/api/scripts/analyze_latency.py                               (modify — --section client + all)
services/api/src/jobs/prune_latencies.py                              (modify — include client_latencies)
services/api/tests/api/v1/client_latency/test_ingest.py               (new)
services/api/tests/api/v1/admin/test_metrics_client.py                (new)

# Flutter admin dashboard
app/lib/features/admin/metrics_client_tab.dart                        (new)
app/lib/features/admin/providers/metrics_client_provider.dart         (new)
app/lib/features/admin/services/metrics_client_service.dart           (new)

# Tests
app/test/core/services/perf_navigator_observer_test.dart              (new)
app/test/core/services/client_latency_ingest_test.dart                (new)
app/test/core/services/frame_jank_aggregator_test.dart                (new)
```

## Story List (draft — ACs firmed up per-story)

### cla-1a — Backend `client_latencies` table + model + nightly prune
**AC:** (1) Alembic migration creates table with columns mirroring `request_latencies` + `type`, `route`, `endpoint`, `metric_name`, `platform`, `app_version`, `device_class`, `user_id`, `duration_ms`, `extra jsonb`; (2) partial indexes on `(route, created_at)`, `(platform, created_at)`, `(type, created_at)`; (3) `extra jsonb` is required (nullable but explicit); (4) nightly-prune extended to include `client_latencies` past 30 days; (5) monthly VACUUM task added to the prune job (3.75M row table at steady state benefits).

### cla-1b — `POST /v1/client-latencies` ingest + server-side redaction + anonymous support
**User-locked (2026-04-23):** anonymous ingest is supported. Pre-login cold-start + onboarding events carry `user_id=null`; IP-based rate-limit (10 events/IP/min) protects against abuse.
**AC:** (1) endpoint accepts ≤100 events per call; 413 beyond; (2) when JWT is present, `user_id` is derived from it (ignored if in body); (3) when JWT is absent, `user_id` persists as null AND IP rate-limit (10 events/IP/min) applied via existing rate-limit middleware; 429 on excess; (4) **server-side redaction guard**: `route` is run through `services/api/src/utils/route_redaction.py::redact_route` (shared with `request_latencies` middleware); events with un-redacted routes (raw UUID/int-id in path) return 422; (5) synchronous bulk insert (no task queue); (6) load test: 50 concurrent fake clients × 100 events/batch, p95 ingest <100ms, 100% success rate; (7) tests pin validation + cap + user-id logic + redaction rejection + anonymous+rate-limit code paths; `services/api` coverage at 100%.

### cla-1c — `GET /v1/flags/perf` kill-switch endpoint + Flutter fetch-on-startup
**AC:** (1) new endpoint returns `{ingest_enabled: bool, sampling_rate: float}`; (2) backed by ECS env vars (ECS task-def flippable); (3) Flutter fetches on `main()` after Firebase init; 5-min in-memory cache; default-on if endpoint errors or times out (<500ms); (4) all telemetry emitters check the flag before enqueue; (5) integration test: flip flag off → next batch flush skipped; (6) documented in `docs/PERFORMANCE_OPS.md` kill-switch runbook.

### cla-2 — `analyze_latency.py --section client|all`
**AC:** (1) `--section client` prints client table using the same p50/p95/p99 reducer as server side; (2) `--section all` prints server + client consecutively; (3) `--regression-hunt` extends to client (rule: recent 24h p95 > 1.5× 7-to-30d baseline — same as server); (4) CLI snapshot tests pin both sections; (5) docs section in `docs/PERFORMANCE_OPS.md` shows example output.

### cla-3 — Flutter `ClientLatencyIngest` batched flush service
**AC:** (1) batched in-memory queue; (2) periodic flush every 30s or at 50 events; (3) HTTP failure drops events silently; (4) ≤100 events per POST; (5) `user_id` omitted from client payload; (6) tests with fake-clock confirm flush cadence + cap + silent-drop behavior.

### cla-4 — Flutter `PerfNavigatorObserver` + route-paint events (go_router-aware)
**Critical:** project uses `go_router` + `StatefulShellRoute`. Top-level `GoRouter(observers: ...)` does NOT fire `didPush` on branch switches (bottom-tab swaps) — the most common nav pattern in the app. Observer MUST be registered on each branch's Navigator via `StatefulShellBranch.navigatorKey` + observer list, plus a `GoRouterState` listener as a backstop for programmatic navigation.
**AC:** (1) `didPush` + `didReplace` + branch-switch events all emit route-paint; (2) `addPostFrameCallback` timing captured for each; (3) route name path-param-redacted before enqueue (also hardened server-side per `cla-1b`); (4) tests confirm one event per nav, not duplicated; (5) observer registered on every branch Navigator in `app/lib/core/router/app_router.dart`; (6) integration test: bottom-tab swap Home → Books → Home produces exactly 3 route-paint events.

### cla-5 — Flutter cold-start timing + frame-jank aggregator
**AC:** (1) `app_start` event emitted once per launch with ms duration; (2) `frame_jank_p95` event emitted per active route per minute; (3) events include build-span and raster-span p95 separately; (4) tests with fake `SchedulerBinding` confirm aggregation correctness.

### cla-6 — Dio interceptor chain: perf-timing + Firebase httpMetric + dedup coexistence
**Locked chain order:** `[auth, dedup (from ffm-7), firebase_httpMetric, perf_timing]`.
**AC:** (1) chain ordering pinned in `api_client.dart` with doc comment; (2) `network_request` event emitted per completed request (success + failure) with path-param-redacted endpoint; (3) `firebase_performance` wired via `httpMetric(url, method)` in its own interceptor; (4) client-latency POSTs carry `Options(extra: {'no_dedup': true, '_perf_skip': true})` — bypass both dedup and perf-timing to avoid feedback loops; (5) tests confirm event emission on 2xx, 4xx, 5xx, and timeout paths; (6) coexistence test: two parallel callers produce one Firebase trace, one perf-timing event, one real wire call (dedup coalesced); (7) telemetry feedback-loop test: `POST /v1/client-latencies` during an active flush does NOT emit a `network_request` event for itself.

### cla-7 — iOS MetricKit receiver + EventChannel + Dart handler
**Locked:** EventChannel `com.palateful.metrickit`, not MethodChannel (push-from-native, lossy-OK matches EventChannel semantics). MethodChannel used only for initial subscribe handshake.
**Field strategy:** ~7 most-useful fields (launch-time p95, hang-rate ms, scroll-hitch rate, memory-warning count, cellular-upload-kb, disk-write-kb, cpu-time-s) hoisted to top-level columns; **full `MXMetricPayload` stored verbatim in `extra jsonb`** so we can query new fields later without a migration.
**AC:** (1) `MetricKitReceiver.swift` implements `MXMetricManagerSubscriber`; (2) daily payloads ship via EventChannel with chunking if >1MB (large devices with many app runs can exceed channel soft-limit); (3) Dart side enqueues as `metrickit_daily` events with top-level field extraction + raw `extra`; (4) release-build only (debug/profile skip receiver wiring); (5) manual QA on TestFlight: wait 24h, confirm row with `type='metrickit_daily'`, `platform='ios'`, populated `extra` jsonb.

### cla-8 — Android JankStats receiver + EventChannel + Dart handler
**Locked:** EventChannel `com.palateful.jankstats`. Dep version: pin latest STABLE `androidx.metrics:metrics-performance` (1.0.0-beta01 in the draft is stale — check `mvnrepository` at kickoff for the newest `1.0.x` stable).
**AC:** (1) `metrics-performance` dep added at stable version; (2) `JankStats.createAndTrack(window)` in `MainActivity.onCreate`; (3) per-minute aggregate forwarded via EventChannel; (4) Dart enqueues as `jankstats_daily` events; (5) release-build only; (6) manual QA on Play Internal: confirm row with `type='jankstats_daily'` and `platform='android'` within 24h.

### cla-9 — Flutter web Navigation Timing bridge (package:web + dart:js_interop)
**Locked:** use `package:web` + `dart:js_interop` — `dart:html` is deprecated as of Flutter 3.19+. `dart analyze` lint enforces it.
**Renderer caveat:** canvas renderer makes `first-paint` ≈ `first-contentful-paint` (both fire at frame 1 regardless of content). HTML renderer behaves more like browser semantics. Document which renderer the web build uses and how to interpret the numbers.
**AC:** (1) `kIsWeb`-gated; (2) `package:web` `window.performance.getEntriesByType('navigation')` read on first frame; (3) `PerformanceObserver` registers for `paint` entries; (4) emits `web_navigation` + `first_paint` + `first_contentful_paint` events with `platform='web'`; (5) docs describe renderer-specific behavior; (6) manual QA: open Flutter web in Chrome, confirm rows per session.

### cla-10a — Admin aggregation endpoints (GET)
**Split out of cla-2 for separate review.**
**AC:** (1) four new GET endpoints under `is_admin`: `/v1/admin/metrics/client/routes`, `/endpoints`, `/jank`, `/sparkline`; (2) same p50/p95/p99 reducer as server-side aggregation; (3) filters: platform, app_version, route, window (1h/24h/7d/30d); (4) tests pin query shape + filter combinations + `is_admin` guard; 100% coverage.

### cla-10b — Flutter admin dashboard Client tab
**AC:** (1) new tab wired into `/admin/metrics`; (2) four stat cards (cold-start p95, route-paint p95, network p95, jank p95); (3) drilldown tables per-route + per-endpoint + per-platform; (4) sparklines per metric; (5) filters: platform, app_version, route, window; (6) widget tests pin layout + data binding; (7) visual parity pass against existing server-side tab (same look-and-feel).

### cla-11 — Firebase Performance Monitoring enablement (scoped)
**Scope:** HTTP + app-start only. Auto screen-rendering traces explicitly DISABLED (see `cla-12` for scope lockdown). Rationale: avoid duplicate source of truth on route-paint and sidestep "slow screen" default UX behaviors.
**Web compatibility caveat:** `firebase_performance` 0.10.x has known Flutter web build issues (tree-shake errors with `dart2js` in release). If `flutter build web --release` fails, fall back to mobile-only (iOS+Android) Firebase enablement and document in the same PR. This is a soft-fail story — don't block the release on Firebase web.
**AC:** (1) Firebase project Performance Monitoring toggled on (manual console step documented in `docs/PERFORMANCE_OPS.md`); (2) `firebase_performance` dep pinned at a version verified to build on iOS + Android release; (3) `flutter build web --release` verified before merge (with documented fallback if it fails); (4) Firebase console shows app-start + HTTP entries after 24h on a TestFlight / Play Internal build; (5) docs describe Firebase as secondary source + how to compare it with custom.

### cla-12 — Firebase Performance scope lockdown (disable auto screen traces)
**New story spawned by party-mode.** Avoids duplicate route-paint measurement and prevents any "slow screen" default UX bleed.
**AC:** (1) iOS `Info.plist` adds `firebase_performance_collection_enabled=YES` + screen-rendering collection disabled via the appropriate key; (2) Android `AndroidManifest.xml` adds the equivalent scope flag; (3) Firebase console shows HTTP + app-start entries only — no `_st_` screen traces; (4) docs explain the scope decision; (5) the audit is re-verifiable via a `firebase_performance` inspection test.

### cla-13 — Privacy policy + Data Safety form update
**New story spawned by party-mode.** MetricKit (iOS) + JankStats (Android) + custom telemetry cross the "diagnostic data" line for App Store Data Safety + Play Console Data safety forms. MUST ship before the app rollout.
**AC:** (1) `app/web/privacy.html` (from `epic-android-privacy-policy-page`) updated with a new "Diagnostic data" section describing what's collected + retention; (2) App Store Data Safety form updated (screenshot-captured in story); (3) Play Console Data safety form updated (screenshot-captured); (4) cross-reference documented in `ANDROID.md`; (5) soft dependency on `epic-android-play-console-launch` — flag if it conflicts with a staged rollout.

### cla-14 — Synthetic load test on ingest endpoint
**New story spawned by party-mode.** Validates the 500 events/user/day × 50 users assumption before it's real.
**AC:** (1) `locust` or scripted `asyncio` burst: 50 concurrent fake clients × 100 events/batch over 5 minutes; (2) ingest endpoint p95 <100ms under load; (3) 100% success rate (no 5xx, no timeouts); (4) DB side: monitor `pg_stat_activity` + buffer hit rate; no slow-query log entries; (5) results captured in `docs/PERFORMANCE_OPS.md` as the signed-off baseline.

## Dependencies

- **None hard.** `cla-1` (backend table) unblocks `cla-2` (script + dashboard) and all client-side stories that POST to the ingest endpoint.
- **Story order within epic**: `cla-1` → `cla-2` → everything else in parallel. `cla-3` (ingest service) is a prereq for every Flutter emitter (`cla-4`, `cla-5`, `cla-6`).
- **Cross-epic soft**: `epic-perf-debug-tooling`'s CI regression guard reads the `client_latencies` table and the `--section client` output; best if this epic lands first, but debug-tooling can ship with the guard running in "budget-only" mode until client data lands.
- **External dependencies**: Firebase Performance Monitoring (console toggle, already-present Firebase project), iOS MetricKit framework (iOS 13+), Android JankStats (`metrics-performance:1.0.0-beta01`, API 16+).

## Open Questions for the User (post-party-mode)

1. **Anonymous ingest for cold-start events?** Cold-start events arrive before the JWT is available. Option A: drop (current default — we lose first-paint on fresh installs). Option B: allow `user_id=null` with IP-rate-limit. Option B costs ~1 day of work but captures the most interesting signal (first-paint on a fresh install). Recommendation: **B** — worth the extra day for the signal quality.
2. **Admin per-user drilldown — ever?** Locked for v1 as aggregate-only. Commit to "never per-user," or leave door open for v2? Affects whether `(user_id, created_at)` is indexed in `cla-1a`. Recommendation: skip the index for v1; add in v2 if/when per-user drilldown ships.
3. **`analyze_latency.py --regression-hunt` client baseline window.** Server-side uses 7-to-30d. Client metrics are noisier (device heterogeneity) — wider baseline (14-to-30d) + higher threshold (2.0× instead of 1.5×)? Recommendation: same-as-server for v1; loosen if false positives bite.
4. **MetricKit top-level field set.** Draft ships 7. Disk reads + animation hangs are also genuinely useful. Ship all ~20 in `extra jsonb` but surface only 7 as top-level columns? That's the low-cost compromise. Confirm.
5. **`firebase_performance` on web if it fails to build.** `cla-11` has a soft-fail fallback (mobile-only Firebase). Is that acceptable, or must web Firebase block the epic? Recommendation: accept soft-fail — web custom pipeline is the primary source anyway.
6. **Kill-switch sampling rate knob.** `cla-1c` returns `{ingest_enabled, sampling_rate}`. Ship the sampling knob in v1 even though we plan to run at 100%? Keeps the lever in place for emergencies. Recommendation: ship the knob, default to 1.0.
7. **`epic-android-privacy-policy-page` cross-epic coordination.** `cla-13` depends on `app/web/privacy.html` existing (from the privacy-policy epic). Confirm that epic has shipped or ships before this one, otherwise `cla-13` must also author the initial file.

