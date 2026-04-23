# cla-8 — QA Walkthrough

## What shipped

Android `androidx.metrics:metrics-performance:1.0.0` (latest stable from
Google Maven, verified at kickoff — supersedes the stale `1.0.0-beta01`
the epic draft named) is now wired into the app. The path:

1. `app/android/app/build.gradle.kts` — adds the `metrics-performance`
   dep and enables `buildFeatures.buildConfig = true` so Kotlin can
   read `BuildConfig.DEBUG` for the release-only gate.
2. `app/android/app/src/main/kotlin/com/palateful/palateful/JankStatsBridge.kt`
   — new. Attaches JankStats to `activity.window` and rolls up per-
   minute (jank-frame count, total frames, total + max jank duration).
   Implements `EventChannel.StreamHandler` on `com.palateful.jankstats`.
   Buffers up to 8 pre-subscribe aggregates.
3. `MainActivity.kt` — instantiates the bridge inside
   `configureFlutterEngine`, wires the EventChannel, gated on
   `!BuildConfig.DEBUG`. Stops the bridge in `onDestroy`.
4. `app/lib/core/services/jankstats_bridge.dart` — Dart side.
   Subscribes to the channel and enqueues one `ClientLatencyIngest`
   event per payload with `type=jankstats_daily`,
   `durationMs=total_jank_duration_ms`, `extra=` the full mapped
   dict. GetIt `isRegistered` guard for the kE2EMode case.
5. `main.dart` — bootstraps the bridge after the ingest singleton,
   Android-only, web-guarded. (Mirrors the cla-7 iOS bridge wiring
   exactly.)

## Manual QA (Play Internal testing path)

JankStats reports real data from any Android build, but we gate it to
release-mode so dev tracing stays clean. So validation happens on a
Play Internal build, not a debug `flutter run`.

- [ ] Produce a release AAB: `flutter build appbundle --release`
      (or upload via Fastlane to Play Internal).
- [ ] Install on a physical Android device; use the app for a couple
      of scrolling sessions (Home → Books list → Recipe detail → back).
- [ ] Wait at least 1 minute (the bridge emits once a minute) — or
      several minutes so there's a populated window or two.
- [ ] In the DB:
      ```sql
      SELECT id, created_at, type, platform, app_version, duration_ms,
             jsonb_pretty(extra) AS extra
      FROM client_latencies
      WHERE type = 'jankstats_daily'
      ORDER BY created_at DESC
      LIMIT 10;
      ```
- [ ] Confirm at least one row with:
      - `type = 'jankstats_daily'`
      - `platform = 'android'`
      - `app_version` matches the Play Internal build
      - `extra.jank_frame_count` (could be 0 on smooth devices)
      - `extra.total_frame_count` > 0
      - `extra.total_jank_duration_ms` >= 0
- [ ] **Negative check — debug build**: run `flutter run --debug` on
      the same device, use the app for a few minutes. Confirm **no**
      new `jankstats_daily` rows appear for that device's
      `app_version`. (MainActivity's `!BuildConfig.DEBUG` guard.)

## Regression surface

- `app/test/core/services/jankstats_bridge_test.dart` — 5 Dart-side
  tests: kE2EMode guard (no ingest → silent drop), payload mapping,
  non-Map rejection, missing `total_jank_duration_ms` defaults to 0,
  non-Android `start()` is a no-op.
- No unit tests for the Kotlin side — instrumented tests require a
  device/emulator, out of scope for this PR. AC is validated via the
  Play Internal manual steps above.
- No schema changes: `jankstats_daily` type already lives in
  `libraries/utils/utils/models/client_latency.py` as of cla-1a.

## Known-safe choices (and why)

- **`androidx.metrics:metrics-performance:1.0.0`** — stable, verified
  on Google Maven today. The `1.0.0-beta01` version the epic draft
  mentioned is one of five beta + one RC versions superseded by
  1.0.0 (GA). No migration needed; the API surface we use is the
  stable one.
- **Per-minute aggregation, type tag is `jankstats_daily`**. Naming
  mirrors `metrickit_daily` for parity; the server-side aggregator
  (cla-10a `/jank` endpoint) groups across the time window, so it
  doesn't matter whether each event is 60 s or 24 h.
- **Pre-subscribe buffer (8 payloads max)**. First-minute flushes
  can arrive before Dart subscribes. Dropping the oldest if the
  buffer fills is fine — JankStats emits per-minute, so at most 8
  minutes of pre-subscribe backlog.
- **Uses `frameDurationUiNanos`** from `FrameData` (the UI-thread
  component of the frame). Compositor-side hitches are also in the
  payload (`frameDurationCpuNanos` on newer API levels) but we only
  ship the UI-side duration for v1 simplicity; revisit if the
  operator dashboard shows a gap.
- **BuildConfig opt-in in Gradle**: AGP 8+ defaults `buildConfig` to
  `false`. Enabling it is cheap and also benefits future feature
  flags. Comment in the gradle file documents why.

## Backout

- Revert the commit. The `metrics-performance` dep will also fall
  off the APK; no migrations or schema changes to undo.
