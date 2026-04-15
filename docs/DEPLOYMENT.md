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
