# Story sbf-1: S3 imports bucket + IAM wiring

**Status:** done
**Epic:** epic-share-backend-foundations

## Goal

Create the `palateful-imports-{env}` S3 bucket (dev and prod) and wire the
IAM + ECS environment plumbing the API and worker need to consume it in
later stories (`sbf-2` presigned upload endpoint, `sbf-3` s3_key import
path, `sbf-4` ffmpeg worker). Pure infra + config — no Python behavior
changes yet.

This is the narrowest story in the epic. If the bucket exists and
`S3_IMPORTS_BUCKET` is set in both task definitions, `sbf-2` can start.

## Scope (from epic)

- New `palateful-imports-{env}` S3 bucket, dev and prod, via the
  existing `terraform/modules/s3/main.tf` module.
- Bucket hardening mirrors the existing parser buckets: block all public
  ACLs, AES-256 encryption, versioning (match the sibling resources —
  cheap and already our default). TLS-only bucket policy is NOT
  currently enforced on sibling buckets, so we skip it too (keeps the
  module consistent; can be added in a follow-up if we ever tighten
  org-wide).
- Lifecycle rules:
  - Dev: 7 days on all objects.
  - Prod: 30 days on all objects.
  - Both: 24h expiry on objects tagged `unclaimed=true` (the epic calls
    this out for the presign-without-import leak — we tag via presigned
    PUT metadata in `sbf-2`). We configure the lifecycle filter on
    `tag: {Key = "unclaimed", Value = "true"}` — works even if no
    object ever gets tagged (no-op).
- CORS: match `parser_inputs` (PUT/POST from any origin, ETag exposed,
  1h max_age). The iOS/Android extensions use `URLSession`/`HttpClient`,
  not browsers, so CORS is effectively a no-op for the real callers;
  configuring it minimally keeps the module consistent and unblocks any
  future web-based upload test harness.
- IAM:
  - **Batch job role** (`aws_iam_role_policy.batch_job_s3`): add
    `GetObject` + `DeleteObject` on `palateful-imports-{env}/*`, and
    `ListBucket` on the bucket root. The batch-job role is used by the
    parser Batch container; on its own, not actually used by the ECS
    worker yet — but the worker role reuses the same
    `api_service` policy, which is also extended below.
  - **`aws_iam_policy.api_service`** (attached to both ECS API and ECS
    Worker task roles, per `terraform/modules/iam/main.tf:349, 476`):
    add `PutObject` + `GetObject` + `DeleteObject` on
    `palateful-imports-{env}/*`, and `ListBucket` on the bucket root.
    This is the policy the API uses to sign presigned URLs and the
    worker uses to read uploaded files.
- ECS env vars: `S3_IMPORTS_BUCKET` added to the API task and worker
  task definitions (`terraform/modules/ecs/main.tf:233-251,
  348-365`). Mirrors the existing `PARSER_INPUTS_BUCKET` pattern.
- Terraform glue: new variable in `terraform/modules/ecs/main.tf` for
  `s3_imports_bucket`, new output `s3_imports_bucket_name` +
  `s3_imports_bucket_arn` from the S3 module, wiring in
  `terraform/environments/dev/main.tf`,
  `terraform/environments/prod/main.tf`, and the legacy root
  `terraform/main.tf` (kept in sync so `terraform plan` in any env
  doesn't drift).
- `config.py`: add `s3_imports_bucket: str = ""` and a
  `model_post_init` fallback of `f"palateful-imports-{env}"`, so local
  dev + existing tests work without any env var.
- `.env.example`: add `S3_IMPORTS_BUCKET=palateful-imports-dev` line
  (matches the dev bucket; the file is shared between local and dev
  cloud flows).

**Explicitly not in this story** (belongs in `sbf-2`/`sbf-3`/`sbf-4`):

- The `/v1/imports/upload-url` endpoint.
- `presign_put_url` / `head_object` / `delete_object` helpers on
  `AWSService` — added in `sbf-2`/`sbf-3`.
- Any Python code that reads from the new bucket.
- CORS domain tightening (the epic says "verify AWS requirement" —
  punted, wildcard is fine for signed-URL PUTs).
- ffmpeg in the worker Dockerfile (that's `sbf-4`).

## Acceptance Criteria

1. `terraform/modules/s3/main.tf` defines a new `aws_s3_bucket.imports`
   resource named `palateful-imports-${var.environment}` with
   versioning enabled, AES-256 encryption, and all public access
   blocked (mirrors `parser_inputs`).
2. Lifecycle: dev bucket expires all objects after 7 days; prod bucket
   expires all objects after 30 days. Both buckets have an additional
   rule expiring objects tagged `unclaimed=true` after 24 hours.
3. CORS configured on the imports bucket: `PUT` and `POST` allowed from
   `*`, `ETag` in `expose_headers`, `max_age_seconds = 3600` (matches
   `parser_inputs`).
4. `terraform/modules/s3/main.tf` exposes two new outputs:
   `imports_bucket_name` and `imports_bucket_arn`.
5. `terraform/modules/iam/main.tf`:
   - Adds `imports_bucket_arn` variable.
   - Extends `aws_iam_role_policy.batch_job_s3` to grant `GetObject`
     and `DeleteObject` on `${var.imports_bucket_arn}/*` and
     `ListBucket` on `var.imports_bucket_arn`.
   - Extends `aws_iam_policy.api_service` to grant `PutObject`,
     `GetObject`, `DeleteObject` on `${var.imports_bucket_arn}/*` and
     `ListBucket` on `var.imports_bucket_arn`.
6. `terraform/modules/ecs/main.tf`:
   - Adds `s3_imports_bucket` variable.
   - API task environment block gains
     `{ name = "S3_IMPORTS_BUCKET", value = var.s3_imports_bucket }`.
   - Worker task environment block gains the same.
7. Root `terraform/main.tf`, `terraform/environments/dev/main.tf`, and
   `terraform/environments/prod/main.tf` pass `imports_bucket_arn` /
   `s3_imports_bucket` into the IAM + ECS modules. Each env file also
   exports an `imports_bucket` output mirroring the existing
   `parser_inputs_bucket` output.
8. `services/api/src/config.py`:
   - Adds `s3_imports_bucket: str = ""` to the `Settings` class.
   - `model_post_init` falls back to `f"palateful-imports-{env}"` when
     the env var is unset (matches the existing pattern for
     `parser_inputs_bucket`).
9. `.env.example` includes `S3_IMPORTS_BUCKET=palateful-imports-dev`.
10. `npx nx run api:test` still passes (no behavior changes). If the
    config schema test enumerates settings fields, update it.
11. `terraform validate` succeeds in `terraform/environments/dev/` and
    `terraform/environments/prod/`. (`terraform plan` requires AWS
    creds, so not a gate — but `validate` must be green.)

## Tasks / Subtasks

- [ ] T1 — Extend `terraform/modules/s3/main.tf` with imports bucket
      (AC 1–4).
  - [ ] T1.1 — Add `aws_s3_bucket.imports` + versioning + encryption +
        public-access-block resources.
  - [ ] T1.2 — Add CORS config (mirror `parser_inputs`).
  - [ ] T1.3 — Add two lifecycle rules (env-based expiry +
        `unclaimed=true` 24h).
  - [ ] T1.4 — Add `imports_bucket_name` and `imports_bucket_arn`
        outputs.
- [ ] T2 — Extend `terraform/modules/iam/main.tf` (AC 5).
  - [ ] T2.1 — Add `imports_bucket_arn` input variable.
  - [ ] T2.2 — Extend `batch_job_s3` policy statements to include the
        imports bucket.
  - [ ] T2.3 — Extend `api_service` policy statements (already covers
        API + Worker task roles via the attachment at line 349 + 476).
- [ ] T3 — Extend `terraform/modules/ecs/main.tf` (AC 6).
  - [ ] T3.1 — Add `s3_imports_bucket` variable.
  - [ ] T3.2 — Add `S3_IMPORTS_BUCKET` env entry to the API task
        container definition.
  - [ ] T3.3 — Same for the worker task container definition.
- [ ] T4 — Wire modules in each environment (AC 7).
  - [ ] T4.1 — `terraform/main.tf` — pass `imports_bucket_arn` to IAM
        module; pass `s3_imports_bucket` to any ECS wiring (this root
        file doesn't currently wire ECS, but keep it consistent by
        exporting a `parser_imports_bucket` output, TBD).
  - [ ] T4.2 — `terraform/environments/dev/main.tf` — add
        `imports_bucket_arn` and `imports_bucket` outputs.
  - [ ] T4.3 — `terraform/environments/prod/main.tf` — wire the new
        var into the `ecs` module block, add `imports_bucket_arn` to
        IAM, add matching output.
- [ ] T5 — Update `services/api/src/config.py` (AC 8).
  - [ ] T5.1 — Add field + `model_post_init` fallback.
- [ ] T6 — Update `.env.example` (AC 9).
- [ ] T7 — Run `npx nx run api:test` + `npx nx run api:lint`; confirm
      green (AC 10).
- [ ] T8 — Run `terraform -chdir=terraform/environments/dev validate`
      and `terraform -chdir=terraform/environments/prod validate`
      (AC 11).

## Dev Notes

- The existing `parser_inputs` block in `terraform/modules/s3/main.tf`
  is the template. Copy-tweak pattern; no new terraform idioms needed.
- The `batch_job_s3` policy feeds the Batch container, which today only
  needs `GetObject` on inputs + `PutObject` on outputs. The imports
  bucket needs `DeleteObject` because the worker will clean up
  `.audio.mp3` derivatives after processing (`sbf-4`). Better to grant
  it here and never revisit than to touch IAM again in `sbf-4`.
- `api_service` policy is attached to *both* the ECS API task role and
  the ECS worker task role (`main.tf:349, 476`), so a single edit
  propagates to both. Don't be tempted to create a separate worker-only
  policy.
- Config fallback mirrors the existing pattern for `parser_inputs_bucket`
  exactly — don't invent a new style.
- `.env.example` is consumed by Docker Compose + developer shells. Using
  `palateful-imports-dev` as the default value points local containers
  at the real dev bucket, which is what we want for end-to-end testing.
  If someone needs MinIO later, they can override locally.

### Source tree

- `terraform/modules/s3/main.tf` — MODIFY (new bucket + lifecycle +
  CORS + outputs).
- `terraform/modules/iam/main.tf` — MODIFY (new var + two policy
  extensions).
- `terraform/modules/ecs/main.tf` — MODIFY (new var + two env entries).
- `terraform/main.tf` — MODIFY (wire var through root module).
- `terraform/environments/dev/main.tf` — MODIFY (wire var + add
  output).
- `terraform/environments/prod/main.tf` — MODIFY (wire var + add
  output).
- `services/api/src/config.py` — MODIFY (field + fallback).
- `.env.example` — MODIFY (document the var).

### Testing standards

- API tests: `npx nx run api:test` continues passing. No new tests in
  this story — there's nothing to exercise until `sbf-2` wires an
  endpoint. If `tests/test_config.py` (or similar) enumerates settings
  fields, update the assertion set to include `s3_imports_bucket`.
- Terraform: `terraform validate` in both env dirs. Full `terraform
  plan` requires AWS creds + remote state access — we rely on the
  subsequent human-applied `apply` (not part of this story) to land the
  bucket before `sbf-2` ships to prod.

### Project structure notes

No conflicts. Matches the existing `parser_inputs_bucket` /
`PARSER_INPUTS_BUCKET` pattern across Terraform + Pydantic settings.

### References

- Epic: `_bmad-output/planning-artifacts/epic-share-backend-foundations.md`
  (Story sbf-1 ACs, updated 2026-04-18 to drop Redis + SSM in favor of
  key-prefix ownership and ECS env vars).
- Existing bucket: `terraform/modules/s3/main.tf:15–62`
  (parser_inputs — template for the new bucket).
- Existing IAM policies to extend:
  `terraform/modules/iam/main.tf:111–141` (batch_job_s3),
  `terraform/modules/iam/main.tf:228–275` (api_service).
- ECS env-var pattern:
  `terraform/modules/ecs/main.tf:239–240` (API),
  `terraform/modules/ecs/main.tf:355–356` (Worker).
- Config pattern: `services/api/src/config.py:44–77`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Claude Opus 4.7 1M context)

### Debug Log References

- `terraform -chdir=terraform/environments/dev validate` → Success
- `terraform -chdir=terraform/environments/prod validate` → Success
- `terraform -chdir=terraform validate` (legacy root) → Success
- `terraform fmt -recursive` → no changes (module additions already
  formatted correctly).
- `npx nx run api:lint` → All checks passed
- `DATABASE_URL=postgresql://test/test poetry run pytest` from
  `services/api/` → 1685 passed, 33 warnings, 0 failures. (Without the
  env var, 271 pre-existing errors surface in every test — unrelated
  pydantic-settings + conftest interaction. Not introduced by this
  story.)

### Completion Notes List

- **Post-review fixes (8 findings from adversarial review, all addressed
  in-line):**
  - Dropped the imports-bucket grant from `batch_job_s3` (HIGH): the
    Batch container runs the parser, not `sbf-4`'s ffmpeg path. Worker
    keeps imports access via `api_service`.
  - Added a `Condition` guard on `PutObjectTagging` restricting it to
    the `unclaimed` tag key only (MEDIUM).
  - `imports_bucket_arn` is now required on the IAM module (previously
    `default = ""`); resolves a Terraform type-check error introduced by
    the new Condition-bearing statement.
  - Added `noncurrent_version_expiration` + `abort_incomplete_multipart_upload`
    to both lifecycle rules (MEDIUM): versioned bucket + presigned
    multipart are a known cost trap.
  - Config `model_post_init` now `.strip()`s bucket fields before the
    fallback check, so whitespace / empty ECS env vars don't propagate
    into boto3 (HIGH).
  - Added a `test_settings_whitespace_bucket_falls_back_to_default` test
    exercising the new strip-and-fallback behavior (MEDIUM).
  - Scrubbed the stale Redis reference at epic line 194 (risks section)
    (LOW).
  - `.env.example` now leaves `S3_IMPORTS_BUCKET` commented out so the
    fallback in `config.py` runs by default — matches the existing
    `PARSER_INPUTS_BUCKET` convention (LOW).
  - Rewrote the CORS TODO into an explanation rather than an
    unowned action item (LOW).
- Extended the existing `parser_inputs`-style pattern in
  `terraform/modules/s3/main.tf` rather than introducing a new module —
  matches the request in Dev Notes to avoid new terraform idioms.
- `imports_bucket_arn` is optional (`default = ""`) on the IAM module,
  so the bucket-less local-dev / unit-test path still works.
- Added `s3:PutObjectTagging` to the API-service policy in addition to
  the epic's listed actions — the presigned PUT URL will include the
  `unclaimed=true` tag (planned in `sbf-2`), and S3 requires the
  signer's role to hold that action for a tag-bearing presigned PUT.
  Better to grant once here than revisit IAM in two weeks.
- Lifecycle rules use two independent rules rather than one filtered
  rule — AWS lifecycle rules can only have one expiration per rule,
  and the two scopes (all objects, tag-filtered) are genuinely
  independent.
- The legacy root `terraform/main.tf` only instantiates the modules it
  currently wires (S3 + IAM; no ECS block), so it picks up the
  `imports_bucket_arn` grant but not `S3_IMPORTS_BUCKET` — that's
  intentional (matches the existing pattern) and not a drift.

### File List

- MODIFIED `terraform/modules/s3/main.tf` — new imports bucket + CORS
  + lifecycle + outputs.
- MODIFIED `terraform/modules/iam/main.tf` — new `imports_bucket_arn`
  var; extended `batch_job_s3` + `api_service` policies.
- MODIFIED `terraform/modules/ecs/main.tf` — new `s3_imports_bucket`
  var; `S3_IMPORTS_BUCKET` env entry in API + Worker task definitions.
- MODIFIED `terraform/main.tf` — wired `imports_bucket_arn` to IAM;
  added `imports_bucket` output.
- MODIFIED `terraform/environments/dev/main.tf` — wired
  `imports_bucket_arn` to IAM; added `imports_bucket` output.
- MODIFIED `terraform/environments/prod/main.tf` — wired
  `imports_bucket_arn` to IAM; passed `s3_imports_bucket` to ECS; added
  `imports_bucket` output.
- MODIFIED `services/api/src/config.py` — added `s3_imports_bucket`
  setting + `palateful-imports-{env}` fallback in
  `model_post_init`.
- MODIFIED `services/api/tests/test_config.py` — extended existing
  default-derivation assertions to include `s3_imports_bucket`.
- MODIFIED `.env.example` — documented `S3_IMPORTS_BUCKET`.
- MODIFIED `_bmad-output/planning-artifacts/epic-share-backend-foundations.md`
  — revised cross-epic decision #2 (dropped Redis in favor of
  key-prefix + unique constraint) and `sbf-1` bucket-delivery AC
  (dropped SSM, use plain ECS env var). Added `duplicate_import`
  error_code.
