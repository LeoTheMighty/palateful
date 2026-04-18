# Play Console store-listing assets

Version-controlled store-listing PNGs uploaded to Play Console →
**Grow → Store presence → Main store listing → Graphics**. Kept in-repo so
`apl-2` re-uploads from a clean checkout instead of a Figma hunt.

## What lives here

| File | Dimensions | Format | Owner |
| --- | --- | --- | --- |
| `icon-source-1024.png` | 1024×1024 | PNG, RGB | `arh-3` (launcher source art) |
| `icon-512.png` | 512×512 | PNG | `apl-2` (generated from source) |
| `feature-graphic-1024x500.png` | 1024×500 | PNG, no alpha | `apl-2` (**operator produces — see below**) |
| `screenshots/phone-1.png` | ≥1080×1920, portrait | PNG | `apl-2` (**operator captures — see below**) |
| `screenshots/phone-2.png` | ≥1080×1920, portrait | PNG | `apl-2` |
| `screenshots/phone-3.png` | ≥1080×1920, portrait | PNG | `apl-2` |
| `screenshots/phone-4.png` | ≥1080×1920, portrait | PNG | `apl-2` |

ANDROID.md Section 12 (Store Listing) references every path above
verbatim — do not rename.

## Source of truth

`icon-source-1024.png` is the brand launcher icon (also fed to
`flutter_launcher_icons` via `arh-3`). It is the **only** source-of-truth
raster — re-export from Figma into this path if brand colors change and
everything downstream regenerates.

## Re-export procedures

### `icon-512.png` — fully automatable

Downscale the source icon with macOS `sips`:

```bash
sips -z 512 512 \
  app/android/play-store-assets/icon-source-1024.png \
  --out app/android/play-store-assets/icon-512.png
```

Output inherits the source color space (RGB, no alpha). If Play Console
rejects the upload citing "icon must be 32-bit PNG with alpha," re-export
from Figma at 512×512 with transparency enabled and commit directly (skip
the `sips` step).

### `feature-graphic-1024x500.png` — operator action (design tool required)

Not re-exportable from repo assets alone — requires a design tool
(Figma / Sketch / Photoshop). Spec:

- **Dimensions:** exactly 1024×500.
- **Format:** PNG (24-bit preferred) or JPEG. Google discourages alpha
  channels on feature graphics; if the source has alpha, flatten against
  the brand cream before export.
- **Content:** Palateful wordmark + tagline **"Your kitchen's recipe memory"**
  (locked in the epic workshop) + subtle kitchen imagery (a pan, cutting
  board, or similar — low-contrast so the wordmark reads).
- **Safe area:** keep the wordmark + tagline roughly centered with
  ~50 px of margin from every edge. Play Console can crop this image for
  some surfaces, so critical elements should not sit on the edges.
- **Background:** brand cream (eye-drop the flat area of
  `icon-source-1024.png` for the exact hex).

Export to `app/android/play-store-assets/feature-graphic-1024x500.png`
and commit.

### `screenshots/phone-1..4.png` — operator action (emulator required)

Captured from a running Android emulator (Pixel 7, API 34) with
Palateful installed in release mode. Scenes are locked by the epic AC:

| File | Scene |
| --- | --- |
| `phone-1.png` | Home screen, 6+ recipes visible, bottom nav visible |
| `phone-2.png` | Recipe detail with a photo + ingredient list + steps |
| `phone-3.png` | Meal calendar (week view) with 3–4 meals scheduled |
| `phone-4.png` | Cooking mode with an active timer |

Capture procedure:

```bash
# 1. Launch the Pixel 7 API 34 emulator.
#    (Android Studio → Device Manager → "Pixel 7 API 34" → ▶︎)
#    Or from CLI, if emulator tools are on PATH:
#    emulator -avd Pixel_7_API_34 -no-snapshot-load

# 2. Run Palateful in release mode against the running emulator. From
#    the app/ subdirectory (monorepo root hosts services/, libraries/
#    — Flutter lives under app/):
cd app
flutter run --release

# 3. In the app, navigate to each scene above. There is no automated
#    fixture loader — seed content manually: import 6+ recipes for the
#    home screen shot, open one for the detail shot, schedule 3–4 meals
#    for the calendar shot, start a timer in cooking mode for the timer
#    shot.

# 4. Capture each screenshot via adb:
adb exec-out screencap -p > \
  app/android/play-store-assets/screenshots/phone-1.png
# Repeat for phone-2.png … phone-4.png after navigating each scene.

# 5. Verify dimensions (must be portrait ≥ 1080×1920):
sips -g pixelWidth -g pixelHeight \
  app/android/play-store-assets/screenshots/phone-*.png
```

Pixel 7 emulator native resolution is 1080×2400 — fits the floor.

### Re-capture on UI regressions

If a screenshot drifts from reality (new nav item, colors changed, home
layout tweaked), re-capture **only the affected file(s)**. Update
ANDROID.md Section 12 if scene descriptions change.

## Upload order in Play Console

1. App icon → upload `icon-512.png`.
2. Feature graphic → upload `feature-graphic-1024x500.png`.
3. Phone screenshots → upload `phone-1.png` first (shows up as the hero),
   then `phone-2..4.png` in order.

Play Console re-compresses everything; don't worry about file size.

## Git policy

All PNGs in this directory are **tracked** (not gitignored). They are the
single source of truth for a clean-checkout re-upload. Do not add this
directory to any `.gitignore`.
