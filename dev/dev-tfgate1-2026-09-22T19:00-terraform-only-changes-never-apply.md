---
hash: tfgate1
type: dev
created: 2026-09-22T19:00:00-06:00
title: Terraform-only changes merge cleanly and are never applied
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: ready
owner: null
branch: null
---

## Goal

`terraform-prod` in `ci.yml` requires `needs.deploy-images.result == 'success'`;
its own comment says *"pure terraform edits → terraform-prod also skips.
Terraform-only changes land via force-deploy.yml."* So any infra-only PR merges,
shows a clean plan, and **is never created**. That's the same class as the §2 outage fix
that merged six weeks early and never shipped.

The documented alternative, `force-deploy.yml`, rebuilds every image from HEAD,
runs the migrator and force-deploys every service, so applying one alarm ships
every undeployed change. It has run **twice (2026-04-16) and failed both times**.

## Acceptance criteria

- [ ] A Terraform-only change to main is applied, against the **currently
      deployed** image tags, so it can't point ECS at a tag not in ECR (the
      reason the gate exists, run 24534239978).
- [ ] Reuse the existing `resolve-tags` job if it already yields the currently
      deployed tags. Reusing it beats adding a second mechanism.
- [ ] **Baseline drift checked before this goes live.** The first gated apply
      picks up *all* pending drift, not just the change that triggered it. A
      read-only `terraform plan` against prod at the deployed tags must show
      nothing worse than what's already known (0a measured: tags plus two
      secret versions, no destroys).
- [ ] **Proven by application, not by a green job.** The failure mode is a job
      that reports success while doing nothing. The proof is the *next*
      Terraform-only merge actually creating a resource; alrt1's SNS topic is
      the planned first test.
- [ ] Until fixed, a merged Terraform-only PR must visibly say it is **not
      applied**. Silent non-application is the failure mode.

## Technical notes

- **Leo's decision (2026-09-22): fix the gate first**, not a targeted manual
  apply and not `force-deploy.yml`. Owner: palateful-0e.
- Found while building alrt1 (obsgap1 follow-up). Blocks the four alert specs'
  "live in prod" ACs unless they're applied another way.
- `force-deploy.yml` never having succeeded is its own finding. It may deserve
  a separate spec once someone reads its two failed runs.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: —.
