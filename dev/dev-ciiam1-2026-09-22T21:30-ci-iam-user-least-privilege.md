---
hash: ciiam1
type: dev
created: 2026-09-22T21:30:00-06:00
title: CI's AWS user is effectively admin, on a public repo
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

The IAM user CloudTrail attributes CI actions to, `palateful-github-actions`,
has **`arn:aws:iam::aws:policy/IAMFullAccess`** and
**`arn:aws:iam::aws:policy/PowerUserAccess`** attached (measured,
`list-attached-user-policies`). `IAMFullAccess` lets it grant itself anything,
so in practice it is admin. The repo is **public**, and after tfgate1 every
merged Terraform change runs with these keys.

## Acceptance criteria

- [ ] Enumerate what the deploy path actually calls. `terraform-prod`
      manages many resource types, so derive the list from the Terraform, and
      from CloudTrail for the deploy and migrator jobs. Don't guess.
- [ ] Replace both managed policies with a least-privilege policy. **No
      `iam:*` beyond what the Terraform manages.**
- [ ] Proven by a full deploy *and* a Terraform-only apply succeeding under the
      new policy, plus one denied call the old policy would have allowed.

## Technical notes

- High blast radius: too tight a policy breaks the deploy path. Land it with
  a deploy scheduled right after, not quietly.
- Consider OIDC federation (GitHub → AWS role) instead of long-lived keys in a
  public repo's secrets. That's a larger change, so decide it separately.

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
