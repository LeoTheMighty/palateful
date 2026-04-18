# SHARE.md — iOS Share Extension launch runbook

Manual steps to ship the `PalatefulShare` extension (epic
`epic-share-ios-extension`). Code for all 5 stories (sie-1…sie-5) is
landed on `main`. This file walks you through the bits Claude can't
do: App Store Connect, signing, device testing.

## TL;DR

1. Create App ID + App Group + provisioning profile in Apple Developer
   (~15 min).
2. Open `app/ios/Runner.xcworkspace` in Xcode and verify signing for
   `PalatefulShare` target (~5 min).
3. Build to a device and validate the happy path from Safari (~10 min).
4. Run through the device matrix before submitting the next TestFlight
   build (~30 min).

Total: ~1 h of human work, then ship.

---

## 1. Apple Developer: App ID + App Group + provisioning profile

### 1a. Create the new App ID

1. Go to <https://developer.apple.com/account/resources/identifiers/list>.
2. **+** → **App IDs** → **App**.
3. Description: `Palateful Share Extension`.
4. Bundle ID (Explicit): `com.palateful.palateful.share` — **exactly**;
   the Ruby target wiring hard-codes this.
5. Capabilities: enable **App Groups**.
   - Edit → check `group.com.palateful.app` (the existing App Group the
     main app and `PalatefulWidgets` share). Do NOT enable push,
     associated domains, background modes, or any other cap — keeping
     the surface minimal reduces App Review scrutiny.
6. Save.

### 1b. Confirm main App ID has the App Group enabled

`com.palateful.palateful` (the main app) likely already has
`group.com.palateful.app` enabled — the existing `Runner.entitlements`
lists it. If Xcode complains about capability mismatch later, revisit
this.

### 1c. Create a provisioning profile (Development + Distribution)

Xcode Cloud and Xcode's "automatic signing" usually handle this, but if
you ever hit `No profiles for 'com.palateful.palateful.share' were
found`:

1. Same page → **Profiles** → **+**.
2. Select **App Store** (for distribution) → Continue.
3. App ID: `com.palateful.palateful.share`.
4. Certificates: pick your existing distribution cert.
5. Profile Name: `Palateful Share Extension — App Store`.
6. Repeat with **iOS App Development** → `Palateful Share Extension — Development`.
7. Download both and double-click to install into Xcode.

---

## 2. Xcode: verify target signing + build

Open `app/ios/Runner.xcworkspace` (NOT the `.xcodeproj` — Flutter pods
are only wired into the workspace).

### 2a. Confirm the target exists

Target list should show four entries:

- `Runner`
- `RunnerTests`
- `PalatefulShare`   ← new
- `Pods-*` aggregates (auto-generated)

If `PalatefulShare` is missing, run:

```sh
ruby app/ios/scripts/add_share_extension.rb
```

The script is idempotent — re-running is a no-op when the target
already exists.

### 2b. Signing

On `PalatefulShare` target → **Signing & Capabilities**:

- **Team**: `H66YP2QFW2` (same as main app — already set in the
  project).
- **Automatically manage signing**: ✅ checked.
- **Bundle Identifier**: `com.palateful.palateful.share` (pre-set).
- **App Groups**: should list `group.com.palateful.app` (entitlement
  file already references it). If Xcode shows a `!`, click **Fix Issue**
  and grant Apple Developer access.

If automatic signing fails, uncheck it and pick the profiles you
created in step 1c manually.

### 2c. Build to a device

```sh
cd app && flutter run -d <your-iphone-udid>
```

Or build through Xcode directly — pick the `Runner` scheme and your
device. The `Embed App Extensions` phase auto-embeds
`PalatefulShare.appex` into `Runner.app/PlugIns/`.

After install, quit the app. Then open Safari → any recipe page → Share
button. **Palateful** should appear in the app row. If it doesn't:

- Scroll right in the app row, tap **More** → **Edit**, and manually
  enable Palateful. (iOS sometimes hides newly-installed extensions.)
- Kill Safari fully (swipe up) and reopen.

---

## 3. Happy path smoke test

### 3a. URL share from Safari

1. Open a recipe on allrecipes.com.
2. Share → Palateful.
3. Sheet should show "Recipe URL · allrecipes.com", the default recipe
   book selected, Save + Cancel buttons.
4. Tap Save → "Saved ✓" appears for ~1 s → sheet dismisses.
5. Within ~30 s, push notification fires (`IMPORT_NEEDS_REVIEW` /
   `IMPORT_COMPLETE`).
6. Open Palateful → Activity Hub → row should be present.

### 3b. Photo share from Photos

1. Photos → pick any photo → Share → Palateful.
2. Sheet should show "Recipe photo · NNN KB".
3. Save → same flow.

### 3c. PDF share from Files

1. Files → any PDF → Share → Palateful.
2. "Recipe PDF · NNN MB" + book picker.
3. For a >10 MB file, a disclosure line reads "Uploading NN MB to
   Palateful".
4. Save → same flow.

### 3d. Oversize file (>100 MB)

1. Share a ~150 MB video.
2. Sheet should show "This file is too large" with a Close button only.
   No Save button. No network calls (verify via Console.app if
   paranoid).

### 3e. Signed-out state

1. In Palateful, sign out.
2. Share any URL → Palateful.
3. Sheet should show "Sign in to save shared recipes." with a Close
   button. No Save button.

---

## 4. Full device test matrix (before next TestFlight build)

Per `sie-5` AC. Each combination = ~3 min.

|               | iOS 17 | iOS 18 |
|---------------|--------|--------|
| iPhone SE 3rd | [ ]    | [ ]    |
| iPhone 15 Pro | [ ]    | [ ]    |
| iPad          | [ ]    | [ ]    |

For each cell, run 3a + 3b + 3c + 3d + 3e from section 3.

**iOS 18 notes**: Apple tightened extension memory in 18. The
`sie-4` AC says <80 MB RSS on a 100 MB video upload; measure via
Xcode → **Debug navigator** → Memory gauge while the PUT is in
flight. If you see > 80 MB, something in `PalatefulShare/` is
buffering (the lint in `ci_post_clone.sh` catches the common
offenders, but not all of them).

**iPad**: on iPad the extension is presented as a popover. If it renders
stretched to full screen, verify `preferredContentSize` in
`ShareViewController.swift` matches the design (340×300).

**VoiceOver**: iPhone → Settings → Accessibility → VoiceOver on. Share
a URL. Swipe right through the sheet — every element should read a
label; the title reads "Save to Palateful" via `screenChanged`
announcement on open.

---

## 5. What did NOT land

These are gaps the code leaves open; either defer or track separately.

1. **PalatefulWidgets / PalatefulNotificationService source folders
   are NOT wired into Xcode.** The directories exist but `pbxproj`
   doesn't reference them as targets — someone started those
   extensions and stopped. This epic only added `PalatefulShare`.
   If you care about widgets / rich notifications, file a separate
   epic — the pattern (this Ruby target script) is now proven and
   trivial to replicate.

2. **Backup of file-upload path when extension dies mid-PUT.** If the
   iOS process is reaped during a background S3 PUT, the ETag is lost
   and the main-app reconciler can't resubmit — the file share is
   effectively dropped. Common case (small files, fast networks)
   completes within the extension's 30s post-`completeRequest`
   window. Full-bulletproof would require the main app reconnecting
   to the background URLSession via
   `application(_:handleEventsForBackgroundURLSession:)` — ~200 loc
   of Swift+Flutter plumbing. Deferred to v2.

3. **Automated XCUIApplication memory test.** `sie-4` AC called for
   an automated XCTest that drives the extension and asserts
   `os_proc_available_memory()` stays under a threshold. This needs a
   UI test target that doesn't exist yet, plus a CI runner with a
   physical device. Run the memory check manually via Xcode's Debug
   navigator on the iPhone SE as described in section 4.

4. **`receive_sharing_intent` plugin is still in `pubspec.yaml`.** The
   existing Flutter share path (Android + cold-start from main-app-
   routed iOS shares) still uses it. The new iOS extension is
   orthogonal and doesn't link any Dart code. No cleanup needed.

---

## 6. Rollback

If something explodes post-ship:

1. **Hide the extension from the share sheet** (zero-code, fastest):
   users can turn it off via iOS share sheet → More → Edit →
   toggle Palateful off. Surface this in release notes if needed.
2. **Pull the target from the build**: open Xcode → delete
   `PalatefulShare` from the target list → Archive. This unships
   the extension on the next TestFlight upload without touching the
   main app.
3. **Full revert**: `git revert` the sie-1 through sie-5 commits (in
   reverse order) and push. The revert is clean because the Flutter
   side's `SharedStateService` and `PendingImportsReconciler` have
   no callers besides themselves once the extension is gone.

---

## 7. Telemetry / observability

All events POST to `/v1/events` with `source: "ios_share_extension"`:

- `share_extension_latency_ms` — share-sheet-tap → Saved checkmark,
  in ms. Target p50 < 2500 ms on Wi-Fi (`sie-3` AC).
- `share_extension_cancelled` — user tapped Cancel.
- `share_extension_multi_item_truncated` — >1 attachment; emitted with
  `{count, kept_type}`.
- `share_extension_size_too_large` — hit the 100 MB gate; emitted with
  `{kind: "file" | "text", bytes}`.
- `share_extension_failed` — 4xx / 5xx or network failure from
  `/upload-url`, PUT, or `/import`.

Query these in Redash / whatever your `/v1/events` pipeline terminates
in. No additional dashboard work is part of this epic.

---

## 8. Version bump

`app/pubspec.yaml` has already been bumped by the final commit in this
series. Verify before you push the TestFlight build:

```sh
grep '^version:' app/pubspec.yaml
```

Should be one patch + one build number higher than the previous
TestFlight cut.
