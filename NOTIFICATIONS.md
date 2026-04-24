# Notifications, Capabilities & iOS Native Extensions

> **Scope:** this runbook covers every iOS capability the app currently uses (push notifications, share extension, widgets, Live Activities) plus ones you may want to add later (Sign in with Apple, Associated Domains / Universal Links, App Attest, CloudKit). It documents the Apple Developer Console steps, Xcode wiring, Firebase integration (where relevant), and specific pitfalls we've already hit.
>
> **Urgent:** Section §1 is the unblock procedure for the current "push notifications return `no_tokens`" bug. Everything below it is reference material for later.
>
> **Related docs:** `SHARE.md` (already documents the share extension launch runbook), `docs/PUSH_NOTIFICATIONS.md` (code-side architecture), `docs/DEPLOYMENT.md` (Xcode Cloud pipeline).

---

## Contents

- §1. [Unblock push notifications (urgent)](#1-unblock-push-notifications-urgent)
- §2. [How Apple's three control planes fit together](#2-how-apples-three-control-planes-fit-together)
- §3. [Current state — what's wired today](#3-current-state--whats-wired-today)
- §4. [Push Notifications (APNs + FCM) — full setup](#4-push-notifications-apns--fcm--full-setup)
- §5. [Share Extension — already live; full reference](#5-share-extension--already-live-full-reference)
- §6. [Notification Service Extension — rich notifications](#6-notification-service-extension--rich-notifications)
- §7. [Widgets (PalatefulWidgets) — already shipping](#7-widgets-palatefulwidgets--already-shipping)
- §8. [Live Activities + ActivityKit](#8-live-activities--activitykit)
- §9. [Background Modes](#9-background-modes)
- §10. [Associated Domains / Universal Links (future)](#10-associated-domains--universal-links-future)
- §11. [Sign in with Apple (Guideline 4.8 risk)](#11-sign-in-with-apple-guideline-48-risk)
- §12. [App Attest / DeviceCheck (abuse protection)](#12-app-attest--devicecheck-abuse-protection)
- §13. [Non-capability permissions (Camera, Mic, Photos, Location)](#13-non-capability-permissions-camera-mic-photos-location)
- §14. [Diagnostics cheat-sheet](#14-diagnostics-cheat-sheet)
- §15. [Xcode Cloud signing quirks](#15-xcode-cloud-signing-quirks)

---

## 1. Unblock push notifications (urgent)

Symptom: admin "Send test push to myself" returns `result=no_tokens`. Client-side `error_logs` (service=`client`) shows the ground truth:

```
PlatformException(apns.registrationFailed,
  no valid "aps-environment" entitlement string found for application,
  NSCocoaErrorDomain code 3000)
```

**Root cause.** `Runner.entitlements` declares `aps-environment=production`, but the provisioning profile Xcode Cloud is signing with doesn't grant that entitlement. The App ID either never had Push Notifications enabled, or the capability was enabled after the current profile was minted (profiles don't auto-refresh — they have to be regenerated).

### Fix procedure (10 min)

1. **Apple Developer Console → Identifiers**
   - [developer.apple.com/account → Certificates, Identifiers & Profiles → Identifiers](https://developer.apple.com/account/resources/identifiers/list)
   - Click `com.palateful.palateful` → Edit
   - Check **Push Notifications** → Save

2. **Create APNs Auth Key** (one-time per team, reusable forever — do this now if you haven't already)
   - Same screen → **Keys** tab → **+** → name it "Palateful FCM" → check **Apple Push Notifications service (APNs)** → Continue → Register
   - **Download the `.p8` file immediately** — Apple only lets you download it once. Save to 1Password / secure storage.
   - Copy the **Key ID** (10-char, shown on screen) and note your **Team ID** (top-right of the portal, `H66YP2QFW2`).

3. **Upload the `.p8` to Firebase**
   - [console.firebase.google.com](https://console.firebase.google.com) → Palateful → Project Settings → **Cloud Messaging** tab
   - iOS app (`com.palateful.palateful`) → APNs Authentication Key → **Upload**
   - File: the `.p8`; Key ID: from step 2; Team ID: `H66YP2QFW2`

4. **Regenerate provisioning profiles**
   - If using **automatic signing** (Xcode Cloud default): nothing manual. The next CI build fetches a freshly-minted profile. Just trigger a new build.
   - If using **manual signing**: Profiles tab → delete old `Palateful` distribution profile → Generate → check APNs capability → download → drop into Xcode.

5. **Trigger a fresh Xcode Cloud build.** Re-running an existing build reuses the cached profile; use "Start Build" on a new commit (a no-op version bump works).

6. **Install from TestFlight, cold-start the app, fire admin test push.** Verify with:
   ```bash
   ./bin/prod-script /tmp/check_smoke_test.py
   ```
   You should see `push.ensureRegistered: completed, final_status=authorized` followed by **no** `apns.registrationFailed` rows, and `push_tokens_count` becomes ≥1.

7. **Once confirmed working, revert the temporary diagnostic** in `app/lib/main.dart:118-134` (the `BootSmokeTest` POST block). The permanent `ErrorReporter` mirror stays.

---

## 2. How Apple's three control planes fit together

Read this once; it makes every other section make sense.

Three systems must agree for a capability to work at runtime:

1. **Apple Developer Portal → Identifiers → App ID** — the **allow-list.** Checkbox here says "this App ID *may* use X."
2. **Provisioning Profile** — the **proof.** Embeds the entitlements granted by the App ID. **Toggling any capability on an App ID invalidates all existing profiles for that App ID**; they must be regenerated. This is the single most common cause of capability bugs.
3. **Xcode target → `Signing & Capabilities` + `.entitlements` file** — the **claim.** Must list the entitlements, which the profile must grant. If the claim isn't in the profile's grants, code signing fails; if the claim is in the profile but missing from the built IPA, iOS rejects the API at runtime (this is exactly what happened with `aps-environment`).

**App Store Connect's "Capabilities" tab is informational only.** You do not enable capabilities from ASC — you enable them in the developer portal's Identifiers section and then add them in Xcode.

**Canonical order of operations for a new capability:**

1. Portal → Identifiers → App ID → check capability → Save.
2. Portal → Profiles → regenerate (or rely on Xcode / Xcode Cloud auto-refresh for **managed capabilities** — Xcode 15+ can flip the App ID checkbox + regenerate the profile in one step when you add the capability via Xcode's Signing & Capabilities tab).
3. Xcode → target → Signing & Capabilities → **+ Capability** → add it. This edits the `.entitlements` file (and sometimes `Info.plist`).
4. Build. For Xcode Cloud with automatic signing, the next CI run fetches the new profile.

Inspect what's actually in a built IPA:
```bash
codesign -d --entitlements :- path/to/Runner.app
```

---

## 3. Current state — what's wired today

### Targets in `app/ios/Runner.xcodeproj`

| Target | Bundle ID | Type | Entitlements | Status |
|---|---|---|---|---|
| **Runner** | `com.palateful.palateful` | App | `aps-environment=production`, `group.com.palateful.app` | **Push signing broken — §1** |
| **PalatefulShare** | `com.palateful.palateful.share` | Share extension | `group.com.palateful.app` | Live |
| **PalatefulNotificationService** | `com.palateful.palateful.notificationservice` | Notification service ext. | (inherits) | Live (rich image notifs) |
| **PalatefulWidgets** | `com.palateful.palateful.widgets` | Widget + Live Activity ext. | `group.com.palateful.app` | Live |
| **RunnerTests** | | Test bundle | — | Unit tests |

> **Note on identifiers:** the iOS bundle ID is `com.palateful.palateful` (and `.share`, `.widgets`, etc. for extensions). The string `com.palateful.app` is a separate thing used for the Auth0 URL-scheme callback and as the App Group suffix (`group.com.palateful.app`) — don't confuse it with the bundle ID when clicking through the Apple Developer portal.

### Info.plist keys already set (Runner)

- `NSSupportsLiveActivities = true`
- `UIBackgroundModes = [remote-notification]`
- `NSUserNotificationUsageDescription`, `NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`, `NSMicrophoneUsageDescription`, `NSSpeechRecognitionUsageDescription`
- `CFBundleURLTypes` (Auth0 callback `com.palateful.app`)

### Firebase configuration

- `app/ios/Runner/GoogleService-Info.plist` — project `palateful`, iOS app `1:386854922290:ios:899d64f146311162c8b42b`, bundle `com.palateful.palateful`
- `app/lib/firebase_options.dart` — DefaultFirebaseOptions generated by `flutterfire configure`
- Crashlytics dSYM upload runs in `app/ios/ci_scripts/ci_post_xcodebuild.sh`

### Flutter packages relevant here

- `firebase_core ^3.9.0` / `firebase_crashlytics ^4.3.10` / `firebase_messaging ^15.2.0`
- `live_activities ^2.0.0`
- `home_widget ^0.7.0`
- `receive_sharing_intent ^1.8.0`
- `flutter_local_notifications ^18.0.0`

---

## 4. Push Notifications (APNs + FCM) — full setup

See §1 for the procedure. Here's the extended reference.

**Use an APNs Auth Key (`.p8`), not a certificate (`.p12`).** The key never expires, covers development + production in one, and works across every app in the team. Certificates rotate yearly per bundle ID and require separate dev + prod — avoid.

**`aps-environment` value semantics.** In `Runner.entitlements` it's hardcoded `production`. iOS actually uses the value embedded in the provisioning profile at sign time: Debug builds get `development` (routes to APNs sandbox), Release / TestFlight / App Store builds get `production`. You don't manually edit the string for debug vs release.

**APNs tokens are environment-specific.** A sandbox token is invalid against production APNs. FCM handles the routing automatically; if you ever bypass FCM and push via `api.push.apple.com` directly, you'll need to track which environment minted each token.

**Rich notification images** require `mutable-content: 1` on the payload plus a URL at `fcm_options.image`. If either is missing, `PalatefulNotificationService` never runs. See §6.

**2025 APNs CA change — not your problem.** Apple rotated the APNs server CA. FCM handles the server-side trust chain; we're insulated unless we ever implement direct APNs pushing ourselves.

### Error: `apns.registrationFailed` / `NSCocoaErrorDomain code 3000`

Root-cause checklist (ordered by likelihood):

1. App ID doesn't have Push Notifications enabled in the portal.
2. Provisioning profile is stale (capability added after profile was minted).
3. `CODE_SIGN_ENTITLEMENTS` build setting in `project.pbxproj` doesn't point at `Runner/Runner.entitlements`.
4. Manual signing + wrong profile selected.
5. IPA was built before the capability change and you're running that cached binary.

### Error: `firebase_messaging/apns-token-not-set`

Downstream of #3000. APNs never registered, so `FirebaseMessaging.instance.apnsToken` is nil, so `getToken()` throws. Fix APNs registration and this disappears.

---

## 5. Share Extension — already live; full reference

> `SHARE.md` in the repo root has the full end-to-end setup runbook. This section is the capability-level summary.

**Target:** `PalatefulShare` / `com.palateful.palateful.share`. Registers Palateful in the system share sheet for URLs, images, files, videos, text.

### Apple Developer Console

- Separate App ID `com.palateful.palateful.share` (already registered).
- Both the main app's App ID and the extension's App ID have **App Groups** enabled with `group.com.palateful.app` (already set).

### How it works

- Extension's `NSExtensionActivationRule` declares what triggers it (URL / image / file / movie / text).
- Entry point `ShareViewController.swift` → `ShareViewModel.swift` handles recipe-book selection and dispatches `UploadService.swift`.
- `SharedState.swift` reads auth JWT + recipe book list from `UserDefaults(suiteName: "group.com.palateful.app")`. The main app writes this state on auth change via a MethodChannel.
- `UploadService` uses a **streaming** `URLSession.uploadTask(with:fromFile:)` to stay under iOS's ~120 MB extension RAM ceiling. The CI lint in `ci_post_clone.sh:44-55` rejects any `Data` / `UIImage(contentsOfFile:)` reads — violating that ceiling crashes the extension silently.
- For deferred uploads after the extension is dismissed, it uses a background `URLSession` with `sharedContainerIdentifier = "group.com.palateful.app"`, so the main app's `AppDelegate` picks up the completion handler when iOS wakes it back up.

### Signing

Same Team ID as main app. Extension has its own profile. Automatic signing + Xcode Cloud handles it.

### Pitfalls we've hit

- **Missing `sharedContainerIdentifier`** on background session → extension crashes with no error message.
- **Build config not wired to `Generated.xcconfig`** → fixed in commit `62cff6a`. Symptom: Flutter build settings don't flow into the extension target.
- **Memory over-budget from buffered reads** → see `bin/prod-ios-deploy` and `ci_post_clone.sh` lint.

---

## 6. Notification Service Extension — rich notifications

**Target:** `PalatefulNotificationService` / `com.palateful.palateful.notificationservice`. Runs ~30s before iOS displays a push notification; used for attaching downloaded images to push payloads (recipe covers, partner avatars).

### Apple Developer Console

Separate App ID. Enable App Groups if the extension needs shared state (it doesn't currently). No capability checkbox for "notification service extension" — it's a target type.

### Current implementation

`NotificationService.swift:77` handles:
1. `didReceive(_:withContentHandler:)` extracts `image_url` from payload.
2. `URLSession.shared.downloadTask` downloads the image.
3. Moves to `NSTemporaryDirectory()` with correct extension.
4. Attaches via `UNNotificationAttachment`.
5. `serviceExtensionTimeWillExpire()` delivers unmodified notification on timeout.

### Payload contract (server-side)

Backend must send:
```json
{
  "aps": { "alert": {...}, "mutable-content": 1 },
  "fcm_options": { "image": "https://..." }
}
```

The `mutable-content: 1` flag is **required** — without it the extension is never invoked. FCM's server SDK sets this automatically when you use `notification.image`.

### Pitfalls

- Team ID mismatch between extension and host → code signing rejects the whole IPA.
- 30s hard timeout — fall back gracefully; don't block indefinitely.
- Forgetting `mutable-content: 1` on the server → hours of debugging nothing.

---

## 7. Widgets (PalatefulWidgets) — already shipping

> **Heads-up:** widgets are already live. Your future-roadmap note about "I really want a widget" is already met.

**Target:** `PalatefulWidgets` / `com.palateful.palateful.widgets`. Contains:

- `NextMealWidget` — small/medium/large. Reads `next_meal_json` + `today_meals_json` from app-group UserDefaults.
- `ShoppingListWidget` — medium/large. Reads `shopping_list_json`.
- `CookingTimerLiveActivity` — Dynamic Island + lock-screen timer UI.
- `AppIntents.swift` — Siri App Intents for recipe lookup (reads `recipes_index_json` from app-group UserDefaults).

### Data flow

```
Flutter (main app)
  ├─ widget_data_service.dart ─→ HomeWidget.saveWidgetData()
  │                              └→ UserDefaults(suiteName: "group.com.palateful.app")
  ├─ spotlight_index_service.dart (recipes_index_json)
  └─ live_activity_service.dart ─→ LiveActivities plugin
                                    └→ ActivityKit (native)

UserDefaults (app group) ←→ PalatefulWidgets extension (SwiftUI)
```

### Apple Developer Console

Widget extension has its own App ID. App Groups enabled on both the widget and the main app. No widget-specific capability.

### Future expansion — iOS 14/16/17/18 features

- **iOS 14+:** home screen widgets. ✅
- **iOS 16+:** lock-screen widgets (`accessoryRectangular`, `accessoryCircular`, `accessoryInline`). Not yet wired — could surface next meal on lock screen.
- **iOS 17+:** interactive widgets (buttons in widgets). Could let users mark shopping items checked directly from the widget.
- **iOS 18+:** `ControlWidget` in Control Center, Action Button, Lock Screen controls. Could provide "start timer" / "view today's meal" quick-actions.

### Pitfalls

- Widget can't call Flutter Dart code. All data exchange is via app-group UserDefaults (small JSON) or app-group container files (blobs). Push updates via `WidgetCenter.shared.reloadAllTimelines()` or `reloadTimelines(ofKind:)`.
- Manual signing with Flutter + widget extension has a well-known `CodeSign Failed` footgun. Stay on automatic signing.

---

## 8. Live Activities + ActivityKit

**Current state.** `NSSupportsLiveActivities=true` in Runner's Info.plist. The widget extension hosts `CookingTimerLiveActivity`. Wired via the `live_activities` Flutter plugin.

### What else is needed to ship new Live Activities

1. **`ActivityAttributes`** — Swift struct **shared between main app and widget extension** (Target Membership: both). Nested `ContentState` (dynamic) and outer `Attributes` (static).
2. **`ActivityConfiguration`** in the widget extension's `WidgetBundle` — defines lock-screen UI + Dynamic Island compact/minimal/expanded variants.
3. **Start locally**: `Activity<YourAttrs>.request(attributes:, content:, pushType: .token)`.
4. **Update from server** via APNs with `apns-push-type: liveactivity` and topic `com.palateful.palateful.push-type.liveactivity`. Payload includes `aps.event` (`update` / `end`) and `content-state`.

### Push-to-Start (iOS 17.2+)

App registers a **push-to-start token** at launch → server sends an APNs push with `event: "start"` → iOS starts the Activity even if the app is killed.

### FCM wiring

FCM supports Live Activities. Extract the push token from `Activity<Attrs>.pushTokenUpdates`, POST alongside the regular FCM token. Backend uses FCM's Live Activity API or pushes directly to APNs.

### Pitfalls

- Activities auto-end after ~8h wall clock or 12h stale. Not "always on."
- Widget extension's Info.plist also needs `NSSupportsLiveActivities=true` (easy miss).
- Wrong APNs topic = silent drop.

---

## 9. Background Modes

Current: `remote-notification` (silent-push wake-up for ~30s).

| Mode | Adds | For Palateful |
|---|---|---|
| `remote-notification` | Silent pushes wake app | ✅ already on |
| `fetch` (`BGAppRefreshTask`) | System wakes app opportunistically | Maybe — refresh meal calendar |
| `processing` (`BGProcessingTask`) | Minutes of background work, idle + charging | Maybe — pre-cache recipe images overnight |
| `audio` / `location` / `voip` | Specialized | No |

### Modern API: BGTaskScheduler

1. Add `fetch` or `processing` to `UIBackgroundModes`.
2. Add `BGTaskSchedulerPermittedIdentifiers` to Info.plist (e.g., `com.palateful.palateful.refresh`).
3. Register handlers in `AppDelegate.application(_:didFinishLaunchingWithOptions:)` via `BGTaskScheduler.shared.register(forTaskWithIdentifier:)`.
4. Submit a `BGAppRefreshTaskRequest` or `BGProcessingTaskRequest`.

### iOS 26 (WWDC25): `BGContinuedProcessingTask`

User-visible background task with a system progress UI. For user-initiated long uploads or exports. Not needed yet; flag on the radar.

No portal capability — Background Modes is purely Info.plist + code.

---

## 10. Associated Domains / Universal Links (future)

**What it does.** `https://palateful.app/recipe/123` opens the app directly when installed; falls back to the website otherwise.

**When you'll want it.** Email invites, shared recipe links, "accept invitation" flows. Strongly recommended for the invitations epic.

### Apple Developer Console

Identifiers → `com.palateful.palateful` → check **Associated Domains** → Save → regenerate profile.

### Xcode

Signing & Capabilities → **+ Associated Domains** → add entries like `applinks:palateful.app`. During testing, use `applinks:staging.palateful.app?mode=developer` to bypass the aggressive AASA cache (otherwise you can wait 24h to re-test changes).

### Web server

Host `https://palateful.app/.well-known/apple-app-site-association`:

```json
{
  "applinks": {
    "apps": [],
    "details": [{
      "appIDs": ["H66YP2QFW2.com.palateful.palateful"],
      "components": [
        { "/": "/recipe/*", "comment": "Recipe deep link" },
        { "/": "/invite/*", "comment": "Invitation deep link" }
      ]
    }]
  }
}
```

Serve over HTTPS, `Content-Type: application/json`, **no redirects**, under 128 KB. A redirect once is a redirect forever — iOS caches it.

### Runtime (Flutter)

Use `app_links` or `uni_links` package. Native: `application(_:continue:restorationHandler:)` forwards `NSUserActivity.webpageURL` to Flutter.

---

## 11. Sign in with Apple (Guideline 4.8 risk)

> **Potential App Store rejection.** App Store Review Guideline 4.8 (revised Jan 2024, still in force 2026) says: if you offer *any* third-party or social sign-in, you must also offer a login that (1) limits data to name + email, (2) supports email privacy, (3) doesn't track for ads. Google Sign-In alone does **not** qualify. Sign in with Apple does. An app with only Google OAuth via Auth0 is technically non-compliant. Review often catches this.

**Options:**
- Add **Sign in with Apple** via Auth0's Apple connector (simplest).
- Add **email magic-link / passwordless** login via Auth0 (also satisfies 4.8 if privacy properties are met).

### Apple Developer Console

Identifiers → App ID → check **Sign In with Apple** → Configure ("Enable as a primary App ID") → Save → regenerate profiles.

Separate key: Keys → + → **Sign In with Apple** → download `.p8` (different from APNs key).

### Xcode

Add **Sign in with Apple** capability → entitlement `com.apple.developer.applesignin = ["Default"]`.

### Runtime

`ASAuthorizationAppleIDProvider().createRequest()` → present `ASAuthorizationController`. First-time sign-in returns name + email; cache them (subsequent sign-ins only return the user identifier).

### Auth0 wiring

Auth0 Dashboard → Authentication → Social → **Apple** → provide Services ID, Team ID, Key ID, `.p8` signing key.

---

## 12. App Attest / DeviceCheck (abuse protection)

**What it does.** Cryptographically proves "this API request came from a real, unmodified Palateful app on a real Apple device." Protects public/unauthenticated endpoints (invitation accept, signup, share-link consumption) from bots.

**Relevance.** Worth considering once you hit public-facing flows at scale. Not urgent.

### Apple Developer Console

Identifiers → App ID → check **App Attest** → Save → regenerate profile.

### Runtime sketch

1. `DCAppAttestService.shared.isSupported` (false on simulator, jailbroken devices).
2. `generateKey` → cache `keyID` in Keychain.
3. `attestKey(_:clientDataHash:)` → attestation blob.
4. Send `keyID + attestation` to backend on first use; backend validates via Apple's App Attest endpoint, stores public key per user.
5. Each subsequent request: `generateAssertion(_:clientDataHash:)` → header; backend verifies.

### Firebase App Check (optional)

If you want Firebase App Check guarding Firestore / Storage / RC, configure: Firebase Console → App Check → iOS app → Apple App Attest → Register. In code: `AppCheck.setAppCheckProviderFactory(AppAttestProviderFactory())` before `FirebaseApp.configure()`. Not needed if your backend validates attestations itself.

### Pitfalls

- Keys are rate-limited per device per app — cache the `keyID`; don't regenerate per session.
- Fails silently on simulator — CI and tests need a bypass path.
- DeviceCheck bit-store is deprecated; App Attest is the modern successor.

---

## 13. Non-capability permissions (Camera, Mic, Photos, Location)

These are **Info.plist only** — no portal checkbox, no entitlement, no profile regen.

| API | Info.plist key | Status |
|---|---|---|
| Camera | `NSCameraUsageDescription` | ✅ set |
| Photo Library (read) | `NSPhotoLibraryUsageDescription` | ✅ set |
| Photo Library (write-only) | `NSPhotoLibraryAddUsageDescription` | not set (not needed) |
| Microphone | `NSMicrophoneUsageDescription` | ✅ set |
| Speech Recognition | `NSSpeechRecognitionUsageDescription` | ✅ set |
| Notifications | `NSUserNotificationUsageDescription` | ✅ set |
| Location (when-in-use) | `NSLocationWhenInUseUsageDescription` | not set (not needed yet) |
| HealthKit (if ever) | `NSHealthShareUsageDescription` + `NSHealthUpdateUsageDescription` + entitlement + App ID capability + `UIRequiredDeviceCapabilities: healthkit` | N/A |

HealthKit is the odd one out in this group — it requires the portal checkbox AND entitlement AND Info.plist strings. Everything else is pure Info.plist.

---

## 14. Diagnostics cheat-sheet

### "Is my entitlement actually in the IPA?"
```bash
codesign -d --entitlements :- path/to/Runner.app
```
Exact string `aps-environment` must appear. If absent, signing is broken, not APNs.

### "What's the user's push state?"
```bash
./bin/prod-script /tmp/inspect_push_leo.py
```
(Script in `/tmp/` — see push-diag debugging session for contents.)

### "Did the client send any ErrorReporter events?"
```bash
./bin/prod-script services/api/scripts/audit_errors.py \
    --service client --window 24h --top 50
```
`service='client'` rows are mirrored from `ErrorReporter.report` / `.log` on device. They land in `error_logs` via `POST /v1/users/me/client-errors`. If zero rows, either the app isn't running the new build, or the `/client-errors` route isn't deployed on the backend yet (we hit this — ECS task was 1 day stale).

### "Is the backend up to date?"
```bash
aws ecs describe-tasks --cluster palateful-prod \
  --tasks $(aws ecs list-tasks --cluster palateful-prod \
    --service-name palateful-api-prod --query 'taskArns[0]' --output text) \
  --query 'tasks[0].startedAt' --output text
```
If that timestamp is older than the commit you expect to be live, run `./bin/prod-deploy`.

### "Did my push actually send?"
Admin dashboard → Notifications → "Send test push". Returns `{outcome, tokens_registered, success_count, failure_count}`. The audit row lands at `service='audit'` in `error_logs`.

---

## 15. Xcode Cloud signing quirks

- **Use automatic signing.** Xcode Cloud fetches certificates + profiles on demand. Toggling a capability on an App ID → next CI build pulls a fresh profile. Works for **managed capabilities** (Push, Sign in with Apple, Associated Domains, App Groups, App Attest, HealthKit, etc.).
- **Don't mix manual + automatic.** The single most common Xcode Cloud failure mode is `project.pbxproj` having manual profile refs while Xcode Cloud expects automatic. If you see "Provisioning profile doesn't include XXX entitlement," verify the target's signing is automatic in both Debug and Release.
- **Re-running a build reuses the cached profile.** To pick up a portal change, trigger a **new** build (a trivial commit works).
- **dSYMs upload** happens in `ci_post_xcodebuild.sh` via `FirebaseCrashlytics/upload-symbols`. If Crashlytics stops receiving symbolicated crashes, check that script and `GoogleService-Info.plist` is still at `app/ios/Runner/GoogleService-Info.plist`.
- **Extension embedding** is verified in `ci_post_xcodebuild.sh` — if you add a new extension target, add an embedding verification line there too, or the IPA may pass CI but lack the extension on-device.

### When Xcode Cloud's automatic signing fails

Typical error: `Provisioning profile "iOS Team Provisioning Profile: com.palateful.palateful" doesn't include the com.apple.developer.XXX entitlement.`

Checklist:

1. Portal → Identifier → is capability X checked? If not: check, save.
2. Portal → Profiles → is there a profile newer than the capability-enable timestamp? If not: generate.
3. Xcode → target → Signing & Capabilities → panel shows "Automatic signing" with a recent date? If stale: toggle off/on.
4. Xcode Cloud → trigger a **new** build (not a re-run).
5. Local: `codesign -d --entitlements :-` on the downloaded IPA should list the entitlement.

Any missing link produces the same error surface with a different fix.

---

## Known unknowns (verify when you actually implement)

- **Firebase's APNs key upload UI**: docs name only the `.p8` + Key ID; community sources insist Team ID is a separate required field. Likely present but unverified in 2026 UI.
- **iOS 18 `ControlWidget` entitlement**: no entitlement appears to be required beyond standard widget extension signing, but this is based on the absence of docs, not a positive claim.
- **Xcode Cloud behavior for non-managed legacy entitlements**: most standard capabilities are managed. Esoteric migrations may not be — test empirically before relying on auto-refresh.
