# MANUAL — Things only you can do

## Imported from BMAD backlog (2026-07-27)

- [ ] **Play Console launch runbook** — execute `ANDROID.md` (single operator, Day 1 signup → Day 3 first tag). Code + store assets landed under `epic-android-play-console-launch` (apl-1..4); the Play Console account, listing paste-ins, Data Safety form, and tester recruitment are human-only steps. Source: legacy DEV.md "MANUAL DOCS" + epic-android-play-console-launch.
- [ ] **iOS share-extension ship steps** — execute `SHARE.md` (App ID + App Group + provisioning profile, Xcode signing for `PalatefulShare`, on-device happy-path validation, device matrix before next TestFlight). Code for sie-1..5 is on main. Source: legacy DEV.md "MANUAL DOCS" + epic-share-ios-extension.


## /devx-init deferred work

- [ ] **devx-init: supervisor-install-deferred** — OS-supervisor install deferred by non-interactive `devx init`
  Bare `devx init` never installs launchd/systemd/Task Scheduler units
  unattended. To install the manager/concierge supervisor, run the
  interactive `/devx-init` flow (or see docs/SETUP.md). Until then,
  `devx manage` / `devx loop` run only while you start them yourself.
  Filed: 2026-07-27T16:00:08.032Z  <!-- devx:init-failure:supervisor-install-deferred -->
