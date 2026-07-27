# MANUAL — Things only you can do

## Imported from BMAD backlog (2026-07-27)

- [ ] **Play Console launch runbook** — execute `ANDROID.md` (single operator, Day 1 signup → Day 3 first tag). Code + store assets landed under `epic-android-play-console-launch` (apl-1..4); the Play Console account, listing paste-ins, Data Safety form, and tester recruitment are human-only steps. Source: legacy DEV.md "MANUAL DOCS" + epic-android-play-console-launch.
- [ ] **iOS share-extension ship steps** — execute `SHARE.md` (App ID + App Group + provisioning profile, Xcode signing for `PalatefulShare`, on-device happy-path validation, device matrix before next TestFlight). Code for sie-1..5 is on main. Source: legacy DEV.md "MANUAL DOCS" + epic-share-ios-extension.


## Spec-blocking runs

- [ ] **bugsimppho7: capture the vision-eval baseline run** — AC4 of
  `dev/dev-bugsimppho7-*-vision-extraction-eval-suite.md` wants a first
  `vision_extraction` run pasted into the PR description as the
  `field_accuracy` regression baseline. It needs a real `OPENAI_API_KEY`
  and bills 5 live gpt-4o-mini vision calls, so no unattended agent can
  do it. Run from `services/eval/`:

  ```bash
  # 1. The one live run.
  OPENAI_API_KEY=<key> poetry run python -m src.main run \
      --suite vision_extraction --output results/vision-baseline.json

  # 2. Capture it: rewrites baselines/vision_extraction_baseline.json
  #    and prints the PR-pasteable markdown block. No API calls.
  poetry run python scripts/capture_vision_baseline.py \
      --results results/vision-baseline.json --markdown
  ```

  Paste step 2's markdown block into the PR and commit the updated
  `baselines/vision_extraction_baseline.json`. Don't hand-transcribe the
  console table — the capture script is what pins `field_accuracy_avg`
  as the soft regression bar for the future hardening pass.

  Everything else in the suite — evaluator, 0.80 gate, fixtures, docs,
  baseline placeholder + capture script, and 78 offline tests (including
  a seeded end-to-end run through the real `EvalRunner`) — is already
  green without spending anything.

## /devx-init deferred work

- [ ] **devx-init: supervisor-install-deferred** — OS-supervisor install deferred by non-interactive `devx init`
  Bare `devx init` never installs launchd/systemd/Task Scheduler units
  unattended. To install the manager/concierge supervisor, run the
  interactive `/devx-init` flow (or see docs/SETUP.md). Until then,
  `devx manage` / `devx loop` run only while you start them yourself.
  Filed: 2026-07-27T16:00:08.032Z  <!-- devx:init-failure:supervisor-install-deferred -->
