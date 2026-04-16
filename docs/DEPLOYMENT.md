# Deployment

How to ship Palateful to production. The repo has three independently
deployable surfaces — backend, web, and iOS — each with its own script
under `bin/`. None of these require SSH, Xcode UI, or manual console
clicks; everything runs from the CLI on your laptop.

## Backend (API + Worker + Migrator)

```bash
bin/prod-deploy
```

Builds the three Docker images, pushes to ECR with commit-SHA tags,
runs `terraform apply`, executes Alembic migrations, rolls the ECS
services, and blocks until the health check passes. Takes ~5 minutes.

Skip the image build when redeploying unchanged code (e.g. to pick up
a terraform-only change):

```bash
bin/prod-deploy --skip-build
```

### Troubleshooting

- **ECS circuit breaker trips** if tasks churn before passing health
  checks. Clear it with:
  ```bash
  aws ecs update-service --force-new-deployment --cluster <cluster> --service <service>
  ```
- **Tail logs during rollout**: `bin/prod-logs`
- **Exec into a running container**: `bin/prod-console`
- **Check service status**: `bin/prod-status`

## Web (Flutter → Cloudflare Pages)

```bash
bin/prod-web-deploy
```

Builds the Flutter web bundle in release mode and pushes it to
Cloudflare Pages. Live at <https://palateful.app> within a minute or
two of the script finishing.

## iOS (Flutter → TestFlight)

```bash
# 1. Bump the version in app/pubspec.yaml, e.g. 1.0.5+11 → 1.0.6+12
# 2. Build, archive, upload — fully CLI-driven, no Xcode UI needed:
bin/prod-ios-deploy
# 3. Commit the version bump
```

What `bin/prod-ios-deploy` does:

1. Stages `app/.env.prod` as `app/.env` for the duration of the build
   (backed up and restored on exit) so the bundled dotenv asset points
   at `https://api.palateful.app` instead of whatever dev URL your
   working copy has. Also passes `--dart-define=ENV=prod` as a
   belt-and-suspenders second channel.
2. `flutter build ios --release --dart-define=ENV=prod`
3. `xcodebuild ... archive` — produces `build/ios/Runner.xcarchive`
4. Writes an `ExportOptions.plist` pinned to
   `method=app-store-connect` and `destination=upload`
5. `xcodebuild -exportArchive -allowProvisioningUpdates` — uploads
   the archive to TestFlight

TestFlight processing takes ~5–15 minutes after upload before the
build becomes available to testers.

### Xcode Cloud (alternate path)

Pushes to `main` also trigger an Xcode Cloud workflow that archives
and uploads to TestFlight without running `bin/prod-ios-deploy`. The
post-clone hook (`app/ios/ci_scripts/ci_post_clone.sh`) installs
Flutter and stages `.env.prod` as `.env` before `xcodebuild` runs, so
CI builds ship with prod config the same way the local script does.

## Parser (AWS Batch, GPU)

The parser runs on AWS Batch with a GPU instance, not ECS, so it is
**not** part of `bin/prod-deploy`. Deploying means pushing a new image
to ECR and making sure Batch actually picks it up — the second half is
where things go wrong.

```bash
AWS_REGION=us-east-1 npx nx run parser:push
```

Builds `services/parser/Dockerfile.batch`, tags it `:latest`, and
pushes to the `palateful-parser` ECR repository. Takes ~5–10 min;
the HunyuanOCR weights and CUDA base image make this a fat build.

### The revision trap

Batch job definitions are **versioned revisions**, and every
`register-job-definition` call creates a new one. Submitting a job by
name alone (which is what `libraries/utils/utils/services/aws.py`
does) always runs the **highest-numbered active revision**.

Terraform owns rev N with `image = ":latest"`. If anyone runs
`aws batch register-job-definition` out of band — a debugging session,
a one-off script — that creates rev N+1, which becomes the default,
and terraform has no idea. If that rev pins a digest instead of
`:latest`, every subsequent `parser:push` is silently ignored: the
image lands in ECR but Batch keeps running the old digest.

**Always check after deploying**:

```bash
aws batch describe-job-definitions \
  --job-definition-name palateful-parser-job-prod \
  --status ACTIVE \
  --query 'jobDefinitions[].{rev:revision,image:containerProperties.image}' \
  --output table
```

The highest-numbered row **must** point to `palateful-parser:latest`,
not a digest. If it doesn't:

1. Fetch the terraform-owned revision (the one that still has
   `:latest`) as a JSON template.
2. `aws batch register-job-definition --cli-input-json file://...` to
   create a fresh revision with the same config.
3. `aws batch deregister-job-definition` on the stale digest-pinned
   revision so nothing reuses it.

Never pin a digest in a manually registered revision unless you're
deliberately rolling back and you `deregister` it immediately after.

### Verify the new image actually ran

Pushing to ECR is necessary but not sufficient — EC2 instances in the
Batch compute environment may cache images. Confirm a job has run on
the new code by checking the latest log stream:

```bash
aws logs describe-log-streams \
  --log-group-name /aws/batch/palateful-parser-prod \
  --order-by LastEventTime --descending --max-items 1 \
  --query 'logStreams[0].logStreamName' --output text
```

Then `aws logs get-log-events` on that stream and look for whatever
distinguishing output your change added. If the old behavior persists
byte-for-byte (same allocation sizes, same warnings), you're still on
the old image.

### Rollback

Find the previous working image digest in ECR, then register a new
revision pinning that digest and deregister the broken one. This is
the only legitimate reason to pin a digest in a Batch job definition
— and clean it up afterward.

### Known gotchas

- **Batch job role needs `s3:GetObject` on both the inputs and
  outputs buckets.** The outputs bucket holds the manifest the
  container reads at startup. Terraform: `terraform/modules/iam/main.tf`
  under `aws_iam_role_policy.batch_job_s3`. AccessDenied on the
  manifest surfaces to users as the opaque "Photo OCR failed,
  essential container in a task exited".
- **CUDA OOM on large images.** The 16 GB GPU has room for the
  ~7 GB bf16 model plus roughly 6 GB of activations/KV cache.
  Images much above ~1 M pixels can blow that budget on the second
  item in a multi-image manifest because residual allocations from
  the first item aren't released. The parser code now calls
  `torch.cuda.empty_cache()` between items; if OOM returns, the next
  lever is capping image resolution in `process_single`.
- **`max_pixels` / `min_pixels` kwargs on `AutoProcessor`** are a
  Qwen2-VL convention. HunyuanOCR inherits the architecture via
  `trust_remote_code` but the custom processor **may silently ignore
  them** — verify with a log-visible image resize, not by trusting
  the kwargs to take effect.
- **`:latest` caching.** Batch's ECS agent pulls `:latest` fresh when
  an instance has no cached copy, which is most of the time since
  the compute environment scales to zero between jobs. But if you
  see stale behavior right after a push, a stuck EC2 instance is one
  possible culprit — force a new instance by scaling the compute
  environment.

## Terraform (infra-only changes)

For changes that don't need a new container image:

```bash
bin/tf_plan_prod    # preview
bin/tf_update_prod  # apply
```

`bin/prod-deploy` calls these internally as part of the backend flow,
so only run them directly for terraform-only work.

## Pre-deploy checklist

Before any production deploy:

1. `git status` is clean and local `main` matches `origin/main` (push
   first — this session may not have SSH auth).
2. Release notes / version bump committed (iOS specifically — see
   `app/pubspec.yaml`).
3. You know how to roll back: backend redeploys the previous commit
   SHA, web re-runs `bin/prod-web-deploy` from an older commit, iOS
   promotes a prior TestFlight build from App Store Connect.

## Observability post-deploy

- **Backend logs**: `bin/prod-logs`
- **ECS status**: `bin/prod-status`
- **iOS/web crashes**: Firebase Crashlytics console (see
  `app/lib/core/services/error_reporter.dart` for what's captured —
  all uncaught errors plus 5xx API responses tagged with route,
  user id, and HTTP metadata)
