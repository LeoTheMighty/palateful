# QA Walkthrough — sbf-1: S3 imports bucket + IAM wiring

**Status:** ready for QA
**Story:** `sbf-1-s3-imports-bucket-and-iam.md`

This is a pure-infra / config story. There is no user-visible surface,
so QA is deployment + terraform-plan review, not a click-through.

## What changed

New `palateful-imports-{env}` S3 bucket + IAM grants + ECS env-var
wiring so that `sbf-2` (presigned upload endpoint), `sbf-3` (`s3_key`
import path), and `sbf-4` (ffmpeg in worker) can all read and write the
bucket. No behavior change in this story.

## Prerequisites

- AWS credentials in your shell (or `aws-vault`) with terraform apply
  rights on the target account.
- `terraform` 1.5+ on `PATH`.
- `poetry` + `nx` installed (for the API test sanity check).

## Checks

### A. Local — should already be green

1. `terraform -chdir=terraform/environments/dev validate` → **Success**.
2. `terraform -chdir=terraform/environments/prod validate` → **Success**.
3. `terraform -chdir=terraform validate` (legacy root) → **Success**.
4. `npx nx run api:lint` → **All checks passed**.
5. From `services/api/`: `DATABASE_URL=postgresql://test/test poetry run
   pytest tests/test_config.py --no-cov -q` → **12 passed**.
   (Running the full test suite requires `DATABASE_URL` set; without it
   every suite has 271 pre-existing pydantic-settings errors unrelated
   to this story.)
6. Full suite: `DATABASE_URL=postgresql://test/test poetry run pytest
   --no-cov -q` → **1685 passed**.

### B. Dev AWS — optional, apply-time smoke

If/when you `terraform apply` the dev env:

1. `terraform -chdir=terraform/environments/dev plan` and confirm the
   only additions are: `aws_s3_bucket.imports`, its versioning, SSE,
   public-access-block, CORS, lifecycle, plus two new outputs. IAM
   should show policy-document updates (imports-bucket grants added to
   `api_service`) and no new roles.
2. After apply, `aws s3api get-bucket-lifecycle-configuration
   --bucket palateful-imports-dev` should return **two** rules: the
   7-day sweep with `NoncurrentVersionExpiration.NoncurrentDays=1` and
   `AbortIncompleteMultipartUpload.DaysAfterInitiation=1`, and the
   `unclaimed=true` 1-day rule with the same noncurrent sweep.
3. `aws iam get-policy --policy-arn $(terraform output
   api_service_policy_arn)` → the default version JSON should include
   the three `S3Imports*` Sids, with `S3ImportsTagging` carrying the
   `ForAllValues:StringEquals` Condition restricting
   `s3:RequestObjectTagKeys` to `["unclaimed"]`.
4. `aws iam get-role-policy --role-name palateful-batch-job-dev
   --policy-name palateful-batch-job-s3-dev` should **NOT** contain any
   reference to the imports bucket (intentional — Batch container is
   the parser, not ffmpeg).

### C. Prod — apply order

Apply dev first, confirm (B), then:

1. `terraform -chdir=terraform/environments/prod plan` — the diff
   should mirror dev: new bucket, updated policy, new ECS env var
   `S3_IMPORTS_BUCKET` on API + Worker task definitions.
2. After apply, a new revision of the API and Worker ECS task
   definitions should be deployed. The running tasks keep the previous
   revision until the next deploy — verify with `aws ecs
   describe-services` that `desiredCount` matches `runningCount` with
   no rollback events.
3. Exec into a running API task and `env | grep S3_IMPORTS_BUCKET` —
   this will show the NEW value only after the next `/deploy` (old
   tasks still run the previous revision). Harmless until `sbf-2`
   lands.

## What NOT to check in this story

- The `/v1/imports/upload-url` endpoint does not exist yet (**sbf-2**).
- Tagging objects with `unclaimed=true` on presign does not happen yet
  (**sbf-2**).
- Reading an S3 object inside `ParseSourceTask` does not happen yet
  (**sbf-3**).
- ffmpeg inside the worker image does not exist yet (**sbf-4**).

If any of these fail as "not implemented," that is expected for this
story. They will be QA'd in their own stories.

## Rollback

Revert the git commit and `terraform apply`. The bucket is empty
(no clients have written to it yet), so destruction is safe — AWS will
happily delete an empty bucket in one step.
