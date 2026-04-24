<!-- refined via party-mode 2026-04-18 -->
# Epic: Android CI Hardening

## Locked cross-epic decisions (inherited — do not re-litigate)

1. **Contact email v1: `leonid@ac93.org`** (from `epic-android-privacy-policy-page`).
2. **Privacy policy live at `https://palateful.app/privacy` before anything else ships** (from `epic-android-privacy-policy-page`).
3. **`assetlinks.json` ships with placeholder SHA-256**; real fingerprint committed after first manual AAB upload (from `epic-android-release-hardening`).
4. **Adaptive icon via `flutter_launcher_icons` package**, single source PNG at `app/android/play-store-assets/icon-source-1024.png` (from `epic-android-release-hardening`).
5. **Single GCP service account for CI** holds: Play Console release-manager + Firebase Crashlytics upload + Firebase Test Lab permissions (from `epic-android-release-hardening`). Stored as GitHub Secret `FIREBASE_SERVICE_ACCOUNT_JSON`; reused as the Play Store upload key unless scoped-down rotation is worth it later.
6. **Cook timers keep SCHEDULE_EXACT_ALARM** — no CI validation gate on this (decision is owned by Play Console review, not repo-side).

## Added by this workshop

- **Crashlytics symbol upload happens via the Gradle plugin**, not a separate Fastlane step. The existing `id("com.google.firebase.crashlytics")` plugin auto-uploads mapping + native symbols when (a) `firebaseCrashlytics { mappingFileUploadEnabled = true; nativeSymbolUploadEnabled = true }` is in `buildTypes.release` (wired by `arh-5`), and (b) the build process has `GOOGLE_APPLICATION_CREDENTIALS` pointing at a JSON with Firebase access. The CI wire-up is one `google-github-actions/auth@v2` step that exports `GOOGLE_APPLICATION_CREDENTIALS`. No Fastlane `upload_symbols_to_crashlytics` call needed. Story `ach-3` becomes trivial.
- **Concurrency guard on the Android build** — `concurrency: { group: mobile-builds-android, cancel-in-progress: false }` on the `android-build` job so a duplicate tag push (common with `git tag` typos + amend) serializes instead of racing for the same Play Console version-code slot. No cancel-in-progress — we don't want to kill an in-flight Play Store upload.
- **Plugin-compatibility scan before unifying Flutter channel** — the repo currently builds on `channel: master` because some plugin (likely `cloud_firestore` or `receive_sharing_intent`) required a newer engine. Story `ach-1` starts with a 15-minute audit: run `flutter pub outdated` + `flutter pub deps` on the target stable version; if any plugin pins master, either (a) upgrade the plugin, (b) choose a later-stable Flutter version that covers it, or (c) pin the plugin to a commit that works on stable. **Do not silently revert to master** — the CI/stable divergence bug is the whole reason this story exists.
- **`::notice::` the Play Store build link on success** — at the end of the `android-build` job, emit `echo "::notice title=Play Store Internal Track::Build v$VERSION uploaded. Review at https://play.google.com/console/u/0/developers/..."`. Saves the operator a click. Documented in ANDROID.md.
- **Firebase Test Lab auth path**: use `google-github-actions/auth@v2` + `google-github-actions/setup-gcloud@v2` (idiomatic 2026 auth flow; replaces the old `gcloud auth activate-service-account`). Reuses `FIREBASE_SERVICE_ACCOUNT_JSON`.
- **No end-to-end test of "tag triggers Play upload"** pre-production. The first real tag push *is* the verification — YOLO acceptance criteria. This is explicitly captured in `ach-6`'s AC so later reviewers don't read the missing test as a bug.

## Overview

`mobile-builds.yml` can already build a signed AAB and upload it to Play Store internal track. What it can't reliably do today:

- It pins Flutter to `channel: master` + `flutter-version: '3.32.0-0.3.pre'` (pre-release). Meanwhile `ci.yml` uses `channel: stable` with no version pin. Tests pass on stable, builds ship on master — silent divergence bomb.
- No Gradle cache. Every cold run redownloads dependencies; adds 3–5 minutes per build.
- No pre-build `flutter analyze` / `flutter test` gate. A broken `main` can be tagged and shipped to internal track.
- No Crashlytics native-symbol upload step. `epic-android-release-hardening` Story 5 wires the Gradle config; this epic wires the CI step that actually ships symbols to Firebase.
- No promotion pipeline. Moving an AAB from internal → closed → production requires manual Fastlane invocation on someone's laptop.
- No Firebase Test Lab soft-smoke. Play Console's Pre-Launch Report catches some things post-upload, but an in-CI Robo crawl catches the most obvious crashes before burning a version number.

This epic stitches the CI side end-to-end so a `v*.*.*` tag push becomes: analyze → test → build → Crashlytics symbols → Firebase Test Lab soft-smoke → Play Store internal track — with zero human intervention. Plus a separate `promote-android.yml` workflow for track promotion, gated by the `production` environment approval.

## Goal

One-operator release flow: `git tag v1.2.3 && git push --tags` reliably lands a signed AAB on Play Store internal track. Promotion to higher tracks is a single click on `Actions → Promote Android → Run workflow` (requires approval on `production` environment).

## End-user flow

There's no in-app user-visible flow here — it's infra. But the **operator** flow is the thing that matters:

### Operator Flow A — Ship a new internal-track build

1. Operator bumps `app/pubspec.yaml` version (`version: 1.0.16+29`) on main and pushes.
2. Once the PR merges, operator creates a tag: `git tag v1.0.16 && git push origin v1.0.16`.
3. `mobile-builds.yml` triggers on the tag push.
4. Pre-flight: `flutter analyze` + `flutter test` run. If red, the workflow fails — no AAB leaves.
5. `gradle bundle` builds the signed AAB.
6. Crashlytics native symbols upload step runs — Firebase Crashlytics now can symbolicate future release crashes.
7. Firebase Test Lab Robo crawl runs on one Pixel-class emulator. Soft-fail — if Google's servers glitch, it doesn't block the upload.
8. `upload_to_play_store(track: "internal")` lands the AAB.
9. Play Console auto-kicks off Pre-Launch Report (separate, free, server-side).
10. Within ~10 minutes the internal-track build is available to any opted-in tester.

### Operator Flow B — Promote an internal-track build to closed or production

1. Operator visits `https://github.com/<repo>/actions/workflows/promote-android.yml`.
2. Clicks "Run workflow", picks `source_track: internal`, `target_track: closed` (or `production` later).
3. GitHub prompts for approval (production environment gate — same pattern ci.yml already uses for prod infra).
4. Approver approves. Workflow runs a single Fastlane lane (`fastlane android promote`) that calls `upload_to_play_store(track: "internal", track_promote_to: "closed")` — **no rebuild**; it just moves the existing AAB by version code.
5. Play Console shows the AAB now on the target track.
6. For production: operator manually sets rollout % in Play Console UI (not automated — staged rollout UI is Play's strength; duplicating in CI adds fragility).

## Frontend changes

None. No app code touched. All changes are in `.github/workflows/` and `app/fastlane/`.

## Backend changes

None.

## Infrastructure changes

### `.github/workflows/mobile-builds.yml` — rewire `android-build`

- **Flutter version pin** — extract `FLUTTER_CHANNEL` and `FLUTTER_VERSION` into `env:` at the workflow top. Match `ci.yml`'s stable channel. Single source of truth — adding a new workflow file references the same env.
- **Gradle cache** — new `actions/cache@v4` step caching `~/.gradle/caches` + `~/.gradle/wrapper`, keyed on `hashFiles('app/android/**/*.gradle*', 'app/android/gradle/wrapper/gradle-wrapper.properties', 'app/pubspec.lock')`.
- **Pre-build analyze + test** — add two steps before the Gradle build: `flutter analyze --no-fatal-warnings --no-fatal-infos` and `flutter test`. Fail-fast.
- **Crashlytics native symbol upload** — handled by the Fastlane lane directly (Gradle plugin auto-uploads when `mappingFileUploadEnabled + nativeSymbolUploadEnabled` are on, provided `GOOGLE_APPLICATION_CREDENTIALS` points at a service-account JSON with Firebase access). Ensure the service-account JSON is available in CI via `FIREBASE_SERVICE_ACCOUNT_JSON` secret.
- **Firebase Test Lab soft-smoke** — after the AAB builds (but before Play Store upload), run `gcloud firebase test android run --type=robo --app build/app/outputs/bundle/release/app-release.aab --device model=oriole,version=33,locale=en,orientation=portrait --timeout 2m --no-record-video`. `continue-on-error: true` so a Test Lab glitch doesn't block the release.

### `.github/workflows/promote-android.yml` — new file

- Trigger: `workflow_dispatch` only. Inputs: `source_track` (`internal|closed|production`), `target_track` (`closed|production`).
- Gated by `environment: production` (same pattern as `ci.yml`'s deploy jobs — GitHub prompts for reviewer approval).
- Runs on `ubuntu-latest`. Checkout + Ruby setup + Bundler install (no Flutter, no Gradle — promotion doesn't rebuild).
- Calls new Fastlane lane: `bundle exec fastlane android promote source:<source_track> target:<target_track>`.
- Success condition: Fastlane exits 0 and Play Console Release API confirms the AAB now sits on the target track.

### `app/fastlane/Fastfile` — extend Android platform

- **Update `internal` lane:**
  - After `gradle(task: "bundle", ...)`, call `upload_symbols_to_crashlytics` (Fastlane built-in) OR use the Firebase CLI directly via `sh("firebase crashlytics:symbols:upload ...")` to push native + mapping files to Firebase.
  - The Gradle plugin's auto-upload (when `mappingFileUploadEnabled=true`) usually handles this; belt-and-suspenders manual step is optional. Party-mode decision.
- **New `promote` lane:**
  ```ruby
  lane :promote do |options|
    source = options[:source] || "internal"
    target = options[:target] || "production"

    # Find the latest version code on the source track
    upload_to_play_store(
      track: source,
      track_promote_to: target,
      skip_upload_aab: true,
      skip_upload_apk: true,
      skip_upload_metadata: true,
      skip_upload_images: true,
      skip_upload_screenshots: true,
      skip_upload_changelogs: true,
      json_key_data: ENV["PLAY_STORE_JSON_KEY"]
    )
  end
  ```
  This uses Play Console's edit API to move the already-uploaded AAB from track `source` to `target` without rebuilding.

### New GitHub Secrets required

- **`FIREBASE_SERVICE_ACCOUNT_JSON`** — Firebase service account with Crashlytics upload permission. JSON body. (Same service account can double as Play Store upload key if granted both Play Console + Firebase roles; `ANDROID.md` documents the least-privilege option.)
- **`FIREBASE_TEST_LAB_SERVICE_ACCOUNT_JSON`** — optional, can reuse FIREBASE_SERVICE_ACCOUNT_JSON if it has Test Lab permission.

No new secrets for promotion (reuses `PLAY_STORE_JSON_KEY`).

### `ci.yml` — minor touch-up

- Pin `flutter-version` in the existing `flutter-test` job to match `mobile-builds.yml`. Currently `channel: stable, cache: true` with no version pin; drift is bounded by stable release cadence but worth nailing down.

## Initial design principles

- **Soft-fail Test Lab, hard-fail tests.** `flutter test` must pass or no AAB ships. Firebase Test Lab is best-effort — it's nice validation but Google's infra has enough transient hiccups that making it blocking would break the "YOLO it to the store" contract.
- **No rebuild for promotion.** Play Console's track-promote API moves version codes between tracks without re-uploading. Anything we build needs to survive promotion; re-building risks version-code drift or signature mismatch.
- **One source of truth for Flutter version.** Split across `ci.yml` + `mobile-builds.yml` today → drift is inevitable. Extract to shared env var, or reusable workflow if we want maximum strictness.
- **Match the existing `production` environment gate.** `ci.yml` uses `environment: production` on every deploy job. Promotion workflow does too — approval UX is consistent.
- **CI doesn't know about Play Console metadata.** Store listing, screenshots, privacy URL all live in Play Console directly. CI just moves AABs between tracks.

## File structure (anticipated)

### New
- `.github/workflows/promote-android.yml`

### Modified
- `.github/workflows/mobile-builds.yml` — pin Flutter version, add Gradle cache, add pre-build analyze+test, add Test Lab soft-smoke, add Crashlytics symbol upload secret.
- `.github/workflows/ci.yml` — pin Flutter version in flutter-test job.
- `app/fastlane/Fastfile` — extend `android internal` lane, add `android promote` lane.

## Stories

### Story 1: `ach-1` — Unify Flutter channel + version + concurrency guard across workflows

**AC:**
- **Pre-flight plugin-compatibility audit** (15 min): run `flutter pub outdated` on a dev branch using `channel: stable, flutter-version: <latest stable>`. Identify any plugin (cloud_firestore, firebase_messaging, receive_sharing_intent, etc.) that requires a newer engine than the chosen stable version. Resolution: upgrade the plugin or pick a later stable Flutter. **Do not silently re-pin to master.**
- `mobile-builds.yml` env block at top declares `FLUTTER_CHANNEL: stable` and `FLUTTER_VERSION: '<pinned>'`.
- Both `ios-build` and `android-build` jobs use those env vars in their `subosito/flutter-action@v2` step (no inline `channel: master`, no inline `flutter-version`).
- `android-build` declares `concurrency: { group: mobile-builds-android, cancel-in-progress: false }` at the job level. A duplicate tag push serializes instead of racing for the same Play Console version-code.
- `ci.yml` `flutter-test` job is updated to same `flutter-version` (coupled to Story `ach-6`).
- Verify with a dry-run: both workflows show matching Flutter version in the `flutter doctor` log, and a double-tag test (push → force-push override) serializes cleanly.

### Story 2: `ach-2` — Gradle cache + pre-build analyze + test gate

**AC:**
- `android-build` adds `actions/cache@v4` for `~/.gradle/caches` and `~/.gradle/wrapper` keyed on `hashFiles('app/android/**/*.gradle*', 'app/android/gradle/wrapper/gradle-wrapper.properties', 'app/pubspec.lock')` with a fallback restore-key.
- Second cold run of the workflow shows Gradle cache hit (verify via "Cache hit" log line).
- New step *before* the `fastlane android internal` invocation: `flutter analyze --no-fatal-warnings --no-fatal-infos` and `flutter test`. Both must pass.
- A contrived broken PR + tag demonstrates the gate (manually, in a draft branch): analyze fails → AAB never uploads.

### Story 3: `ach-3` — Crashlytics native symbol upload via Gradle plugin (+ CI auth)

**AC:**
- `android-build` job adds a `google-github-actions/auth@v2` step before the Gradle build, authenticating from `FIREBASE_SERVICE_ACCOUNT_JSON` and exporting `GOOGLE_APPLICATION_CREDENTIALS` to subsequent steps.
- No Fastlane `upload_symbols_to_crashlytics` call. The Gradle plugin (already applied via `id("com.google.firebase.crashlytics")` in `app/android/app/build.gradle.kts`) auto-uploads mapping + native symbols during `gradle bundle` when the env var is set and `buildTypes.release { firebaseCrashlytics { mappingFileUploadEnabled = true; nativeSymbolUploadEnabled = true } }` is declared (prerequisite: `arh-5` landed).
- New GitHub Secret `FIREBASE_SERVICE_ACCOUNT_JSON` documented at top of `mobile-builds.yml`.
- After a CI run, Firebase Console → Crashlytics → Palateful Android → Versions list shows the new version with symbols uploaded.
- Gracefully degrades: if symbol upload fails, the Gradle build still succeeds (plugin's default behavior — it warns but doesn't abort).

### Story 4: `ach-4` — Firebase Test Lab soft-smoke step

**AC:**
- `android-build` runs `gcloud firebase test android run --type=robo --app build/app/outputs/bundle/release/app-release.aab --device model=oriole,version=33,locale=en,orientation=portrait --timeout 2m --no-record-video --project palateful` after `gradle bundle`.
- Step has `continue-on-error: true` — Robo crawl failure never blocks upload to Play Store.
- Test Lab run output is visible in the workflow log (device attach, crawl start/end, result URL).
- `gcloud` auth uses `FIREBASE_SERVICE_ACCOUNT_JSON` (reuses the Crashlytics service account, which must also have Test Lab permission — documented in `ANDROID.md`).
- Results link posted to workflow summary via `echo "::notice::Test Lab results: $URL"`.

### Story 5: `ach-5` — New `promote-android.yml` workflow + Fastlane `promote` lane

**AC:**
- `.github/workflows/promote-android.yml` exists with:
  - `workflow_dispatch` trigger only.
  - Inputs `source_track` (default `internal`), `target_track` (default `closed`).
  - `environment: production` gate.
  - Steps: checkout + Ruby/Bundler + `bundle exec fastlane android promote source:<source> target:<target>`.
- `app/fastlane/Fastfile` has a new `android:promote` lane that calls `upload_to_play_store(track_promote_to: ..., skip_upload_*: true)`.
- Manual dry-run test: operator runs workflow with `source=internal, target=closed` against an existing internal-track build → Play Console shows the AAB on closed track.
- Rollback case: operator runs the lane with swapped tracks — track-promote can move a build *back*; workflow supports this (no validation that source is "below" target).

### Story 6: `ach-6` — `ci.yml` flutter-test version pin + success `::notice::` + YOLO acceptance note

**AC:**
- `ci.yml` job `flutter-test` has an explicit `flutter-version` matching `mobile-builds.yml` (coupled to Story `ach-1`).
- At the end of the `android-build` job (post-upload), a step emits `echo "::notice title=Play Store Internal Track::Build vX.Y.Z uploaded — review at https://play.google.com/console"` so the operator sees the link in the workflow summary.
- ANDROID.md Section 17 explicitly documents: "The first real `v*.*.*` tag push is the end-to-end pipeline verification. Watch the Actions tab; the `::notice::` link confirms upload. If something breaks, fix in a follow-up commit + new tag — no rollback on a failed upload is needed because no AAB reached Play Console."
- Next `main` push shows the pinned Flutter version in its `flutter doctor` step.

## Dependencies

- **Depends on `epic-android-release-hardening` Story 5** for the Gradle plugin config that enables NDK symbol upload (Story 3 here consumes it).
- **Independent of `epic-android-privacy-policy-page`** — no code overlap.
- **Blocks `epic-android-play-console-launch`** in the operator flow: ANDROID.md's "tag → Play Store" step assumes this CI works.
- **Inherits GitHub Secrets** from current `mobile-builds.yml` (listed at top of file). Adds `FIREBASE_SERVICE_ACCOUNT_JSON`.

## Open questions for the user

None — party-mode resolved: single GCP service account with three roles (Play + Crashlytics + Test Lab); one Test Lab device (Pixel 7 API 33) in v1; concurrency guard lands in Story `ach-1`.
