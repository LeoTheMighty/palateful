# QA Walkthrough: apl-2 — Play Console store listing assets

## Setup

- `cd /Users/leonidbelyi/personal/palateful`
- Have `ANDROID.md`, `app/android/play-store-assets/README.md`, and a
  file browser open on `app/android/play-store-assets/`.

## Scope note

apl-2 is **partially autonomous**. Autonomous deliverables ship in this
commit (`icon-512.png` + `README.md`). Feature graphic + 4 screenshots
remain operator action, documented in the README. This checklist covers
the autonomous slice only — the manual slice has its own checklist
inside the README.

## Smoke

- [ ] `ls app/android/play-store-assets/` shows `icon-source-1024.png`,
  `icon-512.png`, and `README.md` (no `screenshots/` dir yet; not
  required for this commit).
- [ ] `file app/android/play-store-assets/icon-512.png` reports
  `PNG image data, 512 x 512, ...`.
- [ ] `wc -l app/android/play-store-assets/README.md` → at least 80 lines.

## icon-512.png

- [ ] `sips -g pixelWidth -g pixelHeight app/android/play-store-assets/icon-512.png`
  reports `pixelWidth: 512` + `pixelHeight: 512`.
- [ ] `sips -g format app/android/play-store-assets/icon-512.png`
  reports `format: png`.
- [ ] Visually open `icon-512.png` — Palateful P-mark on cream
  background is legible, not pixelated, centered.
- [ ] File size < 50 KB (source is 10.9 KB at 1024×1024; 512 downscale
  should be smaller still).
- [ ] Re-running the `sips -z 512 512 …` command from the README is
  idempotent — output has the same dimensions (byte-level may vary due
  to sips's PNG encoder determinism; that is fine).

## README.md

- [ ] File-table section lists every planned asset with correct
  dimensions (512×512, 1024×500, ≥1080×1920).
- [ ] Source of truth is `icon-source-1024.png` — stated explicitly.
- [ ] `sips -z 512 512 …` command for regenerating `icon-512.png` is
  inside a fenced code block and runs successfully if copy-pasted.
- [ ] Feature-graphic section names the tagline literal
  **"Your kitchen's recipe memory"** (matches epic workshop decision).
- [ ] Screenshot section names Pixel 7 API 34 emulator + lists all 4
  scenes (home / recipe detail / calendar / cooking mode) verbatim.
- [ ] Screenshot capture section shows `adb exec-out screencap -p`
  command inside a fenced block.
- [ ] "Play Console upload order" section exists with icon →
  feature-graphic → screenshots sequence.
- [ ] "Git policy" paragraph at the end states all PNGs are tracked.

## Path consistency with ANDROID.md

- [ ] `grep -n 'play-store-assets' ANDROID.md` returns at least 6 hits
  (icon, feature graphic, 4 screenshots).
- [ ] Every path in ANDROID.md Section 12 matches the file table in
  the README exactly (icon-512.png, feature-graphic-1024x500.png,
  screenshots/phone-{1,2,3,4}.png).

## Git tracking

- [ ] `git check-ignore app/android/play-store-assets/icon-512.png` →
  nothing printed (not ignored).
- [ ] `git check-ignore app/android/play-store-assets/README.md` →
  nothing printed.
- [ ] `git status --short` shows both files as new-untracked (pre-add)
  or added (post-stage).

## Operator-remaining checklist (NOT part of this commit)

After this commit lands, the operator executes — before the first
Store Listing save in Play Console:

- [ ] Produce `feature-graphic-1024x500.png` per README spec (Figma /
  Sketch / Photoshop). Commit + push.
- [ ] Capture 4 portrait screenshots via emulator per README spec.
  Commit + push.
- [ ] Update `_bmad-output/implementation-artifacts/sprint-status.yaml`
  line `apl-2-produce-play-console-store-listing-assets: in-progress` →
  `done`.
- [ ] Open Play Console → Grow → Store presence → Main store listing →
  Graphics. Upload `icon-512.png`, then `feature-graphic-…png`, then
  `phone-1.png` through `phone-4.png`.
- [ ] Save the Store Listing. Confirm no validation errors on icon or
  graphic dimensions.

No further code review, CI, or tag push is gated on the operator
slice — the remaining work is outside CI's visibility.

## Rollback

If `icon-512.png` is rejected by Play Console or looks wrong when
rendered next to a Figma export:

```bash
git rm app/android/play-store-assets/icon-512.png
# Re-export from Figma at 512×512 with transparency enabled, save to
# app/android/play-store-assets/icon-512.png, then:
git add app/android/play-store-assets/icon-512.png
git commit -m "fix(android): re-export icon-512 with alpha from Figma"
```

README already documents this fallback path.
