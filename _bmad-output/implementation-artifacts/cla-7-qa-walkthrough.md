# cla-7 — QA Walkthrough

## What shipped

iOS MetricKit daily payloads now flow into the `client_latencies` table
as `type=metrickit_daily` events. The path is:

1. `app/ios/Runner/MetricKitReceiver.swift` — implements
   `MXMetricManagerSubscriber`. On every `didReceive(MXMetricPayload)`
   callback, extracts the seven top-level fields the epic calls out
   (launch_time_ms, hang_time_ms, scroll_hitch_ratio, cpu_time_ms,
   disk_write_kb, cellular_upload_kb, memory_peak_mb) and stores the
   full `payload.jsonRepresentation()` under `extra.raw_payload`.
   Truncates raw_payload (`payload_truncated=true`) past ~900KB so we
   stay under the Flutter binary messenger cap.
2. `app/ios/Runner/AppDelegate.swift` — instantiates the receiver in
   `didFinishLaunchingWithOptions` and wires an `FlutterEventChannel`
   on `com.palateful.metrickit` with `MetricKitReceiver` as its
   `FlutterStreamHandler`. Gated by `#if !DEBUG` — debug builds never
   even subscribe.
3. `app/lib/core/services/metrickit_bridge.dart` — Dart side of the
   same channel. `start()` subscribes to the broadcast stream; each
   event is coerced into a `ClientLatencyIngest.enqueue` with
   `type=metrickit_daily`, `durationMs=cpu_time_ms`, `extra=` the full
   mapped dict. GetIt `isRegistered<ClientLatencyIngest>()` guard
   because kE2EMode skips the ingest singleton.
4. `app/lib/main.dart` — bootstraps `MetricKitBridge` inside
   `_bootstrapClientLatencyIngest` (after ingest is registered, iOS
   only, web-guarded).

## Manual QA (TestFlight-only path)

MetricKit only delivers real data from release builds on physical
devices — per Apple, Simulator never fires `MXMetricManagerSubscriber`
and Debug/Profile builds are filtered out OS-side. So the AC calls for
manual verification on TestFlight, 24h after install.

- [ ] Ship a TestFlight build that includes this change.
- [ ] Install it on a real iPhone; use the app for ~10 minutes (so
      there's something for MetricKit to summarize).
- [ ] Wait 24 hours.
- [ ] In the DB (prod or staging mirror):
      ```sql
      SELECT id, created_at, type, platform, app_version, duration_ms,
             jsonb_pretty(extra) AS extra
      FROM client_latencies
      WHERE type = 'metrickit_daily'
      ORDER BY created_at DESC
      LIMIT 5;
      ```
- [ ] Confirm at least one row with:
      - `type = 'metrickit_daily'`
      - `platform = 'ios'`
      - `app_version` matches the TestFlight build
      - `duration_ms > 0` (cumulative CPU time in ms)
      - `extra.launch_time_ms` present (and reasonable, <5000 typical)
      - `extra.raw_payload` a non-trivial JSON object (tens of keys)
- [ ] **Negative check — Debug build**: install a local Debug build,
      leave it running for 10 minutes, then confirm **no** new
      `metrickit_daily` rows appear for that device's app_version
      over the next 24h. (The `#if !DEBUG` gate should stop the
      subscriber from ever registering.)

## Regression surface

- `app/test/core/services/metrickit_bridge_test.dart` — 6 Dart-side
  tests: kE2EMode guard (no ingest registration → silent drop),
  full-payload mapping, non-Map rejection, `payload_truncated`
  propagation, missing `cpu_time_ms` defaults to 0, non-iOS `start()`
  is a no-op.
- Can't unit-test the Swift side directly — AC validates via the
  TestFlight steps above.
- No server schema changes: `client_latencies` already accepts the
  `metrickit_daily` type (it's in `libraries/utils/utils/models/client_latency.py`
  as of cla-1a).

## Known-safe choices (and why)

- **No histogram p95 extraction** (launch_time_ms uses the histogram's
  first bucket start). Computing MXHistogram p95 in Swift requires
  iterating buckets with `bucketCount` weights — adds ~30 lines of
  arithmetic for a number that's already persisted in `extra.raw_payload`
  and queryable server-side. If the first bucket turns out misleading
  we'll parse raw_payload to derive p95 in SQL or a follow-up script.
- **`cumulative_cpu_time_ms` as durationMs**. The schema requires a
  `duration_ms`; MetricKit's day-aggregate doesn't map cleanly to a
  single duration, so we pick the field most likely to trend with
  app-perf regressions. Documented inline in `metrickit_bridge.dart`.
- **Pending-payload buffer on the Swift side**. First-launch
  MetricKit callbacks can arrive before Dart has subscribed to the
  EventChannel; we buffer up to 8 events and drain on `onListen`.
  Cap is there so a runaway OS callback loop can't grow the queue
  without bound.
- **Kept FlutterMethodChannel contract from `palateful/push` untouched**
  to avoid regressing the APNs handoff.

## Backout

- Revert the commit. No migrations, no schema changes, no runtime
  flags.
- If a build fails to compile because MetricKit isn't available on
  someone's Xcode (unlikely — MetricKit ships with the iOS SDK since
  2019), the `#if !DEBUG` gate + `@available(iOS 13.0, *)` checks can
  be broadened.
