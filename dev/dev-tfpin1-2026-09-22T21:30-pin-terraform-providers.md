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
      (`setup-terraform` with `terraform_version`). **CI floats on
      `terraform_version: latest`** (measured in #29's job log). The version
      that last wrote prod state is **`1.16.3`**, read from the **raw** state
      object in S3, so a Terraform release changes the CLI under an unattended
      apply.
- [ ] **Don't use `terraform state pull` to find which version wrote state.**
      It re-stamps the *local* CLI's version when it serializes. This spec's
      first draft read "1.4.2" that way, from the local CLI, while the raw
      object said 1.16.3. Read the object directly:
      `aws s3 cp s3://<bucket>/<key> - | jq .terraform_version`.
- [ ] **Local plans must use the pinned version too.** A 1.4.2 plan against
      state written by 1.16.3 reported **6 spurious in-place updates**
      (ACM cert, ElastiCache, Redis SSM parameter, the **RDS instance**, two
      secret versions), with before, after and sensitivity all identical. They
      vanished under 1.16.3 (`2 add, 0 change`). Under
      auto-apply, a reviewer comparing a local plan against CI's would chase
      phantom drift or, worse, dismiss real drift as "the usual noise".
- [ ] Proven by CI `init` succeeding against the committed lockfile.

## Technical notes

- Provider upgrades then become deliberate PRs, with their plan in the body.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
- 2026-09-22T23:30 — corrected: the CLI version that wrote state is 1.16.3,
  not 1.4.2. The earlier value came from `terraform state pull`, which re-stamps
  the local CLI's version. Proved by a 1.16.3 plan: the six zero-diff updates a
  1.4.2 plan showed are gone. Added the `state pull` trap and the requirement
  for a local/CI version match.
