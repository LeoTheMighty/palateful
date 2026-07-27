# MANUAL — Things only you can do

## Imported from BMAD backlog (2026-07-27)

- [ ] **Play Console launch runbook** — execute `ANDROID.md` (single operator, Day 1 signup → Day 3 first tag). Code + store assets landed under `epic-android-play-console-launch` (apl-1..4); the Play Console account, listing paste-ins, Data Safety form, and tester recruitment are human-only steps. Source: legacy DEV.md "MANUAL DOCS" + epic-android-play-console-launch.
- [ ] **iOS share-extension ship steps** — execute `SHARE.md` (App ID + App Group + provisioning profile, Xcode signing for `PalatefulShare`, on-device happy-path validation, device matrix before next TestFlight). Code for sie-1..5 is on main. Source: legacy DEV.md "MANUAL DOCS" + epic-share-ios-extension.


## irrd-3a — confidence eval calibration gate

- [ ] **Run the opt-in confidence gates and commit the baselines** — the gate
  wiring, both metrics, and the CLI are on `feat/dev-irrd3a`, but the numbers
  themselves need a real LLM run: `OPENAI_API_KEY` + ~10 minutes. No key is
  available to the loop, and `services/eval/.env.eval` does not exist in the
  worktree.

  ```bash
  cd services/eval && cp .env.eval.example .env.eval  # add OPENAI_API_KEY

  # 1. Capture the PRE-confidence title baseline (AC11 needs a "before").
  EXTRACTOR_EMIT_CONFIDENCE=false npx nx run eval:confidence-gate -- --write-baseline

  # 2. Re-run with the confidence prompts on. Exit 1 = a gate failed.
  EXTRACTOR_EMIT_CONFIDENCE=true npx nx run eval:confidence-gate
  ```

  Step 2 fails in one of two ways, each self-describing in the run output:
  calibration MAE > 0.3 → the report's `AC9 retune` block prints the exact
  `_W_INGREDIENTS` / `_W_TITLE` / `_W_STEPS` values to paste into
  `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py`
  (searched offline against the run's own samples, so no extra API spend),
  and the projected MAE they reach — apply them and re-run to confirm; title
  F1 more than 5% below the step-1 baseline → retune the confidence-emitting
  prompts (AC11).
  Commit the regenerated `services/eval/baselines/*.json` with whatever change
  made them pass. Everything deterministic is already covered by
  `npx nx run eval:test` — this step is only about the real numbers.

## /devx-init deferred work

- [ ] **devx-init: supervisor-install-deferred** — OS-supervisor install deferred by non-interactive `devx init`
  Bare `devx init` never installs launchd/systemd/Task Scheduler units
  unattended. To install the manager/concierge supervisor, run the
  interactive `/devx-init` flow (or see docs/SETUP.md). Until then,
  `devx manage` / `devx loop` run only while you start them yourself.
  Filed: 2026-07-27T16:00:08.032Z  <!-- devx:init-failure:supervisor-install-deferred -->
