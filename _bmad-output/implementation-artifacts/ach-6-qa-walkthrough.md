# QA walkthrough — ach-6 (ci.yml pin + success notice + YOLO note)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/ci.yml` — `flutter-test` job:
  - `subosito/flutter-action@v2` now pins `flutter-version: '3.32.0'`
    (matches `mobile-builds.yml` from ach-1).
  - Inline comment explaining the coupling so a future bump updates
    both files.
- `.github/workflows/mobile-builds.yml` — `android-build` job:
  - New `Emit Play Store summary link` step appended after the Test
    Lab soft-smoke step.
  - Only fires on tag pushes (`if: startsWith(github.ref,
    'refs/tags/v')`) so the `workflow_dispatch` path (no tag) doesn't
    emit a misleading link.
  - Parses the version from the tag ref
    (`${GITHUB_REF_NAME#v}` → `1.2.3`) and emits
    `::notice title=Play Store Internal Track::Build v<VERSION>
    uploaded. Review at https://play.google.com/console/…`.
- `ANDROID.md` — new subsection `### 18.1 — YOLO acceptance`:
  - Explains the deliberate absence of a pre-production pipeline
    test.
  - Documents the two `::notice::` lines to look for in the workflow
    summary.
  - Documents the roll-forward protocol (new tag, never revert).

## Static verification

1. `grep -n "flutter-version: '3.32.0'" .github/workflows/ci.yml`
   — one match inside `flutter-test`.
2. `grep -n "flutter-version: '3.32.0'" .github/workflows/mobile-builds.yml`
   — no direct match (the pin lives in `env:` block); check
   `grep "FLUTTER_VERSION:" .github/workflows/mobile-builds.yml`
   returns `FLUTTER_VERSION: '3.32.0'`.
3. `grep -n "Emit Play Store summary link" .github/workflows/mobile-builds.yml`
   — one match.
4. `grep -n "### 18.1" ANDROID.md` — one match inside Section 18.

## Live verification (deferred to first main push + first tag push)

- First `main` push after this merges: `ci.yml` `flutter-test` job's
  `flutter doctor` step prints `Flutter 3.32.0`.
- First `v*.*.*` tag push: workflow summary shows both `::notice::`
  lines — Test Lab (soft, may be absent if Test Lab glitched) + Play
  Store Internal Track (hard).

## Deviation from epic text

The epic's AC for ach-6 specified "ANDROID.md Section 17 explicitly
documents…" but Section 17 is tester recruitment (from
`epic-android-play-console-launch`, which landed first). The correct
home for this YOLO note is Section 18 (First CI-driven release) since
that's the tag-push flow. Deviation captured here + in the story file.

## Non-regressions

- No other `ci.yml` jobs touched (the Flutter version pin was
  deliberately scoped to `flutter-test` — the other Flutter jobs
  (`deploy-web`) don't ship AABs so their version drift matters less,
  and re-pinning all of them expands the blast radius for this
  change).
- No Fastlane changes.
- No new secrets.

## Rollback

Single-commit revert. All three changes (ci.yml pin, mobile-builds.yml
notice, ANDROID.md 18.1) ride together.
