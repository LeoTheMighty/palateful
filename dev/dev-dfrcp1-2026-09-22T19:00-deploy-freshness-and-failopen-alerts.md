---
hash: dfrcp1
type: dev
created: 2026-09-22T19:00:00-06:00
title: G3 + G11 — give deploy-freshness a recipient; alarm on rsh102 failing open
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: in-progress
owner: /devx-2026-09-22T1212-6355
branch: null
---

## Goal

Two working detectors with nobody listening. **deploy-freshness** has correctly
reported a 52-day-stale prod on every scheduled run since 2026-09-20 (4
verdicts) to no one. Before that, 49 runs died at `configure-aws-credentials`
and measured nothing (obsgap1 §1a). **rsh102** fails open with 200 on a broken
pool or an unreachable DB, so after it lands a total DB outage reads
`{"status":"ok"}` (G11, from 0a).

## Acceptance criteria

- [ ] **G3:** deploy-freshness notifies on a red *verdict*: publish to the
      topic or add a failure-notification step. It must distinguish a real
      verdict from the check dying at credentials, since 49 of its runs were
      the latter.
- [ ] **G11:** one metric filter on the phrase **`failing open`** in the API
      log → alarm → topic. All four fail-open branches use it
      (`db_probe.py:252, :270, :277`; `health_router.py:41`). Can only be
      wired once rsh102 is **deployed**.
- [ ] **G11 ships with a test** asserting every fail-open branch emits
      `failing open`, placed beside the filter. The filter makes the phrase a
      contract, and nothing else enforces it: a rewording would silently drop a
      failure mode while every verdict test still passes (0a).
- [ ] Each alert driven once and confirmed received.

## Technical notes

- G11 is blocked by rsh102 being **deployed**, not merged.
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
- 2026-09-22T12:12:19-06:00 — claimed by /devx in session /devx-2026-09-22T1212-6355
