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

- 2026-09-22T21:40 — **Leo's answers to the two questions above, and a
  correction to the entry I just wrote.**

  **1. The channel is email via SNS.** That is what he will act on, so the
  SNS email subscription is *the* gate. Consequences: the `palateful-prod-alerts`
  0-subscriptions finding stops being context and becomes the blocking
  prerequisite — nothing else in this story can be verified until a confirmed
  subscription exists. And **SES is not needed**: an SNS email subscription is
  the simpler route to the same inbox, so the "0 verified identities" finding
  is now informational rather than a path to build.

  **2. GitHub Actions email notifications are switched OFF**, deliberately —
  too noisy across his personal and work repos.

  **CORRECTION TO MY 21:10 ENTRY.** I wrote that `deploy-freshness` failed 52
  times "with nobody noticing", which implies inattention. That is wrong, and
  the truth is worse: **that path could not have reached him at all.** The
  watcher was not being ignored; it was shouting into a channel that was
  switched off. I inferred a human cause for a structural one — the same
  mistake as reading a green health check as a healthy database.

  **What this changes in the acceptance criteria.** A scheduled GitHub Action
  is still structurally right as the *watcher* — outside AWS, outside the API,
  outside the DB. But:
  - **Its verdict must leave GitHub** to reach him. Publishing to SNS is that
    exit. A red run in the Actions UI reaches nobody.
  - **"Its own failure must be visible" cannot mean a red run.** That is
    precisely the 52-failure shape. It needs an external heartbeat: something
    that notices the watcher *stopped reporting*, through a channel that is
    not the watcher and not GitHub.
  - So the criterion moves from "the scheduled job goes red" to **"the absence
    of a verdict reaches Leo"**.

  **One concrete mechanism**, offered for whoever builds this rather than
  prescribed: the watcher publishes a heartbeat to the SNS topic on every run,
  pass or fail; a CloudWatch alarm on that topic's `NumberOfMessagesPublished`
  (`< 1` over a window longer than the schedule interval) fires when the
  heartbeat stops. That alarm lives in AWS and alerts by the same email, so it
  is independent of GitHub entirely — it detects a watcher that died, was
  disabled, or lost its credentials, which is exactly how `deploy-freshness`
  failed. It does not require the watcher to be healthy enough to report its
  own failure, which is the property that matters.

  **And the subscription itself has to be watched.** The coordinator's
  original constraint — a confirmed subscription someone later deletes returns
  us to a silent void — means the gate is not "the topic exists" but "the
  topic has a confirmed subscription", checked continuously. A deleted
  subscription is indistinguishable from silence at every layer above it.

- 2026-09-22T22:00 — **ACCEPTED LIMITATION, recorded deliberately rather
  than left implicit.** Leo's call, 2026-09-22.

  > **If the SNS email subscription is deleted, every alert path goes silent
  > simultaneously and nothing warns.** Accepted by Leo on 2026-09-22.

  Why it is a single point of failure and not two paths: with email-via-SNS
  as the primary channel, and the heartbeat alarm above also alerting by
  email, **both terminate in the same inbox via the same subscription.**
  That is genuinely two independent paths against a *dead watcher* — which
  is the failure this story is about, and the one it does cover. It is not
  two paths against a *dead subscription*: that single deletion takes out
  the alert and the alert-about-the-alert together.

  **Mitigation Leo did want:** a periodic check that the subscription still
  exists **and is `Confirmed`** (not `PendingConfirmation`), alerting if the
  count drops to zero.

  **And the same weakness applies to that check**, which is why it is stated
  in the same breath rather than presented as a fix: the subscription-watcher
  alerts *through the subscription it is watching*, so in the exact scenario
  it exists for — the subscription is gone — its alert cannot arrive either.
  What it actually buys is narrower, and worth being precise about:
  - it converts an invisible failure into a **recorded** one, discoverable
    the next time anyone looks, instead of leaving nothing at all;
  - it catches the **`PendingConfirmation`** case, where a subscription was
    created but never confirmed — which looks like coverage in the console
    and delivers nothing;
  - it catches a drop to zero *while some other path still works*, if one is
    ever added.

  It does **not** close the accepted gap. Closing that needs a second channel
  Leo reads, and there is not one today. A limitation that is written down is
  survivable; one that is discovered during an incident is not.
