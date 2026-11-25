---
hash: fdlane1
type: dev
created: 2026-09-22T21:30:00-06:00
title: `force-deploy.yml` doesn't share CI's deploy lane, despite saying it does
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

`force-deploy.yml` says it will *"Share the production-deploy concurrency lane
with CI so a force-deploy and a main-push deploy can't run at the same time"*,
but it uses `group: deploy-production`. CI uses workflow-level
`${{ github.workflow }}-${{ … github.ref }}`. **They are different groups,
so both can deploy to prod at once**, including two Terraform applies against
the same state. It has also **never succeeded**: 2 runs, both 2026-04-16, both
failed (measured).

## Acceptance criteria

- [ ] Put both workflows' prod-mutating jobs in one shared concurrency group
      (job-level on `terraform-prod`, `run-migrator`, `deploy-services`), with
      `cancel-in-progress: false` for applies.
- [ ] Decide whether `force-deploy.yml` should exist at all. Its original
      purpose (landing Terraform-only changes) is tfgate1's job now.
- [ ] If it stays, read its two failed runs and make it succeed once.

## Technical notes

- Cancelling a `terraform apply` mid-run can leave a state lock or a
  partial apply. That's why applies shouldn't be `cancel-in-progress`.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
