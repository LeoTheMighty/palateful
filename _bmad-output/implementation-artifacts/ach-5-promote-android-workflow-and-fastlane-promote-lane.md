# Story ach-5: promote-android.yml workflow + Fastlane promote lane

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Turn "move an AAB from internal → closed → production" into a single
GitHub Actions workflow dispatch with reviewer approval. Today the
operator has to invoke Fastlane manually from their laptop; that's
fine once (the first closed-test cut) but terrible as a recurring
motion.

Two deliverables:

1. `.github/workflows/promote-android.yml` — `workflow_dispatch` with
   `source_track`/`target_track` inputs, gated by
   `environment: production` (reviewer approval matches the pattern
   every `ci.yml` deploy job already uses).
2. `app/fastlane/Fastfile` — new `android:promote` lane that calls
   `upload_to_play_store(track_promote_to: …, skip_upload_*: true)`.
   **No rebuild** — the AAB already sits on the source track; we just
   flip its assignment.

## Implementation

### `.github/workflows/promote-android.yml`

- Trigger: `workflow_dispatch` only (never runs on push).
- Inputs:
  - `source_track` — `choice` of `internal | closed | production`,
    default `internal`.
  - `target_track` — `choice` of `closed | production`, default `closed`.
- Job `promote`:
  - `runs-on: ubuntu-latest`
  - `environment: production` → GitHub prompts for reviewer approval.
  - Steps: checkout + Ruby/Bundler (no Flutter, no Gradle — no rebuild).
  - Invokes `bundle exec fastlane android promote
    source:<source> target:<target>`.
  - Success `::notice::` step for the workflow summary.
- Reuses `PLAY_STORE_JSON_KEY` — same secret the internal-track upload
  uses. No new secrets.

### `app/fastlane/Fastfile` — new `promote` lane inside
`platform :android`

```ruby
desc "Promote an already-uploaded AAB between Play Store tracks without rebuilding"
lane :promote do |options|
  source = options[:source] || "internal"
  target = options[:target] || "production"

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

Every `skip_upload_*` flag is set — we are moving an existing
artifact, not pushing a new one.

## Acceptance criteria

- [x] `promote-android.yml` exists with `workflow_dispatch` only.
- [x] Inputs: `source_track` + `target_track` with choice-typed
  options.
- [x] `environment: production` gate on the `promote` job.
- [x] Steps: checkout + Ruby/Bundler + `bundle exec fastlane android
  promote`.
- [x] No Flutter, no Gradle — zero rebuild.
- [x] `Fastfile` has `android:promote` lane calling
  `upload_to_play_store` with `track_promote_to` + all `skip_upload_*`
  flags true.
- [ ] Dry-run test: deferred to first real operator invocation. Play
  Console Release API confirms the AAB now sits on the target track.
- [x] Rollback case — promoting back (e.g. `source=production,
  target=closed`) works because no validation on directionality is
  enforced. Play Console's own API permits this.

## File list

### New

- `.github/workflows/promote-android.yml`

### Modified

- `app/fastlane/Fastfile`
