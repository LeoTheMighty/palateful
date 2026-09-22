---
hash: tfpin1
type: dev
created: 2026-09-22T21:30:00-06:00
title: Terraform providers are unpinned under what is now an auto-apply pipeline
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

No `.terraform.lock.hcl` is committed (measured). Every CI run resolves
`hashicorp/aws ~> 5.0` fresh. After tfgate1, **a provider release can change
what an unattended apply does, with no repo change and no review.** The six
zero-diff "updates" in today's baseline plan are the kind of provider-driven
noise this invites.

## Acceptance criteria

- [ ] Commit `terraform/environments/prod/.terraform.lock.hcl`. **Generate it
      with `terraform providers lock -platform=linux_amd64
      -platform=darwin_arm64`.** A lockfile made on a Mac alone has only macOS
      hashes, and CI's `init` on linux_amd64 fails the checksum.
- [ ] Pin the Terraform CLI version in both `terraform-prod` jobs
      (`setup-terraform` with `terraform_version`) to the version that wrote
      state. It's `1.4.2` today (measured, `terraform state pull`).
- [ ] Proven by CI `init` succeeding against the committed lockfile.

## Technical notes

- Provider upgrades then become deliberate PRs, with their plan in the body.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
