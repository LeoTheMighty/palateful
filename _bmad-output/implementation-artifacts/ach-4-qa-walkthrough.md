# QA walkthrough — ach-4 (Firebase Test Lab soft-smoke)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/mobile-builds.yml` — `android-build` job:
  - `google-github-actions/setup-gcloud@v2` step (pins `gcloud` onto
    `$PATH`; auth reused from the ach-3 auth step).
  - `Firebase Test Lab soft-smoke (Robo)` step:
    - `gcloud firebase test android run --type=robo` against the
      just-built AAB.
    - Device: Pixel 6 (`oriole`) / API 33 / en / portrait.
    - Timeout: `2m`, `--no-record-video`.
    - `continue-on-error: true` — a Test Lab infra glitch cannot
      fail the job.
    - Inline `|| true` on the `gcloud` call — two layers of soft-fail.
    - Emits `::notice title=Firebase Test Lab::Robo crawl results:
      <URL>` when a Firebase console URL is parsed from the log.

## Static verification

1. `grep -n "google-github-actions/setup-gcloud@v2" .github/workflows/mobile-builds.yml`
   — one match, inside `android-build`.
2. `grep -n "continue-on-error: true" .github/workflows/mobile-builds.yml`
   — on the Test Lab step.
3. `grep -n "::notice title=Firebase Test Lab" .github/workflows/mobile-builds.yml`
   — the result-URL emit.
4. YAML parses: `python3 -c "import yaml; yaml.safe_load(open(...))"`.

## Design choices captured in the story file

- Test Lab runs **after** Play Store upload (not before). Play
  internal-track AABs are superseded by the next tag push without side
  effects, so a Robo-detected crash means "cut a new tag" not "revert"
  — same model Play's Pre-Launch Report uses.
- One device only (`oriole` / API 33). ANDROID.md Section 6 documents
  the pin; adding more devices later is a one-line change.

## Live verification (deferred to first tag push)

- Step log shows a Firebase Test Lab invocation, crawl start/end,
  result URL.
- Workflow summary shows the `::notice::` with the Firebase console
  URL.
- Opening the URL shows the Robo results for the crawl.

## Failure-mode smoke

- **Missing AAB** — step logs `::warning::AAB not found at …` and
  exits 0. No Test Lab call. (Contrived: delete the AAB between steps.)
- **Test Lab 5xx** — step logs the error, `continue-on-error` keeps
  the job green, no `::notice::` emitted. Operator continues with
  the upload (already completed).
- **Robo finds a crash** — step exits non-zero; `continue-on-error`
  keeps the job green; the operator reads the result URL in the
  workflow summary and decides whether to ship a fix. Per epic
  design, no automatic rollback.

## Non-regressions

- Fastlane lane unchanged.
- iOS-build unchanged.
- Secrets: no new secret — reuses `FIREBASE_SERVICE_ACCOUNT_JSON` via
  ach-3's auth step.

## Rollback

Single-commit revert. No external state mutated beyond Firebase's own
crawl history (already retained by Google indefinitely — no cleanup
needed).
