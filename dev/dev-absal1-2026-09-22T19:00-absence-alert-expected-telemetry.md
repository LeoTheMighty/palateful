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
  **Read the 2026-09-22T21:10 status-log entry before relying on this**: as
  of today there is no email to arrive — `palateful-prod-alerts` has 0
  subscriptions and SES has 0 verified identities, so "drive it to ALARM and
  confirm the email" currently confirms nothing.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: alrt1, tfgate1.

- 2026-09-22T21:10 — **recon from palateful-0a (rsh102/logconn1), read-only,
  no writes.** Requested by the coordinator so it isn't lost in messages.
  Ownership unchanged: this story is 30's. Everything below is measured.

  **1. `palateful-prod-alerts` is unwired at BOTH ends.**

      SNS topics            : dynamodb (0 subs), palateful-prod-alerts (0 subs)
      CloudWatch alarms     : ZERO in the account

  The 0-subscriptions half is known. The other half is that **nothing
  publishes into it either** — there are no alarms at all. So it is not "a
  channel nobody listens to", it is a channel with no speakers and no
  listeners. The ACs above say to publish to `module.alerts.topic_arn` and
  then "confirm the email arrives". Today that publish reaches nobody, and
  there is no email. Both need a subscription to exist first.

  **2. SES looks like a working path and sends nothing.**

      sendingEnabled        : true
      ProductionAccessEnabled: true        <- out of the sandbox
      verified identities   : ZERO         <- (v1 and v2 both empty)

  Production access without a verified identity sends nothing. Same shape as
  the topic: existence mistaken for capability.

  **3. The only non-AWS path already in production is FCM push**
  (`libraries/utils/utils/services/push_notification.py`,
  `FIREBASE_CREDENTIALS_JSON`). It works and is independent of SNS and
  CloudWatch entirely — but it **routes through the API service**, so it
  shares a blast radius with much of what is worth alerting on. Independent
  of SNS is not the same as independent of the thing being watched. It only
  qualifies if invoked from outside the API.

  **4. The argument for this story's acceptance criteria.** The
  outside-AWS watcher this story needs *already exists here*:
  `deploy-freshness.yml`, scheduled, in GitHub Actions — structurally the
  right shape, independent of SNS, CloudWatch and the API.

  It failed **52 times against 2 successes**, every scheduled run for over a
  month, dying at `configure-aws-credentials` before ever reaching its
  measure step, and nobody noticed (measured by palateful-0e; run history
  confirmed independently during rsh102's deploy verification).

  So the independent path was built, ran daily, and was silently ineffective
  for weeks. That is this story's own failure class, already realised, in
  this repo. It argues the AC has to be stronger than "the alert fires":
  **the alert must ARRIVE, at a human, and its own failure must be visible.**
  A scheduled job red-lighting daily into an unread inbox is the same silent
  void as a topic with 0 subscriptions, wearing different clothes.

  **Two questions no AWS inspection can answer** (with Leo via the
  coordinator): which channel does he actually read — everything in the
  account today is one nobody reads — and do GitHub Actions failure
  notifications reach him at all? The 52 unnoticed failures suggest not, and
  if they don't, GitHub cannot be the fallback either.

  **On the "don't publish failure into the channel you watch" constraint:**
  the test has to be *break the channel, confirm the alert still arrives by
  the independent path* — in both directions — not "the code has a second
  path". Every path above currently fails that test, because there is no
  second path yet.
