---
hash: e2egetit
type: debug
created: 2026-07-30T13:00:00-06:00
title: E2E_MODE app launch crashes — ClientLatencyIngest not registered in GetIt
from: dev/dev-fltup1-2026-07-30T09:00-align-local-flutter-to-ci-pin.md
status: in-progress
owner: /devx-loop-2026-07-30T17-52-24-754-38586
---

## Goal

`flutter drive` flow 01 reaches its assertions and passes. Today the app
crashes on its first frame under `E2E_MODE=true` because
`ClientLatencyIngest` is never registered with GetIt, so the router never
finishes building and no test can find any widget.

This is the **successor blocker** to `debug/debug-e2edwds`. That ticket's
dwds attach failure is fixed (see its status log — Flutter 3.41.7 resolved
it). This is what is in the way now.

## Acceptance criteria

- [ ] Repro exists (below — reproducible on demand, fails in <30s).
- [ ] Root cause documented with evidence: why `ClientLatencyIngest` is
      resolved on the first-frame path but not registered under
      `E2E_MODE=true`.
- [ ] Fix + regression test. The regression test must fail before the fix —
      a widget/unit test that boots the router under `E2E_MODE=true` is
      enough; it does not require the full driver stack.
- [ ] Flow 01 gets past app launch and its assertions actually evaluate
      (pass or fail on their own merits, not on a crashed router).

## Repro

Requires local Flutter **3.41.7** (`dev/dev-fltup1`) — on 3.38.9 the run
dies earlier at the dwds attach and never reaches this.

```bash
npx nx run e2e:stack-up                  # API healthy at GET /v1/health
<chromedriver-150> --port=4444 &         # must match local Chrome's major
cd app
flutter drive --driver=test_driver/integration_test.dart \
  --target=integration_test/01_app_launch_test.dart -d chrome \
  --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000
```

## Evidence (fltup1, 2026-07-30)

Debug service attaches cleanly first — this is *not* a dwds problem:

```
Waiting for connection from debug service on Chrome...             25.5s
Debug service listening on ws://127.0.0.1:50013/fKozVNQEnc0=/ws
```

Then, during a scheduler callback on the first frame:

```
══╡ EXCEPTION CAUGHT BY SCHEDULER LIBRARY ╞═══════════════════════
The following StateError was thrown during a scheduler callback:
Bad state: GetIt: Object/factory with type ClientLatencyIngest is not
registered inside GetIt.

package:get_it/get_it_impl.dart 682:5   [_findRegistrationByNameAndType]
package:palateful/core/router/app_router.dart 98:32               <fn>
package:palateful/core/services/perf_navigator_observer.dart 87:25 <fn>
package:flutter/src/scheduler/binding.dart 1430:7  [_invokeFrameCallback]
```

The reported second failure is a **consequence, not a separate defect** —
the router never completes, so nothing renders:

```
Expected: at least one matching candidate
  Actual: _TextWidgetFinder:<Found 0 widgets with text "Home": []>
waitFor timed out looking for: Found 0 widgets with text "Home"
  helpers.dart 48:3
```

`flutter test` (the 1564-test widget suite) is **green** on the same commit
and same toolchain, so the gap is specific to the `E2E_MODE=true` boot path
— the suite's harness presumably registers the dependency that the real
`main()` under E2E_MODE does not.

## Technical notes

- Start at `app/lib/core/router/app_router.dart:98` (the `sl<...>()` call
  site) and `app/lib/core/services/perf_navigator_observer.dart:87`, then
  compare against wherever `ClientLatencyIngest` *is* registered for the
  normal boot path — the likely shape is a registration guarded by a flag
  that `E2E_MODE` skips, or ordered after the first frame.
- Prefer fixing registration over making the call site null-tolerant unless
  latency ingest is genuinely undesirable in E2E — swallowing it at the
  call site would hide the same class of bug next time.
- Bounding the driver run is advisable: `flutter drive` hung after the
  suite had already reported its verdict, so wrap it in a timeout.

## Status log

- 2026-07-30T13:00 — filed from `dev/dev-fltup1` AC #5. Surfaced only once
  the Flutter 3.41.7 upgrade let the debug service attach and the test body
  execute for the first time; it was previously masked by the dwds failure.
- 2026-07-30T11:52:25-06:00 — claimed by /devx in session /devx-loop-2026-07-30T17-52-24-754-38586
