---
hash: alrt1
type: dev
created: 2026-09-22T19:00:00-06:00
title: G1 — the alert push channel: SNS topic + a human who actually receives it
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

Nothing in the live AWS account can push to a human: zero alarms, zero
EventBridge rules, zero metric filters, no Chatbot, and one SNS topic with no
subscribers (obsgap1 §1, measured). **Every other alert publishes here**, so
this goes first. It multiplies every other alert, and without it each one
reports into the void deploy-freshness already fires into.

## Acceptance criteria

- [ ] `terraform/modules/alerts/` defines `aws_sns_topic.alerts`
      (`palateful-prod-alerts`) with outputs `topic_arn` and `topic_name`,
      instantiated as `module "alerts"` in a new
      `terraform/environments/prod/alerts.tf` and exposed as root outputs.
- [ ] **No subscription in Terraform.** The email subscription is created
      **once, by hand**, outside Terraform (being put to Leo, 2026-09-22). The
      repo is public, and so are its Actions logs, so the address must never
      appear in a `.tf` file, a `.tfvars` file, a plan, a PR, a CI log, a commit, or Terraform state.
      That rules out every in-Terraform option. This follows the repo's
      existing `modules/secrets` pattern (Terraform owns the container, a
      human supplies the sensitive value).
- [ ] **Applied by a normal merge once tfgate1 is fixed.** Its appearance in
      AWS is tfgate1's proof, so the two land in sequence.
- [ ] **Subscription confirmed:** AWS emails a confirmation link and delivers
      nothing until it is clicked. Tell the coordinator the moment it is
      pending.
- [ ] **Delivery proven:** one test message published and Leo confirms it
      arrived. A topic with a pending subscription is the detector-into-a-void
      failure this whole initiative exists to prevent.

## Technical notes

- Terraform plan output goes in the PR body in full, with anything that isn't
  a pure add flagged. **The address must not appear in it.**
- **Leo's decision (2026-09-22): he subscribes by hand.** When the topic
  exists, hand him a copy-pasteable step: the console path to the topic's
  *Create subscription* page (protocol: Email), and the equivalent
  `aws sns subscribe --topic-arn <ARN> --protocol email --notification-endpoint`
  with the ARN filled in and **the endpoint left for him to type**. Remind
  him the confirmation email must be clicked. Then send one test publish;
  **his confirmation that it arrived is the proof**, not the topic existing.
- **The subscription is not managed as code.** If it is ever deleted, nothing
  recreates it and every alarm goes back to publishing into a void. **absal1
  (U3) is what would catch that.** Land them together, or one quietly defeats
  the other.
- Owner: palateful-0e.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: tfgate1.
