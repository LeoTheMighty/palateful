# QA walkthrough — arh-3: Adaptive launcher icon

## Smoke prerequisites

- Android emulator: Pixel 7 API 33 (adaptive icons + themed icons).
- Optional second emulator: Pixel 2 API 25 (raster fallback).

## Checklist

- [ ] `cd app && flutter build appbundle --release` completes without
      errors.
- [ ] `adb install-multiple` the generated AAB onto the Pixel 7 API
      33 emulator.
- [ ] Home screen:
  - [ ] Palateful icon appears with a clean adaptive shape (circle on
        Pixel, rounded square on emulators without OEM launcher
        overrides).
  - [ ] No "dumb square container" fallback.
- [ ] Settings → Wallpaper & style → toggle "Themed icons" ON. Confirm
      the Palateful icon switches to a monochrome rendering that picks
      up the system accent color (acceptable if it looks washed out
      until a transparent-background source PNG lands — see story
      notes).
- [ ] Long-press home screen → widgets → notifications preview uses
      the same adaptive icon.
- [ ] Pixel 2 API 25 emulator: icon falls back to the raster
      `mipmap-*dpi/ic_launcher.png` with no visual regression vs. the
      pre-arh-3 icon.
- [ ] `dart run flutter_launcher_icons` run a second time produces
      no git diff (idempotency — verified locally before merge but
      re-confirmed here).

## Regression surface

- **Launch experience**: the Flutter `LaunchTheme` referenced in
  AndroidManifest.xml (line 22) uses `android:icon="@mipmap/ic_launcher"`
  — same resource identifier, so the pointer is unchanged. Boot splash
  should be visually identical to pre-arh-3.
- **MCP server / web launcher**: iOS launcher icon is untouched
  (`ios: false` in the `flutter_launcher_icons:` block). Web
  `favicon.png` is untouched.

## Known caveat — opaque source

v1 uses the iOS 1024×1024 launcher as the source, which is opaque. The
adaptive foreground therefore fills its inset square with the iOS
background, which Android shape-masks down. Themed icon looks washed
out because the monochrome derivation desaturates the full image
instead of a clean P-mark. Replacing
`app/android/play-store-assets/icon-source-1024.png` with a
transparent-background artwork (1024×1024 PNG, "P" mark centered with
~10% safe-area padding) and re-running the generator produces a
cleaner look without any config change. Logged as a follow-up.

## Out of scope

- 512×512 Play Store listing icon (apl-2).
- iOS launcher icon (unchanged).
- Screenshot-diff automation in CI (future).
