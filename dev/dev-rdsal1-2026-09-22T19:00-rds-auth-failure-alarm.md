---
hash: rdsal1
type: dev
created: 2026-09-22T19:00:00-06:00
title: G2 — alarm on Postgres auth failures (the six-week outage, on minute one)
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

The DB could not authenticate the app from 2026-06-17 to 2026-07-31:
238,258 `password authentication failed` lines in the RDS log, and nothing told a
human (obsgap1 §2). The log already exists and never expires; it only needs
reading.

## Acceptance criteria

- [ ] CloudWatch log metric filter on `/aws/rds/instance/palateful-db-prod/postgresql`
      matching the **anchored** pattern `"FATAL:  password authentication failed"`
      (two spaces), feeding an alarm → `module.alerts.topic_arn`. Not the bare
      phrase: `log_min_duration_statement = 100` writes slow statement text
      into this same log, so a slow SQL query *about* auth failures (e.g.
      `... ILIKE '%password authentication failed%'`) would trip a bare
      filter. 4f tested both against 44 real lines and one labelled synthetic
      line.
- [ ] Threshold per 4f's simulation on the real 5-month series: ≥1 failure in
      **2 of the last 3** five-minute periods. That pages once per episode
      (6/6), 10 minutes after onset, with 0 false pages. "≥5 per 5 min"
      flapped (9 pages for 6 episodes).
- [ ] Filter proven against real lines before it's trusted. Actual line:
      `…:palateful@palateful:[17132]:FATAL:  password authentication failed for user "palateful"`
      (two spaces after `FATAL:`).
- [ ] Alarm driven into ALARM once and the email confirmed received.

## Technical notes

- Being built by **palateful-4f**.
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
