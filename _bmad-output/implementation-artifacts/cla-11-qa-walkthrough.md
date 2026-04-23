# cla-11 — QA Walkthrough

## What shipped

Firebase Performance Monitoring is now enabled as a **secondary** source
of truth alongside the custom `client_latencies` pipeline.

- `pubspec.yaml` pins `firebase_performance: ^0.10.0+11` — the last
  0.10.x line compatible with `firebase_core ^3.x`. 0.11.x requires
  `firebase_core ^4` and is out of scope for this epic.
- `lib/core/services/firebase_http_metric_interceptor.dart` — new Dio
  interceptor that wraps every request in
  `FirebasePerformance.instance.newHttpMetric(url, method)`. Honors
  `Options.extra['_perf_skip']` so the client-latency POSTs don't
  feed back into Firebase. Defensive `try/catch` on every Firebase
  call — a failed metric never fails the user-visible request.
- `lib/main.dart` — initializes Firebase Performance collection and
  inserts the interceptor at slot index 2 of the Dio chain (after
  `dedup`, before `perf_timing`), matching the cla-6 pinned chain
  order `[auth, dedup, firebase_http_metric, perf_timing]`. Gated on
  `!kE2EMode && !kIsWeb` per the epic's AC3 soft-fail.
- `docs/PERFORMANCE_OPS.md` — new **Firebase Performance Monitoring
  (cla-11 / cla-12)** section explaining the "secondary source" stance,
  how to cross-compare with the custom dashboard, and the backout
  path.
- `test/core/services/firebase_http_metric_interceptor_test.dart` —
  5 tests pin the start/stop pair for 2xx, the status-code capture for
  4xx, the `_perf_skip` bypass, graceful handling when Firebase
  throws, and method mapping (POST).

## Manual QA steps

- [ ] Pull + `flutter pub get` — confirm `firebase_performance` + its
      platform_interface resolve cleanly with our existing
      `firebase_core: ^3.9.0` pin.
- [ ] `flutter run --release` on iOS / Android — confirm the app
      still launches normally (Firebase Performance init adds <100 ms
      typically, and our try/catch makes even a broken init survivable).
- [ ] Open the app, navigate around for 30 s to generate network
      traffic. Wait for Firebase's ~12 h reporting window.
- [ ] Firebase Console → Performance → Network requests: confirm at
      least one HTTP trace shows up (e.g. `GET /v1/health`,
      `GET /v1/recipe-books`). Status code column is populated.
- [ ] Firebase Console → Performance → App start: confirm iOS /
      Android app-start p50 populated.
- [ ] Cross-compare one URL's p95 against the admin Client tab's
      **Network** section for the same 24 h window. Agreement within
      ±20% is healthy; >20% divergence → investigate per the
      Performance Ops runbook.
- [ ] **Web smoke test** — `flutter build web --release`. This is
      the known-risk step per AC3. Two possible outcomes:
      - ✅ Build succeeds: no further action, web just doesn't send
        Firebase traces (we runtime-skip on kIsWeb).
      - ❌ Build fails on a `firebase_performance` tree-shake: this is
        the soft-fail the epic accepts. The mobile-only enablement
        still satisfies AC3 + AC4; document the failure mode in the
        docs section and move on.

## Regression surface

- **No schema changes.** `client_latencies` keeps its existing shape.
  Firebase Performance writes to Firebase's own backend.
- **No CI workflow changes.** Tests run via `flutter test`.
- **Dio chain ordering** is now measurably `[auth, dedup,
  firebase_http_metric, perf_timing]`. If a future change tries to
  `.add()` an interceptor at the end expecting it to run after
  `perf_timing`, that still works — our insert is at index 2.
- **Existing ApiClient tests** didn't cover the chain order
  explicitly; they pass unchanged because the interceptor we add in
  `main.dart` never runs under the test harness (it's only added
  after `Firebase.initializeApp` which is skipped in kE2EMode).

## Known-safe choices (and why)

- **`^0.10.0+11` version pin** — verified on pub.dev today as the
  newest 0.10.x (last line compatible with firebase_core `^3.x`).
  Upgrading to 0.11.x would require bumping `firebase_core` across
  the app; out of scope here.
- **`kIsWeb` runtime gate** — AC3 explicitly says mobile-only is
  acceptable if `flutter build web --release` breaks. The runtime
  gate keeps the dep in place (so the tree-shake risk is well-
  defined), but skips init on web. If the build fails, that's a
  separate non-blocker; if the build succeeds, web users simply
  don't get Firebase traces (the custom pipeline still covers them).
- **`try/catch` blankets** around every Firebase call — a
  mis-initialized Firebase Performance must never surface as a
  failed HTTP request or a crash.
- **Slot index 2 insertion** in `main.dart` instead of re-ordering
  `api_client.dart` — keeps the ApiClient constructor pure and
  Firebase-agnostic; the initialization ordering lives where
  Firebase lives (main.dart).
- **Interceptor honors `_perf_skip`** — the client-latency POSTs set
  this flag specifically to avoid a telemetry feedback loop; Firebase
  needs to respect the same bypass.

## Backout

- Revert the commit. No migrations; `firebase_performance` gets
  removed from pubspec; the Dio chain falls back to
  `[auth, dedup, perf_timing]`. Firebase console traces stop
  arriving within ~12 h; they don't need to be deleted.
