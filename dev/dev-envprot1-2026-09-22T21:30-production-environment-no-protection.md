---
hash: envprot1
type: dev
created: 2026-09-22T21:30:00-06:00
title: The `production` environment has no protection — every Terraform change now auto-applies with no human gate
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

Measured live (`gh api …/environments/production`): **`protection_rules: []`**
(no required reviewers, no wait timer), **`deployment_branch_policy: null`**,
and `can_admins_bypass: true`.

Two consequences:
1. **After tfgate1 (#36), every Terraform change merged to `main` applies to
   prod automatically, with no human in the loop.** That was acceptable while
   Terraform-only changes silently never applied. It isn't now.
2. **No branch policy means any branch can use the `production` environment**,
   and so its AWS credentials. A workflow run from any branch that names
   `environment: production` receives the prod keys. (Fork PRs don't get
   secrets; branches pushed to this repo do.)

**`force-deploy.yml`'s header says otherwise:** *"GitHub's required-reviewer
approval gate applies to each one — nothing reaches AWS without human
approval."* That's false, and nothing in the repo reveals it. palateful-4f
reached the same finding independently from that header.

## Acceptance criteria

- [ ] Decide, with Leo, what gates prod: required reviewers, a wait timer, or
      an explicit decision to auto-apply. **Record it.** The failure mode is a
      gate that people believe exists and doesn't.
- [ ] Restrict `production` to deployments from `main`
      (`deployment_branch_policy`).
- [ ] Correct `force-deploy.yml`'s header to match reality.
- [ ] Proven by attempting a `production` deployment from a non-`main` branch
      and watching it be refused, not by reading the settings page.

## Technical notes

- If reviewers are required, the `ci.yml` main-push deploy will also wait for
  approval. That changes the "merge = deploy" contract every tab has been
  working to, so decide it deliberately.
- Cross-ref: palateful-4f's clidet1 (same finding, reached from the
  `force-deploy.yml` header).

## Status log
- 2026-09-22T21:30 — filed as tfgate1 follow-up ("merge now, then harden", Leo). Found
  while building tfgate1; each finding measured live, not read from config.
