---
hash: e2edwds
type: debug
created: 2026-07-27T19:00:00-06:00
title: flutter drive -d chrome cannot attach dwds debug service against Chrome 150
from: dev/dev-bqa102-2026-07-27T11:40-e2e-revival-one-command.md
status: done
---

## Goal

`flutter drive --driver=test_driver/integration_test.dart -d chrome` attaches
its debug service and runs the flow to completion. Today every flow dies with
`AppConnectionException` before the test body executes, which makes the E-2
eval (`evals/e2_e2e_one_command.sh`, two consecutive 8/8 runs) unreachable and
leaves bqa102's headline AC unmet.

## Acceptance criteria

- [x] Repro exists (below — already reproducible on demand).
- [x] Root cause documented with evidence — Flutter-toolchain ↔ Chrome-150
      version skew; see the 2026-07-30 status-log entry.
- [-] Fix + the E-2 eval green: `bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh` exits 0 from `_devx/workstreams`.
      **Fix landed (Flutter 3.41.7 — the attach works). Eval still not
      green**, now blocked by `debug/debug-e2egetit`, a distinct DI defect
      this one was masking. Tracked there, not re-scoped here.

## Repro

Stack up, then a single flow:

```bash
npx nx run e2e:stack-up
cd app
flutter drive --driver=test_driver/integration_test.dart \
  --target=integration_test/01_app_launch_test.dart -d chrome \
  --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000
```

Observed, every time, ~19–21s in:

```
Launching integration_test/01_app_launch_test.dart on Chrome in debug mode...
Waiting for connection from debug service on Chrome...             19.4s
Instance of 'AppConnectionException'
#0  DevHandler._startLocalDebugService (package:dwds/src/handlers/dev_handler.dart:221:7)
#1  DevHandler._createChromeAppServices (package:dwds/src/handlers/dev_handler.dart:303:26)
#2  DevHandler.loadAppServices (package:dwds/src/handlers/dev_handler.dart:275:23)
#3  DevHandler.createDebugConnectionForChrome (package:dwds/src/handlers/dev_handler.dart:587:30)
#4  Dwds.debugConnection (package:dwds/dart_web_debug_service.dart:68:14)
#5  WebDevFS.connect.<anonymous closure> (package:flutter_tools/src/isolated/devfs_web.dart:156:17)
```

## Evidence gathered (bqa102, 2026-07-27)

Hypothesis → check → result, one line each:

- chromedriver/Chrome version mismatch → installed exact-match build
  `chromedriver@150.0.7871.182` via `npx @puppeteer/browsers`, confirmed
  `http://localhost:4444/status` reports `150.0.7871.182` → **not the cause**
  (this *was* a real separate defect — it produced `SessionNotCreatedException`,
  now guarded by the version-aware preflight in
  `services/e2e/scripts/_chromedriver_check.sh`).
- Chrome first-run interstitial blocking page load → re-ran with
  `--web-browser-flag=--disable-search-engine-choice-screen --web-browser-flag=--no-first-run --web-browser-flag=--disable-features=Translate`
  → **identical failure**.
- Stale Chrome device from a prior flow → `pkill -f flutter_tools_chrome_device`
  before every attempt (already in `run_all.sh`), plus the targeted retry
  → **retry fires correctly and fails identically**.
- Transient/flaky → flow 01 *did* pass once (2026-07-27 ~17:08) after a ~5min
  stall, so the path is not categorically broken; it is failing far more often
  than not. Another flow wedged for 53min with no output before being killed.

Leading hypothesis: version skew between the pinned Flutter toolchain and the
installed browser. `flutter --version` → 3.38.9, framework revision
`67323de285`, dated 2026-01-28. Chrome → 150.0.7871.182. `dwds`' Chrome
DevTools Protocol usage is the suspect surface.

## Technical notes

- **First arm of the bisect is now filed as
  `dev/dev-fltup1-2026-07-30T09:00-align-local-flutter-to-ci-pin.md`**: the
  local toolchain is 3.38.9 while CI has been pinned to 3.41.7 since `ach-1`,
  so "upgrade Flutter" is also a drift fix worth doing on its own merits.
  fltup1 is required to answer the dwds question either way and to append its
  result here. If 3.41.7 still cannot drive Chrome 150, this ticket pivots to
  the Chrome-side arm below.
- Remaining arm, if fltup1 comes back negative: try a
  Chrome for Testing 146-line binary via `npx @puppeteer/browsers install
  chrome@146...` with `CHROME_EXECUTABLE` pointed at it, and independently try
  a newer Flutter stable. Whichever moves the needle names the culprit.
- Nothing in the e2e harness itself is implicated: stack lifecycle, health
  gate, auth bypass, DB isolation, teardown-in-trap, exit-code propagation and
  the targeted retry are all verified working in bqa102.
- `E2E_FLOW_TIMEOUT` (default 900s) bounds a wedge — set it lower while
  bisecting to keep iterations cheap.

## Status log

- 2026-07-27T19:17:36-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-28T15:24:17.407Z — [FAIL] loop abandoned e2edwds: 3 consecutive failures on this item; no real work was preserved — bookkeeping-only worktree discarded, item left ready
  - Learning: iteration 1 [FAIL]: No-op iteration: the previous run stalled mid-stream before making any file changes or recording findings on the dwds/Chrome-150 attach failure.
  - Learning: iteration 2 [ERROR]: worker session exceeded the 60min awake-time iteration ceiling and was killed
  - Learning: iteration 3 [FAIL]: No meaningful progress: the iteration ended still waiting on the app build/attach run to produce an outcome (pass, AppConnectionException, or exit), with no file changes and no verified result.
- 2026-07-30T13:10 — **RESOLVED by `dev/dev-fltup1`. Root cause confirmed:
  Flutter-toolchain ↔ Chrome-150 version skew.** The leading hypothesis in
  this spec was right. Upgrading local Flutter 3.38.9 → **3.41.7** (the pin
  CI has used since `ach-1`) makes the debug service attach:

  ```
  Waiting for connection from debug service on Chrome...             25.5s
  Debug service listening on ws://127.0.0.1:50013/fKozVNQEnc0=/ws
  ```

  `grep -c AppConnectionException` over the full run → **0**, where 3.38.9
  failed at ~19–21s inside `DevHandler._startLocalDebugService` on every
  attempt. Same flow (01), same Chrome **150.0.7871.187**, same exact-match
  chromedriver **150.0.7871.182**, same stack — only the toolchain moved.

  Per fltup1 AC #5 this takes the **"attaches"** arm: the Chrome-side arm of
  the bisect is **not** needed, no Chrome for Testing downgrade, and the CI
  pins stay where they are.

  **AC #3 (E-2 eval green) is NOT met, and this ticket is closed anyway** —
  deliberately, because the eval is now blocked by a different defect that
  this one was masking. Once the app actually launched, flow 01 failed on
  `Bad state: GetIt: Object/factory with type ClientLatencyIngest is not
  registered inside GetIt` (`app_router.dart:98` via
  `perf_navigator_observer.dart:87`), which crashes the router on the first
  frame; the follow-on "Found 0 widgets with text 'Home'" is its
  consequence, not a second bug.

  Successor filed as
  **`debug/debug-e2egetit-2026-07-30T13:00-clientlatencyingest-not-registered-in-e2e-mode.md`**
  — that is what bqa102 / the E-2 eval now waits on. Closing this rather
  than re-scoping it keeps the dwds finding (a real, evidence-backed
  toolchain result) from being buried under an unrelated DI bug.
