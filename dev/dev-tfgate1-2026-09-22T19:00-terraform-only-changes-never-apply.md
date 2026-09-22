---
hash: tfgate1
type: dev
created: 2026-09-22T19:00:00-06:00
title: Terraform-only changes merge cleanly and are never applied
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: done
owner: palateful-0e
branch: feat/dev-tfgate1
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
- 2026-09-22T21:00 — **built and verified locally; the real proof comes after merge.**
  - **The fix.** `detect-changes` emits `terraform` (true when the `terraform`
    nx project is affected). `terraform-prod` now runs when images were built
    (unchanged path, HEAD_SHA tags) **or** when `deploy-images` was skipped
    **and** Terraform changed. In that second case it applies against the image
    tags production is running, which `tools/resolve-deployed-image-tags.sh`
    reads from AWS.
  - **`resolve-tags` can't be reused**: all four of its outputs are
    `${{ github.sha }}`. Feeding HEAD_SHA to an infra-only apply is exactly the
    CannotPullContainerError the gate prevents. It stays for the images-built
    path.
  - **`!cancelled()` is load-bearing**: a job whose `needs` include a skipped
    job is itself skipped unless its `if` contains a status function. Without
    it, the fixed gate would still skip silently in the case it exists for.
    The failure path is unchanged: a failed or cancelled `deploy-images` is
    neither `success` nor `skipped`. `needs.resolve-tags.result == 'success'`
    also keeps `terraform-prod` off whenever tests, lint or `detect-changes`
    fail.
  - **Resolver, run live and read-only:** all four tags came back as
    `848311af…`, matching `bin/prod-status`. It fails loudly on anything that
    isn't a 40-hex SHA.
  - **CI's IAM can run it:** `simulate-principal-policy` for
    `palateful-github-actions` returns *allowed* for `ecs:DescribeServices`,
    `ecs:DescribeTaskDefinition` and `batch:DescribeJobDefinitions`.
  - **nx, measured rather than assumed:** this PR's own diff (`ci.yml` +
    `tools/`) affects **no** project, so merging it triggers no deploy and no
    apply. A Terraform-only file affects exactly `terraform`. Control: a
    service file affects `api`.
  - **Baseline drift, the AC — the first answer here was WRONG; corrected
    2026-09-23.** It read: *"0 add, 6 change, 0 destroy … zero-diff updates …
    State was written by Terraform 1.4.2, the same version as the local run,
    so version skew isn't the cause."* **Version skew was exactly the cause.**
    - **There is no baseline drift.** Under Terraform **1.16.3**, the version
      CI runs, a read-only plan at the deployed tags on plain `main` is
      **`No changes. Your infrastructure matches the configuration.`**
    - The six in-place updates (ACM cert, ElastiCache RG, Redis SSM param,
      **RDS instance**, two secret versions) are what **Terraform 1.4.2**
      plans against state written by 1.16.3. Before, after and sensitivity are
      identical on all six; they vanish under 1.16.3.
    - **How the wrong claim was made:** `terraform state pull` **re-stamps the
      local CLI's version** when it serializes, so it reported "1.4.2" — my own
      CLI, not the writer. The **raw** S3 object says `1.16.3`. Read the writer
      with `aws s3 cp s3://palateful-terraform-state/prod/terraform.tfstate - |
      jq .terraform_version`, never `state pull`.
    - **Corroborated by CI, not just locally:** #29's real `terraform-prod`
      (same provider v5.100.0) planned `3 add, 3 change, 3 destroy` — all
      image-driven — and **never touched the six**.
    - **palateful-4f independently "confirmed" the six and was also wrong**,
      because both plans came from the same 1.4.2 CLI. **Two readings sharing
      one instrument error agree on the error.**
    - What stands: **no ECS task definition, service or Batch job definition
      appears**, confirming the resolver matches what is applied. Providers
      are not locked (no `.terraform.lock.hcl`), so each CI run resolves
      `aws ~> 5.0` fresh; today 5.100.0. See **tfpin1**.
- phase 4: single-pass adversarial review of the `ci.yml` diff. **1 HIGH, fixed:**
  the first draft set the four `*_TAG` values in the job-level `env:` *and*
  overrode them from a step via `$GITHUB_ENV`. If a job-level `env:` value
  takes precedence over `$GITHUB_ENV`, the Terraform-only path would have
  applied HEAD_SHA tags for images that were never built. I wasn't certain of
  the precedence, so I removed the dependence on it: the job no longer defines
  the tags, and one step ("Resolve image tags") is their only writer on both
  paths. Re-reviewed: no job-level `*_TAG` remains, 11 consumers, all read it.
  `actionlint` shows the same 3 findings as `main` (SC2086 ×2, SC2129 ×1, none
  on changed lines), so none are new.
- Found along the way, out of scope and not fixed here:
  - **`force-deploy.yml`'s comment is false.** It says it "shares the
    production-deploy concurrency lane with CI", but it uses group
    `deploy-production` while CI uses a per-ref group, so the two can run
    concurrently. It has also never succeeded (2 runs, both 2026-04-16).
  - **Providers are unpinned under what is now an auto-apply pipeline.** Any
    merge can apply with an `aws` provider version nobody has run. Committing
    a lockfile must include `-platform=linux_amd64` hashes, or CI's `init`
    fails on checksum.
  - **The CI IAM user has `IAMFullAccess` + `PowerUserAccess`**, which is
    effectively admin, on a public repo.
- **PROVEN 2026-09-23 — `done`.** Merging #36 changed nothing in prod, as
  predicted (its main run 35759724879 skipped `terraform-prod`; verified it
  skipped for the *right* reason, `Affected projects:` empty → `terraform=false`,
  not a missing output). Then **alrt1 (`b1986ee5`) became the first
  Terraform-only change ever applied by this repo's CI.** Run **35764133052**:
  1. `detect-changes` → **`Affected projects: terraform`**
  2. `deploy-images` → **skipped**
  3. `terraform-prod` → **ran**, and used the **deployed** tag:
     `api_tag=8d6b1329…` while HEAD was `b1986ee5`. This is the branch that had
     never executed, and the one that would have pointed ECS at an unbuilt
     image. Checking the tag against HEAD is the check that catches a rollback.
  4. **`Apply complete! Resources: 2 added, 0 changed, 0 destroyed.`** — exactly
     the pre-merge plan
  5. **`arn:aws:sns:us-east-1:592349850338:palateful-prod-alerts` exists in
     AWS**, with its CloudWatch publish policy.

  Before this, a Terraform-only change merged, planned cleanly and silently did
  nothing — the mechanism that stranded `e74303f3`'s health-probe fix behind
  the April freeze while the credential outage ran for three more months.
- **Landed by hand, not via `devx devx-helper claim`.** The helper creates the
  worktree and branch as part of claiming, and both already existed from
  building the fix, so it would have failed at its worktree stage. There is
  therefore **no claim commit** for tfgate1; the spec frontmatter and the
  DEV.md row were set directly. Recorded so the next reader doesn't read the
  missing claim as drift.
