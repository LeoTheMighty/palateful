---
hash: prsal1
type: dev
created: 2026-09-22T19:00:00-06:00
title: Client parse-failure alert — a contract break has no legitimate volume floor
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

The cart was broken for months: `GET /v1/shopping-lists/{id}` returns 200,
and the client crashes parsing `quantity` (a Decimal serialized as a string).
Every server detector is blind by construction. The only trace was a client
`_TypeError` with 2 hits, which is indistinguishable from noise, and it's Leo's
personal traffic, so any count threshold never trips (cc, clidet1).

## Acceptance criteria

- [ ] Alert on **any** client type-cast failure in an API-response
      deserialize path, regardless of count.
- [ ] Also fires on **recurrence** after a fix. The May fix (`a5c84386`)
      patched a class nothing imports and ran in prod for four months doing
      nothing.
- [ ] Driven once and confirmed received.

## Technical notes

- From clidet1 (palateful-4f), merged-ranking #4.
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
