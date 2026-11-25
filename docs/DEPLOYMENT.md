# Deployment

How to ship Palateful to production. The repo has three independently
deployable surfaces — backend, web, and iOS — each with its own script
under `bin/`. None of these require SSH, Xcode UI, or manual console
clicks; everything runs from the CLI on your laptop.

## Backend (API + Worker + Migrator)

### CI (standard path)

Pushing to `main` triggers the full pipeline automatically:

1. **CI** (`.github/workflows/ci.yml`) — lint, test, model checks
2. **Deploy** (`.github/workflows/deploy.yml`) — triggered when CI
   passes, gated by manual approval in the GitHub "production"
   environment

The deploy workflow uses NX affected detection to only build images,
run migrations, and force-deploy ECS services for projects that
actually changed. Unchanged services keep their existing image tags.

To deploy, just push to `main` and approve in GitHub when prompted.

### Manual deploy (emergency / ASAP)

When you can't wait for CI or need to bypass the pipeline:

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

1. Reads the version from `app/pubspec.yaml` and prints it. **It does
   not bump it** — the script's last line is a reminder to commit the
   bump by hand, and that is how App Store Connect ended up eleven
   builds ahead of the repo. Check App Store Connect's latest build
   number and bump past it *before* running this.
   (Prod config needs no staging: `API_BASE_URL` / `AUTH0_*` are
   compile-time constants in `app/lib/core/config/environment.dart`
   whose defaults are the prod values. The `.env.prod` staging step
   described here previously was removed in `5f13ad7f`, 2026-04-23,
   when `flutter_dotenv` was dropped.)
2. `flutter build ios --release`
3. `xcodebuild ... archive` — produces `build/ios/Runner.xcarchive`
4. Writes an `ExportOptions.plist` pinned to
   `method=app-store-connect` and `destination=upload`
5. `xcodebuild -exportArchive -allowProvisioningUpdates` — uploads
   the archive to TestFlight

TestFlight processing takes ~5–15 minutes after upload before the
build becomes available to testers.

### Xcode Cloud — the CI path

**One rule governs everything here:**

> Branch: `main` · Files and Folders:
> **"Start if 'pubspec.yaml' file from the 'app' folder changes"**

That is the start condition, verbatim, read from App Store Connect on
2026-09-20. **It exists nowhere in this repository** — no workflow file,
no config, no trace beyond `app/ios/ci_scripts/`. Nothing you can grep
will tell you it is there, which is why it is written down here.

#### What it means in practice

**A TestFlight build ships when — and only when — a commit landing on
`main` changes `app/pubspec.yaml`.** Not when `app/lib` changes. Not
when the Xcode project changes. Only that one file.

This is deliberate and it is a good rule: "bump the version, ship a
build." Firing on every Dart merge would burn an App Store Connect
build number and notify every tester each time.

But it has a sharp edge, and it cost a day to find:

> **If you bump the version locally and do not commit it, the build you
> just uploaded is invisible to `main`, and Xcode Cloud never fires.**

`bin/prod-ios-deploy` does not bump or commit anything. It reads the
version, archives, uploads, and prints `Don't forget to commit the
version bump!` — a reminder, not a guard. Run it a few times without
committing and App Store Connect silently drifts ahead of the repo.

**That is exactly what happened.** By 2026-09-20 ASC was at build 88
while `app/pubspec.yaml` said 77 — eleven local uploads whose bumps
never reached git. Then the repo froze on 2026-04-26, `app/pubspec.yaml`
stopped changing entirely, and the trigger had nothing left to fire on.
Three symptoms that looked unrelated — the eleven-build gap, no builds
since 88, and "it was all working at some point" — were one cause. The
pipeline was never broken. It was starved of its input.

So: **committing the bump is not bookkeeping, it is the deploy
trigger.**

#### How to tell whether it actually ran

The part every other artifact left out. Do not reason from
configuration — a screen that looks right is what this document
asserted, wrongly, for seven weeks.

**Xcode Cloud reports through the GitHub commit-statuses API, not
check-runs.** It therefore never appears in the PR checks list, in
`gh pr checks`, or anywhere in the GitHub Actions UI. If you look for
it there you will find nothing, whether or not it ran.

```bash
# Did Xcode Cloud fire for a given commit?
gh api repos/LeoTheMighty/palateful/commits/<sha>/status \
  --jq '.statuses[] | "\(.state)\t\(.context)\t\(.description)"'
# -> pending|success|failure  "palateful | Prod Deploy"  ...
# -> no rows at all = it never fired (check: did the commit touch app/pubspec.yaml?)
```

The `target_url` on that status links straight to the build log in App
Store Connect, which is the only place the log lives.

Cross-check the outcome in **App Store Connect → TestFlight → Builds**:
if the highest build number predates recent pushes to `main`, it is not
running, regardless of what any configuration screen says.

#### Repo-side scaffolding

- `app/ios/ci_scripts/ci_post_clone.sh` — installs the **pinned**
  Flutter (`FLUTTER_VERSION`, kept in step with `ci.yml` and
  `mobile-builds.yml`; this is the third pin site), then `pub get`,
  `pod install`, share-extension lint and unit tests.
- `app/ios/ci_scripts/ci_post_xcodebuild.sh` — asserts
  `PalatefulShare.appex` is embedded (hard failure: a missing extension
  ships a silently broken feature), then uploads dSYMs to Crashlytics
  (soft failure: symbolication is not worth a release).

Apple requires these to sit adjacent to the `.xcworkspace`, which is
why they live under `app/ios/` rather than with the rest of CI.

#### Manual fallback

`bin/prod-ios-deploy` still works and is the documented escape hatch —
it shipped builds 78–88. Use it when CI is unavailable, but **commit
the version bump**, or you reopen the drift described above. A CI path
with no manual fallback would be worse; a manual path that silently
desynchronises the repo is the thing to watch for.

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
