# Story ach-6: ci.yml flutter-test version pin + success notice + YOLO AC note

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Three small cuts that finish the loop:

1. **`ci.yml` flutter-test version pin** — the existing `flutter-test`
   job on `ci.yml` uses `channel: stable` with no version pin; meanwhile
   `mobile-builds.yml` pins `3.32.0` (via ach-1). That divergence re-
   opens the "tests pass on newer stable, builds ship on older" failure
   mode we're trying to kill. Pin both sides to the same version.
2. **Success `::notice::` on android-build** — after upload, emit a
   Play Console link to the workflow summary so the operator gets a
   one-click path to verify.
3. **ANDROID.md Section 18.1 — YOLO acceptance note** — document the
   deliberate choice that the first tag push IS the end-to-end
   verification. Keeps later reviewers from reading the missing
   pre-production test as a bug.

## Implementation

### `.github/workflows/ci.yml` — `flutter-test` job

Add `flutter-version: '3.32.0'` on the `subosito/flutter-action@v2`
step. Keep the comment block explaining the coupling so a future
bump goes to both files.

### `.github/workflows/mobile-builds.yml` — post-upload notice

Add step at the end of `android-build` (after Test Lab soft-smoke):

```yaml
- name: Emit Play Store summary link
  if: startsWith(github.ref, 'refs/tags/v')
  run: |
    VERSION="${GITHUB_REF_NAME#v}"
    echo "::notice title=Play Store Internal Track::Build v${VERSION} uploaded. Review at https://play.google.com/console/u/0/developers"
```

`if: startsWith(github.ref, 'refs/tags/v')` — only runs on actual
tag pushes, not on the `workflow_dispatch` case (where no tag exists
to parse).

### `ANDROID.md` — Section 18.1

New subsection appended to Section 18 (the "First CI-driven release"
section; the most natural home for the YOLO note since that's the
first-tag-push flow). Covers:

- The deliberate absence of a pre-production pipeline test.
- What to look for in the workflow summary after the first tag push
  (the two `::notice::` lines — one soft from Test Lab, one hard from
  the upload).
- The roll-forward protocol when something breaks (new tag, not
  revert) and why Play Store's version-code model makes this cheap.

The epic spec text said "Section 17" for this note, but Section 17
is tester recruitment — Section 18 (tag→Play flow) is the correct
home. Captured in the story file so the deviation is explicit.

## Acceptance criteria

- [x] `ci.yml` `flutter-test` has `flutter-version: '3.32.0'`.
- [x] `mobile-builds.yml` `android-build` ends with an
  `Emit Play Store summary link` step that emits `::notice title=Play
  Store Internal Track::…` when the workflow runs on a `v*.*.*` tag.
- [x] `ANDROID.md` Section 18.1 documents YOLO acceptance (tag push
  = pipeline verification; roll-forward on failure; no rollback for
  upload failures).
- [ ] Next `main` push shows `Flutter 3.32.0` in the `flutter doctor`
  step of the `flutter-test` job — deferred, visible in the first CI
  run after merge.

## File list

### Modified

- `.github/workflows/ci.yml`
- `.github/workflows/mobile-builds.yml`
- `ANDROID.md`
