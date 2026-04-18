# Story arh-3: Adaptive launcher icon via flutter_launcher_icons

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Replace the hand-authored raster-only launcher icon with an adaptive
icon generated from a single source PNG via the `flutter_launcher_icons`
package. The generator emits mipmap-anydpi-v26 adaptive XML (foreground
+ background + monochrome for Android-13 themed icons) plus raster
fallbacks for every density — eliminating the manual density-ladder
math and keeping the source of truth aligned with what apl-2 will
downscale for the Play Store listing icon.

## Scope (from epic)

- New source PNG at `app/android/play-store-assets/icon-source-1024.png`
  (1024×1024). v1 seeds from the existing iOS 1024×1024 launcher icon
  (`app/ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-1024x1024@1x.png`)
  so the Android and iOS brand marks stay in sync until a transparent-
  background design artwork lands.
- `pubspec.yaml` dev_dependency: `flutter_launcher_icons: ^0.14.4`.
- `pubspec.yaml` `flutter_launcher_icons:` config block: android only,
  adaptive background `#FAF7F2` (app's main `cream` surface color,
  `AppColors.cream` in `core/theme/app_colors.dart`), adaptive
  foreground + monochrome derive from the same source.
- `dart run flutter_launcher_icons` regenerates:
  - `mipmap-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher.png`
  - `mipmap-anydpi-v26/ic_launcher.xml` (with `<background>`,
    `<foreground>`, `<monochrome>`)
  - `drawable-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher_foreground.png`
  - `drawable-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher_monochrome.png`
  - `values/colors.xml` (new: declares `@color/ic_launcher_background`)

## Implementation notes

- **Transparency caveat**: the iOS-derived source PNG is opaque, not
  transparent. The adaptive foreground therefore fills the full inset
  square with the iOS icon's own background, which Android crops into
  the shape mask. Until a transparent-background source artwork lands,
  Android 13 themed icons will show a washed-out rasterised mono
  version of the full icon instead of a clean symbol mark. Acceptable
  for internal-track v1; logged as a design follow-up.
- **Idempotency**: re-running `dart run flutter_launcher_icons` with no
  config change produces no diff (verified locally).
- **Pre-API-26 fallback**: the plugin keeps the raster `ic_launcher.png`
  files under every `mipmap-*dpi` so legacy devices continue to render
  correctly.
- **512×512 Play Store icon**: out of scope here — owned by
  `apl-2` which will downscale the same source PNG. The source is
  committed under `app/android/play-store-assets/` precisely so both
  consumers (this story + apl-2) read from one place.

## Acceptance criteria (from epic)

- [x] `app/android/play-store-assets/icon-source-1024.png` exists as a
  1024×1024 PNG. v1 seeded from the iOS launcher icon with a noted
  transparency caveat.
- [x] `app/pubspec.yaml` adds `flutter_launcher_icons: ^0.14.4` to
  `dev_dependencies`.
- [x] `pubspec.yaml` `flutter_launcher_icons:` block specifies
  `android: true`, `image_path`, `adaptive_icon_background: #FAF7F2`,
  `adaptive_icon_foreground`, `min_sdk_android: 26`, and
  `adaptive_icon_monochrome`.
- [x] `dart run flutter_launcher_icons` generates the expected outputs
  (mipmap raster ladder, mipmap-anydpi-v26/ic_launcher.xml with
  `<monochrome>`, drawable foreground + monochrome PNGs, colors.xml).
- [ ] `flutter build appbundle --release` screenshot diff on a Pixel 7
  API 33 emulator — deferred to QA walkthrough (no emulator in dev
  harness).
- [x] Pre-API-26 raster fallback preserved.
- [x] Idempotency: re-running the generator without config changes
  produces no git diff (verified via `git diff --stat` after second
  run).

## QA walkthrough

Split into `arh-3-qa-walkthrough.md`.

## File list

### New
- `app/android/play-store-assets/icon-source-1024.png`
- `app/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`
- `app/android/app/src/main/res/drawable-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_foreground.png`
- `app/android/app/src/main/res/drawable-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_monochrome.png`
- `app/android/app/src/main/res/values/colors.xml`

### Modified
- `app/pubspec.yaml` (dev dep + `flutter_launcher_icons:` block)
- `app/android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png` (regenerated)
- `app/pubspec.lock` (flutter_launcher_icons + transitive dependencies)
