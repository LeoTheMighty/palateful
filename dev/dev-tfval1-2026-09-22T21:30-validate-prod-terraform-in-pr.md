---
hash: tfval1
type: dev
created: 2026-09-22T21:30:00-06:00
title: PR CI validates Terraform only for the dev root, so prod-only files are never checked before merge
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

The `terraform` CI job runs `fmt -check -recursive` on all of `terraform/`, but
**`init -backend=false` and `validate` only in `terraform/environments/dev`**
(`ci.yml:464-469`, measured). Files that exist only in the prod root, such as
`alerts.tf` and every `alarm_*.tf`, are formatted but **never validated before
merge.** After tfgate1, a broken prod file merges and then fails the
unattended apply on `main`. **This affects every alarm PR in flight.**
Found by palateful-4f.

## Acceptance criteria

- [ ] Run `init -backend=false` and `validate` for `terraform/environments/prod`
      in PR CI. It needs no credentials: `-backend=false` doesn't touch state.
- [ ] Proven by a deliberately invalid prod-only file failing PR CI.
- [ ] Optionally, a read-only `terraform plan` in PR CI against prod state,
      which needs credentials, so weigh it against envprot1/ciiam1. The
      alarm PRs have been doing this by hand.

## Technical notes

- Cheapest item here and the most immediately useful: land before the alarm
  PRs if possible.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
