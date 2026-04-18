# QA walkthrough — ach-5 (promote-android.yml + Fastlane promote lane)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/promote-android.yml` — new workflow:
  - `workflow_dispatch` trigger only.
  - Choice-typed inputs: `source_track` (internal|closed|production),
    `target_track` (closed|production).
  - Job name reflects source→target for readable run names.
  - `environment: production` → reviewer approval gate, same model as
    every `ci.yml` deploy job.
  - Steps: checkout + Ruby/Bundler + `bundle exec fastlane android
    promote` + final `::notice::` summary.
  - Reuses `PLAY_STORE_JSON_KEY` — no new secrets.
- `app/fastlane/Fastfile` — new `android:promote` lane calling
  `upload_to_play_store(track_promote_to:)` with every
  `skip_upload_*` flag true. No rebuild.

## Static verification

1. `grep -n "workflow_dispatch" .github/workflows/promote-android.yml`
   — exactly one match, and no `push:`/`pull_request:` triggers.
2. `grep -n "environment: production" .github/workflows/promote-android.yml`
   — one match on the `promote` job.
3. `grep -n "lane :promote" app/fastlane/Fastfile` — inside
   `platform :android` block.
4. YAML + Ruby parse cleanly (`python3 -c "import yaml; …"`,
   `ruby -c app/fastlane/Fastfile`).

## Live verification (deferred to first closed-test cut)

Happy path:

1. Operator: Actions → Promote Android → Run workflow.
2. Pick `source_track: internal`, `target_track: closed`. Run.
3. GitHub prompts for approval on `production` environment. Approve.
4. Lane runs, Fastlane logs "Successfully updated track" or similar.
5. Play Console → Testing → Closed testing → shows the version code
   that was on internal.

Rollback case (intentional — no directionality check):

- Run workflow with `source=production, target=closed` to pull a
  production AAB back to closed test. Play Console's own API permits
  this; Fastlane mirrors it.

## Auditing the inputs

- Every invocation is logged in GitHub Actions with `inputs.source_track`
  + `inputs.target_track` captured. The operator can see *who*
  promoted *what* → *where* by reading the Actions tab.
- `environment: production` gate means the approval is also logged in
  the environment's deployment history.

## Non-regressions

- `mobile-builds.yml` untouched.
- `android internal` Fastlane lane untouched.
- iOS-side is unaffected (no `:promote` lane for iOS — TestFlight
  doesn't have the same track model; promotion there lives in App
  Store Connect directly).

## Rollback of ach-5 itself

Delete `.github/workflows/promote-android.yml` and revert the Fastfile
diff. No external state mutated until the operator first runs the
workflow.
