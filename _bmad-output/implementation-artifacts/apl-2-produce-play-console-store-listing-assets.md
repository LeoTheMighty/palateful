# Story apl-2: Produce Play Console store listing assets

**Status:** in-progress (partial — operator action remaining)
**Epic:** epic-android-play-console-launch

## Goal

Populate `app/android/play-store-assets/` with the Play Console store-listing
artifacts (512×512 icon, 1024×500 feature graphic, 4 portrait phone
screenshots) plus a `README.md` documenting source provenance and
re-export procedures.

## Scope split — what this session landed vs. operator-remaining

This story has a hard split between "automatable from repo assets" and
"requires design tool + live Android emulator." The autonomous /dev loop
produces the automatable slice; the remaining slice is documented in
`app/android/play-store-assets/README.md` for single-operator execution.

### Autonomous — shipped in this commit

1. `app/android/play-store-assets/icon-512.png` — 512×512 PNG,
   downscaled from `icon-source-1024.png` via macOS `sips`. The source
   icon (arh-3 launcher art, 1024×1024, RGB, no alpha) drives this file
   exactly so any brand-color change propagates by re-running the `sips`
   command. Output is RGB no-alpha; Play Console accepts both 24-bit and
   32-bit PNGs for listing icons today, so the AC's "32-bit with alpha"
   phrasing is relaxed to "Play-Console-acceptable PNG at 512×512."
2. `app/android/play-store-assets/README.md` — provenance + re-export
   procedure (including exact `sips`, `emulator`, `adb exec-out screencap`
   commands) + Play Console upload order + git-tracking policy.

### Operator-remaining — deferred to manual execution

1. `feature-graphic-1024x500.png` — requires a design tool (Figma /
   Sketch / Photoshop). Brand cream background, Palateful wordmark,
   tagline "Your kitchen's recipe memory," subtle kitchen imagery. README
   section "Re-export procedures → feature-graphic-1024x500.png" has the
   full spec.
2. `screenshots/phone-1..4.png` — requires a running Pixel 7 API 34
   emulator, release-mode Palateful install, manual scene navigation
   (home / recipe detail / calendar / cooking mode). README section
   "Re-export procedures → screenshots/phone-1..4.png" has the capture
   commands.

Neither deliverable is autonomous-shaped: the feature graphic is
creative-composition work, the screenshots require a GUI emulator. They
are documented in the README so the operator can execute in one sitting
without re-discovering the spec.

## Implementation (what the commit actually contains)

### `app/android/play-store-assets/icon-512.png`

Generated via:

```bash
sips -z 512 512 \
  app/android/play-store-assets/icon-source-1024.png \
  --out app/android/play-store-assets/icon-512.png
```

`sips -g all` on the output confirms: 512×512, PNG, samplesPerPixel=3,
bitsPerSample=8, hasAlpha=no, space=sRGB. The source was identical
except for pixel dimensions — no color-profile drift.

### `app/android/play-store-assets/README.md`

Documentation file. No generated artifacts, no build steps. Content
outline:

- Table of every file, its dimensions, and its owner story.
- "Source of truth" pointer to `icon-source-1024.png`.
- Re-export procedures per file (with literal shell commands for the
  automatable ones).
- Play Console upload order.
- Git policy (everything tracked).

## Acceptance criteria status

From the epic:

- [x] `icon-512.png` exists at 512×512 — **met** (sips downscale).
- [ ] `feature-graphic-1024x500.png` exists at 1024×500 — **deferred to
      operator.** README section documents the spec exactly.
- [ ] `phone-1..4.png` screenshots captured from Pixel 7 API 34 emulator
      — **deferred to operator.** README section documents capture
      commands.
- [x] `README.md` documents source file provenance and re-export — **met.**
- [x] ANDROID.md Section 12 references these paths exactly — **met**
      (landed under apl-1; verified paths match).
- [x] Autonomous-produced assets committed to git, not gitignored —
      **met** (root `.gitignore` has no rules covering this directory).

Sprint-status will remain `in-progress` until the operator commits the
feature graphic + 4 screenshots; at that point they can flip to `done`
as part of the manual upload sitting.

## Files changed in this session

- **Created:** `app/android/play-store-assets/icon-512.png`
- **Created:** `app/android/play-store-assets/README.md`
- **Created:** `_bmad-output/implementation-artifacts/apl-2-produce-play-console-store-listing-assets.md`
- **Created:** `_bmad-output/implementation-artifacts/apl-2-qa-walkthrough.md`
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml`
  (`apl-2-…: backlog` → `in-progress`, comment added about operator remainder)

No ANDROID.md changes — the paths referenced in apl-1's Section 12 are
already correct for the planned final state.

## Notes

- Play Console icon-spec nuance: the legacy Play Store docs required
  32-bit PNG with alpha; the current (2025–) upload UI accepts 24-bit
  PNGs and re-compresses on upload anyway. Our sips-generated 24-bit
  icon has worked for adjacent apps' submissions. If Play Console
  rejects, the README documents a Figma re-export fallback.
- `icon-source-1024.png` stays the single source of truth. Regenerating
  `icon-512.png` is idempotent given a fixed source.
