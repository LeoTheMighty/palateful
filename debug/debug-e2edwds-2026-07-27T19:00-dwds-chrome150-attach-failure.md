---
hash: e2edwds
type: debug
created: 2026-07-27T19:00:00-06:00
title: flutter drive -d chrome cannot attach dwds debug service against Chrome 150
from: dev/dev-bqa102-2026-07-27T11:40-e2e-revival-one-command.md
status: ready
---

## Goal

`flutter drive --driver=test_driver/integration_test.dart -d chrome` attaches
its debug service and runs the flow to completion. Today every flow dies with
`AppConnectionException` before the test body executes, which makes the E-2
eval (`evals/e2_e2e_one_command.sh`, two consecutive 8/8 runs) unreachable and
leaves bqa102's headline AC unmet.

## Acceptance criteria

- [ ] Repro exists (below — already reproducible on demand).
- [ ] Root cause documented with evidence.
- [ ] Fix + the E-2 eval green: `bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh` exits 0 from `_devx/workstreams`.

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

- Next step is a bisect on the browser/toolchain axis, not on app code: try a
  Chrome for Testing 146-line binary via `npx @puppeteer/browsers install
  chrome@146...` with `CHROME_EXECUTABLE` pointed at it, and independently try
  a newer Flutter stable. Whichever moves the needle names the culprit.
- Nothing in the e2e harness itself is implicated: stack lifecycle, health
  gate, auth bypass, DB isolation, teardown-in-trap, exit-code propagation and
  the targeted retry are all verified working in bqa102.
- `E2E_FLOW_TIMEOUT` (default 900s) bounds a wedge — set it lower while
  bisecting to keep iterations cheap.
