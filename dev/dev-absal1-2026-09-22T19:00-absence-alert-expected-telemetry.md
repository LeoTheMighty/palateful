---
hash: absal1
type: dev
created: 2026-09-22T19:00:00-06:00
title: U3 — alert when an expected signal goes silent
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

The failure class behind both big findings: **the recorder depends on the thing
that broke, so the failure produces silence instead of a signal.** `error_logs`
lives in the DB that was rejecting auth for six weeks. The client mirror needs a
valid token and delivered **zero rows for four weeks** (2026-08-23 → 09-19)
with nobody noticing. G2 catches one instance; this catches the class (4f).

## Acceptance criteria

- [ ] Alert when expected telemetry is absent for N days while `/v1/health`
      reports the API up: `service='client'` rows, or the `BootSmokeTest`
      canary.
- [ ] The detector runs **outside** the thing it watches. An absence alert
      that itself needs the DB or a valid token has the same blind spot.
- [ ] Proven by suppressing the signal once and confirming the alert fires.

## Technical notes

- From clidet1 (palateful-4f), merged-ranking #6.
- **Merging does not apply Terraform.** `terraform-prod` in `ci.yml` runs only
  when `deploy-images` succeeds, so a Terraform-only change merges, plans
  cleanly and is **never created**. See `dev/dev-tfgate1-…`. Whatever route is
  **Decided by Leo (2026-09-22): fix the gate** (tfgate1). **Do not merge this
  until tfgate1 is fixed and proven**, or it merges and silently never exists.
  Do not treat a merged alarm as a live one.
- Publish to `module.alerts.topic_arn` (topic `palateful-prod-alerts`, defined
  in `terraform/environments/prod/alerts.tf`). Put the alarm in **its own file**
  in `terraform/environments/prod/` so parallel alert work doesn't collide.
- **Prove it fires.** An alarm that has never been in ALARM state is a
  configured detector, not a verified one. Drive it into ALARM once (e.g.
  `aws cloudwatch set-alarm-state`) and confirm the email arrives.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: alrt1, tfgate1.
