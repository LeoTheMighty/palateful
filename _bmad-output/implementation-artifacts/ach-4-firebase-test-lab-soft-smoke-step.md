# Story ach-4: Firebase Test Lab soft-smoke step

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Catch obvious crashes before they eat a Play Console version code.
Play Console's Pre-Launch Report runs its own Robo crawl after upload,
but by that time the version code is burned — a crash on boot still
means the next build needs a bumped `+build` integer. The in-CI
equivalent (Firebase Test Lab Robo on one Pixel-class emulator) runs
the same style of crawl in ~2 minutes and lets us fail-forward before
the AAB ever leaves the CI runner.

**Soft-fail by design.** Firebase Test Lab occasionally glitches on
Google's side. A Test Lab infra blip must never block an otherwise
healthy release — `continue-on-error: true` is the contract.

## Implementation

### `.github/workflows/mobile-builds.yml` — `android-build` job

The `google-github-actions/auth@v2` step from ach-3 already exports
`GOOGLE_APPLICATION_CREDENTIALS`. Add `google-github-actions/setup-
gcloud@v2` + the Test Lab invocation after the Fastlane build (so the
AAB exists on disk) but before the `::notice::` success line from
ach-6.

Wait — Fastlane's `upload_to_play_store` is inside the same lane as
`gradle bundle`, so the AAB is uploaded before we can run Test Lab
against it. Three options:

1. Split Fastlane `android internal` into two lanes (`build` + `upload`).
   Highest blast radius — other CI + local invocations would need to
   re-glue. Rejected.
2. Run Test Lab against a locally-rebuilt AAB from a separate
   `flutter build appbundle` invocation in a later step. Doubles build
   time. Rejected.
3. Run Test Lab **after** the Fastlane upload. Play Store's internal
   track accepts the AAB first; if Test Lab finds a crash, the
   operator rolls forward with a new tag (internal-track AABs can be
   superseded without side effects). This is the epic's design
   choice — Pre-Launch Report runs the same way. **Accepted.**

Add the step after `Build and upload to Play Store` and before the
success-notice step (ach-6):

```yaml
- uses: google-github-actions/setup-gcloud@v2
  with:
    project_id: palateful

- name: Firebase Test Lab soft-smoke (Robo)
  continue-on-error: true
  working-directory: app
  run: |
    AAB="android/app/build/outputs/bundle/release/app-release.aab"
    if [ ! -f "$AAB" ]; then
      echo "::warning::AAB not found at $AAB — skipping Test Lab."
      exit 0
    fi
    gcloud firebase test android run \
      --type=robo \
      --app "$AAB" \
      --device model=oriole,version=33,locale=en,orientation=portrait \
      --timeout 2m \
      --no-record-video \
      --project palateful \
      2>&1 | tee /tmp/testlab.log || true
    RESULT_URL=$(grep -oE 'https://console.firebase.google.com[^ ]+' /tmp/testlab.log | head -n1 || true)
    if [ -n "$RESULT_URL" ]; then
      echo "::notice title=Firebase Test Lab::Robo crawl results: $RESULT_URL"
    fi
```

Device choice: `oriole` (Pixel 6) / API 33 — broad coverage, cheap
slot. One device is enough for soft-smoke; ANDROID.md Section 6
documents the choice so adding more devices later is a one-line
expansion.

### `continue-on-error: true` + `|| true`

Two layers of soft-fail:

- `continue-on-error: true` at the step level so a non-zero `gcloud`
  exit doesn't fail the job.
- `|| true` inline so the run-step itself never propagates non-zero
  even if something crashes between `gcloud` and the URL grep.

Belt-and-suspenders — Test Lab flakiness is the #1 reason soft-fail
guarantees drift in practice.

## Acceptance criteria

- [x] `gcloud firebase test android run --type=robo ...` step in
  `android-build` after `Build and upload to Play Store`.
- [x] `continue-on-error: true` on the step.
- [x] Device: `oriole,version=33,locale=en,orientation=portrait`.
- [x] Timeout: `2m`. `--no-record-video` to keep cost / time down.
- [x] `gcloud` auth inherits from the ach-3
  `google-github-actions/auth@v2` step. Added `setup-gcloud@v2`
  specifically for the `gcloud` binary.
- [x] Result URL emitted via `::notice title=Firebase Test Lab::Robo
  crawl results: <URL>`.
- [ ] First tag push shows the Robo result URL in the workflow summary
  — deferred to YOLO acceptance.

## File list

### Modified

- `.github/workflows/mobile-builds.yml`
