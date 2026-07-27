---
hash: rsh104
type: dev
created: 2026-07-27T12:33:00-06:00
title: EventBridge rule + Lambda infrastructure for rotation redeploy
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: ready
owner: null
branch: feat/dev-rsh104
---

## Goal

The first Lambda and the first EventBridge rule in this repo. Separated from
rsh103 because its risk is entirely different: not "does the code work" but
**"does the rule ever fire"**. An `ENABLED` rule with a non-matching pattern
is indistinguishable from a working one — the same silent failure this
workstream exists to remove.

**Deadline: 2026-07-29.**

## Acceptance criteria

- [ ] The real `Secret Label Updated` event JSON is captured or confirmed and
      recorded in this status log. If unconfirmable, switch to the CloudTrail
      `RotationSucceeded` pattern (observed 2026-07-21T21:29:14 in this
      incident) and say so explicitly.
- [ ] `terraform/modules/rotation-redeploy/{main.tf,variables.tf,outputs.tf}`
      exist: `aws_cloudwatch_event_rule` scoped to the secret ARN and the
      `AWSCURRENT` label move; `aws_lambda_function` (runtime `python3.13`,
      handler `rotation_redeploy.handler`) packaged via `data "archive_file"`
      (`source_file`); `aws_cloudwatch_event_target`; `aws_lambda_permission`;
      an execution role with `ecs:UpdateService` + `ecs:DescribeServices` on
      the two service ARNs, plus CloudWatch Logs.
- [ ] `archive = { source = "hashicorp/archive" }` declared in
      `required_providers` (`terraform/environments/prod/main.tf:6-11` has only
      `aws` today) and the regenerated `.terraform.lock.hcl` committed.
- [ ] Module wired into `terraform/environments/prod/main.tf`, consuming
      `module.rds.db_master_secret_arn` (already an output at
      `modules/rds/main.tf:235-238`) and both service ARNs.
- [ ] `terraform fmt -check -recursive terraform/` passes; `terraform init`
      succeeds against the committed lock with **no lock mutation**.
- [ ] `terraform plan` output pasted into this status log, reviewed, confirmed
      to contain only this module's resources.
- [ ] **End-to-end proof, not just existence**: a published test event (or a
      forced rotation) produces a Lambda invocation and **two**
      `ecs:UpdateService` calls, visible in CloudWatch Logs / CloudTrail. An
      `ENABLED` rule alone is not a passing criterion.
- [ ] The actual event JSON that matched is recorded in this status log.
- [ ] The Lambda zip contains exactly one `.py` file at the zip root.
- [ ] The resulting deployments settle and the circuit breaker did not roll
      back.

## Technical notes

- **This story is Terraform-only, so CI will not apply it.**
  `terraform-prod` requires `deploy-images.result == 'success'`
  (`ci.yml:703-705`), and `deploy-images` skips when `services_to_build` is
  `[]` (`ci.yml:641-643`); the `ci.yml:698-701` comment says so outright.
  Apply via **Actions → Force Deploy** (`workflow_dispatch`,
  `force-deploy.yml`), which rebuilds all four images at HEAD, applies
  terraform, and carries its own `environment: production` reviewer gate.
- **CI will not validate this module either.** `ci.yml:442-448` runs
  `terraform init`/`validate` against `terraform/environments/dev`, which
  declares only vpc/s3/ecr/iam/batch — no rds, no ecs, and it will never see
  `rotation-redeploy`. Only `terraform fmt -check -recursive`
  (`ci.yml:439-440`) covers the new files. **Reviewing the plan output at
  apply time is the real gate.**
- The runtime + handler string come from rsh103's status log — consume, don't
  invent.
- Both ECS services run a deployment circuit breaker with rollback
  (`modules/ecs/main.tf:366-369`, `:468-471`).
- The 90-day rotation cadence already applied in rsh102 — do not expect it
  here.
- E-5 is validated by rsh103's unit tests; this story's verification type is
  **human** (live event → Lambda → two UpdateService calls).
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 4.

## Status log

- 2026-07-27T12:33 — emitted from plan 462355 at RED-gate PASS. Carried in
  from the Plan stage: the `Secret Label Updated` event shape is still
  unconfirmed (blocks E-5, P0) — this story's first AC owns it, with the
  CloudTrail `RotationSucceeded` signal as the proven fallback.
