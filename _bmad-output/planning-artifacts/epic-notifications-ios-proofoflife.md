<!-- refined via party-mode 2026-04-17 -->
# Epic: Notifications — iOS Proof-of-Life

## Overview

Palateful has most of a notification pipeline already: `firebase_messaging` initialized in Flutter (via `PushNotificationService` at `app/lib/core/services/push_notification_service.dart`, booted from `main.dart:133-136`), FCM token registration hitting the backend, a full `PushNotificationService` in `libraries/utils/utils/services/push_notification.py` with 15 event types and 9+ event callsites across recipe-book / meal-event / shopping-list / friends / invitations code paths, and Terraform that plumbs `FIREBASE_CREDENTIALS_JSON` from AWS Secrets Manager into both API and Worker ECS tasks. **None of it has ever fired on the user's phone.**

The gap is at the edges: iOS never uploaded an APNs auth key to Firebase Console so Firebase couldn't forward a push to iOS even if it tried, the bare `AppDelegate.swift` does not wire `FirebaseApp`, `Messaging.messaging().delegate`, or the APNs-token forwarding callbacks (so even when the `firebase_messaging` Flutter plugin auto-calls `registerForRemoteNotifications()` under the hood, nothing bridges the APNs device token back into Firebase cleanly), `.env.example` doesn't mention `FIREBASE_CREDENTIALS_JSON` / `FIREBASE_CREDENTIALS_PATH` so local dev runs with no creds and no log trace of what would have been sent, and send callsites swallow failures silently so nobody knows what's broken when a push is expected but none arrives.

**Goal:** a push notification arrives on Leo's iPhone. That's it. Once proven, real event triggers (import-complete, partner activity) get flipped on in a follow-up. This epic delivers the plumbing + a deterministic verification button + the docs + a dogfood script so the path can be re-verified on any future device or environment in under five minutes.

## Locked Decisions (inherited + added)

**Inherited from home-polish party-mode (do not re-litigate):**
- Route matching in Flutter uses GoRouter's `matchedLocation` (path strings), not `RouteSettings.name`. The existing tap-handler at `push_notification_service.dart:178-244` already routes via path strings (`/cart`, `/profile`, `/recipe-books/:id`, etc.) — confirmed consistent, no changes needed to the handler in this epic.
- Cold-launch detection uses `GoRouter.of(context).canPop()` (not raw `Navigator.of(context).canPop()`) anywhere the test-push payload needs a deep-link fallback.
- Admin-action audit rows are written to `error_logs` with `service="audit"`, mirroring the `services/api/scripts/promote_admin.py` shape.
- Inline fixes over new abstractions. No feature flags, no backwards-compat shims.

**Inherited from the 2026-04-17 user batch (do not re-litigate):**
- **iOS-first scope.** Android polish is deferred; Android gets `firebase_messaging` defaults.
- **Admin test-push button is THE verification trigger.** Real event triggers remain OFF during this epic.
- **Onboarding permission prompt is the only auto-prompt.** No nagging banners, no re-prompts.
- **Local dev is log-only.** No Firebase creds required to run the stack locally.
- **APNs .p8 auth key** (not certificate), uploaded to Firebase Console.

**Added by this workshop:**
- **The native AppDelegate drives `registerForRemoteNotifications()`, not Flutter.** (See "Key design call" below.) Flutter owns the permission-prompt UI via `firebase_messaging`; iOS native owns APNs registration as a side-effect of permission grant, via a `UNUserNotificationCenter` delegate callback. This removes the Flutter→native race the draft had.
- **Test-push defaults to `?force=true`.** `NotificationType.TEST` bypasses per-user prefs AND quiet hours by default. An admin diagnostic that refuses to fire during quiet hours is not a diagnostic.
- **Test-push endpoint is rate-limited** to 10 calls / minute / admin_user_id to keep the audit log / FCM quota safe from a jittery admin finger.
- **Dogfood script is a shipped artifact.** A 4-step checklist at the bottom of this epic (and mirrored in `docs/PUSH_NOTIFICATIONS.md`) is what Leo runs to prove the round-trip. The DoD points at it.

## End-user flow

### Flow A — First launch (new user)

1. User downloads Palateful from TestFlight (or later, App Store) and opens it.
2. User signs in via Auth0.
3. **New step:** Before the "Choose vibes" onboarding screen, a notification-permission prompt appears. Headline: "Stay in the loop." Body copy references the *categories* of events the app will eventually notify about — honestly phrased for the proof-of-life phase (see UX refinement in notif-4). Two buttons: **Turn On** and **Not Now**.
4. User taps **Turn On** → Flutter calls `FirebaseMessaging.instance.requestPermission(...)` → OS shows the permission sheet → user grants → native `UNUserNotificationCenter` delegate fires with `authorized`, which triggers `UIApplication.shared.registerForRemoteNotifications()` on the main thread → APNs device token arrives in `didRegisterForRemoteNotificationsWithDeviceToken` → Flutter obtains FCM token via `FirebaseMessaging.instance.getToken()` → token is POSTed to `/api/v1/user/push-tokens` and persisted.
5. If the user **denies** at the OS prompt (after tapping "Turn On"), the app records `notification_permission_status = "declined"` based on the actual `AuthorizationStatus` returned from `requestPermission`, NOT based on which button they tapped. This keeps the in-app state accurate even when intent and outcome diverge.
6. Onboarding continues to "Choose vibes" as before.
7. User who taps **Not Now** proceeds directly to "Choose vibes" — no OS prompt fires, `notification_permission_status = "declined"` persisted.

### Flow B — Admin verifies the round-trip (Leo, on his phone)

1. Leo (admin) opens the admin dashboard on his laptop.
2. Under a new "Notifications" section, he sees "Send test push to myself" with a button.
3. He taps the button. The dashboard shows a spinner, then "Sent (msg-id: …)".
4. Within a second or two, his iPhone (foreground OR background OR killed) shows a push: title "Palateful test push", body "If you see this, pushes work 🍽️".
5. Tapping the push opens Palateful to the home screen (deep-link payload is `route: "/"`, handled by the existing tap-router which already uses path strings).
6. If anything fails — no device tokens registered, FCM rejects the send, APNs returns an error — the dashboard surfaces the specific error message, AND a row is written to `error_logs` with `service="push_notifications"` (operational error), plus a SEPARATE `service="audit"` row capturing the admin action itself (see backend changes for the two-row rationale).
7. **Quiet hours:** the default test-push call passes `?force=true`, so it fires regardless. The endpoint response includes a `quiet_hours_active: bool` field so Leo can tell he was inside quiet hours and the force bypass kicked in.

### Flow C — Dev running locally (no real pushes)

1. Dev runs `docker compose up`. The API boots without `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_PATH` in `.env`.
2. `PushNotificationService.__init__` detects no creds, logs once at INFO: `push_notifications: running in log-only mode (no FIREBASE_CREDENTIALS_JSON / FIREBASE_CREDENTIALS_PATH); no pushes will be delivered`.
3. When dev code triggers a push via existing callsites (or the admin test-push button), the service logs the payload it *would* have sent — type, target user_id, title, body, data — at INFO level, and returns `{log_only: true, message_id: "log-only", target: ...}` without touching the FCM SDK.
4. Dev never needs to provision Firebase credentials to work on the rest of the app. Real pushes only fire on deployed ECS tasks.

## Key design call — APNs registration ordering

The draft had Flutter call `requestPermission` and the native AppDelegate separately call `registerForRemoteNotifications()`, which is race-prone (the native call can happen before permission lands, and it relies on Flutter coordinating the moment). The correct shape:

- **Flutter owns the permission UX.** It calls `FirebaseMessaging.instance.requestPermission(...)` when the user taps "Turn On" in onboarding.
- **`firebase_messaging` on iOS auto-calls `UIApplication.shared.registerForRemoteNotifications()`** when permission is granted — the Flutter plugin does this under the hood. (This is documented plugin behavior; confirmed at the plugin's iOS source. See open questions for the sanity-check step in dev.) So in theory, the AppDelegate does not need to call `registerForRemoteNotifications()` at all.
- **What the AppDelegate DOES need:** the APNs-token bridge. When iOS hands the device token to `didRegisterForRemoteNotificationsWithDeviceToken`, our AppDelegate forwards it to `Messaging.messaging().apnsToken = deviceToken` so FCM can pair APNs with the FCM token. Without this forwarding step, FCM has no APNs pairing and pushes fail silently at the APNs leg. **This is the one thing the bare AppDelegate is actually missing.**
- **Belt-and-braces fallback:** if after Flutter's `requestPermission` we observe that `registerForRemoteNotifications()` was not called by the plugin (e.g., plugin version regresses), the AppDelegate's `UNUserNotificationCenter` delegate observes the authorization state and calls `registerForRemoteNotifications()` itself, idempotently. This is a safety net, not the primary path, and it's gated by an authorization-state check so we never register without permission.
- **First-launch race:** if the user closes the app mid-onboarding before granting permission, the native side MUST NOT call `registerForRemoteNotifications()`. The authorization-state gate on the fallback handles this — `registerForRemoteNotifications()` is only called when `authorizationStatus == .authorized` OR `.provisional`. This is verified in notif-1 AC.

## Frontend changes

- `app/ios/Runner/AppDelegate.swift`
  - Import `FirebaseCore` and `FirebaseMessaging`.
  - In `application(_:didFinishLaunchingWithOptions:)`:
    - Do NOT call `FirebaseApp.configure()` — the Flutter plugin calls it on first `firebase_messaging` access. Double-calling logs a warning; leave this to the plugin.
    - Set `Messaging.messaging().delegate = self`.
    - Set `UNUserNotificationCenter.current().delegate = self`.
    - Do NOT call `UIApplication.shared.registerForRemoteNotifications()` unconditionally here — the `firebase_messaging` plugin does this after permission is granted. Calling it unconditionally at launch would register without permission (iOS returns no-op, but log noise and conceptual muddle).
  - Implement `application(_:didRegisterForRemoteNotificationsWithDeviceToken:)` — forward the device token to `Messaging.messaging().apnsToken = deviceToken`. **This is the load-bearing change.**
  - Implement `application(_:didFailToRegisterForRemoteNotificationsWithError:)` — log the error so it surfaces in Xcode / Console.
  - Implement the `UNUserNotificationCenter` delegate safety net: on authorization state transition to `.authorized` or `.provisional`, if `UIApplication.shared.isRegisteredForRemoteNotifications` is false, call `registerForRemoteNotifications()` on the main thread. Idempotent.
- `app/ios/Runner/Info.plist`
  - Add `UIBackgroundModes` array with entry `remote-notification`.
  - Add `NSUserNotificationUsageDescription` — Apple requires a user-facing reason string. Copy: "Palateful sends notifications when your recipe imports finish and when partners update shared books or shopping lists."
- `app/ios/Runner/Runner.entitlements`
  - Audit says it already has `aps-environment = production`. Verify debug builds on TestFlight/dev still work; if dev builds require a separate entitlement value, use Xcode build-variant entitlements. No code change unless misconfigured.
  - **iOS 17+ notification categories:** scope for this epic is general (non-time-sensitive) notifications only. We do NOT request `UNUserNotificationCenter`'s time-sensitive entitlement; all test pushes and future real events ship as standard categories. Time-sensitive is a follow-up decision tied to specific event types (e.g., "partner is cooking now") and deliberately out of scope.
- `app/lib/features/onboarding/`
  - New onboarding step: `notification_permission_step.dart` — a single screen with "Turn On / Not Now".
  - Wire into the onboarding flow before "Choose vibes".
  - "Turn On" invokes `FirebaseMessaging.instance.requestPermission(alert: true, badge: true, sound: true, provisional: false)` and proceeds regardless of the OS outcome. "Not Now" proceeds immediately with no system prompt.
  - The recorded `notification_permission_status` reflects the `AuthorizationStatus` returned from `requestPermission` (`authorized` → "granted", `denied` → "declined", `provisional` → "provisional", `notDetermined` → "declined" since the user tapped Not Now), NOT which button was pressed.
- `app/lib/core/services/push_notification_service.dart`
  - Verify existing `requestPermission` / token-registration path still works after the AppDelegate changes. Add `debugPrint` on token arrival and on permission-grant outcome so dogfood diagnosis doesn't need a debugger.
  - Tap-handler at lines 178-244 is already path-string-based (`/cart`, `/profile`, `/recipe-books/:id`, etc.) and needs no changes for the proof-of-life payload.

## Backend changes

- `libraries/utils/utils/services/push_notification.py`
  - **Log-only mode:** in `__init__`, if neither `FIREBASE_CREDENTIALS_JSON` nor `FIREBASE_CREDENTIALS_PATH` is set, set `self._log_only = True` and emit a single INFO log. Short-circuit all `send_*` methods when `self._log_only`, logging the payload and returning `{log_only: True, message_id: "log-only", target: ...}`.
  - **Send logging:** every `send_to_token` / `send_to_tokens` / `send_to_user` / `send_to_users` call logs INFO on success (type, target user_id(s), FCM message-id) and ERROR on failure (type, target, FCM response body, exception chain). Keep swallowing failures (existing behavior — never raise out); just stop swallowing *silently*.
  - **Quiet-hours suppression logs:** when `_is_quiet_hours` suppresses a send, log INFO with reason so "nothing fired" is distinguishable from "fired but was quiet".
  - Add `NotificationType.TEST` enum member. Per-user preferences DO NOT apply to TEST (admin diagnostic). Quiet hours apply by default but are bypassed when `force=True` is passed to `send_to_user`.
- `services/api/src/api/v1/admin/notifications.py` (NEW)
  - `POST /api/v1/admin/notifications/test-push`
    - Body (all optional): `{title?: str, body?: str, target_user_id?: UUID}`. Defaults: `title="Palateful test push"`, `body="If you see this, pushes work 🍽️"`, `target_user_id=current_user.id`.
    - Query param: `?force=true` (default true). When true, bypasses quiet hours. When explicitly set to false, quiet hours apply and the response carries `suppressed_by_quiet_hours: true` with no message-id.
    - Auth: admin-only via the existing `is_admin` dependency.
    - **Rate limit: 10 requests / minute / admin_user_id.** In-memory sliding window is acceptable for this epic (the admin surface is tiny). Over-limit returns 429 with `{ok: false, error: "rate_limited", retry_after_s: int}`.
    - Behavior: calls `PushNotificationService.send_to_user(target, type=NotificationType.TEST, title=..., body=..., data={"source": "admin_test", "route": "/"}, force=force)`.
    - Response 200: `{ok: true, message_id: str, target_user_id: UUID, log_only: bool, quiet_hours_active: bool}`.
    - Response 4xx/5xx: structured error `{ok: false, error: str, detail: dict}`.
  - **Two-row audit pattern:**
    - Row 1 (always): `error_logs` with `service="audit"`, `error_type="AdminTestPushAudit"`, `user_id=target_user_id`, `error_message="admin:test_push target=<uuid> by admin_user=<uuid> result=<ok|err> message_id=<id>"`. Mirrors the `promote_admin.py` shape exactly (same column set, same `service="audit"` sentinel) — this is the admin-action audit row.
    - Row 2 (only on send failure): `error_logs` with `service="push_notifications"`, `error_type="PushSendFailure"`, context containing the FCM response body. This is the *operational* error row that would also be written by a non-admin send failure; it's how the troubleshooting checklist in `docs/PUSH_NOTIFICATIONS.md` finds failures. Keeping these two rows distinct means the audit dashboard isn't noisy with FCM 4xx responses and the ops dashboard isn't polluted with admin-action metadata.
- `services/api/src/api/v1/user/complete_onboarding.py`
  - Accept optional `notification_permission_status: "granted" | "declined" | "provisional" | null`.
  - Persist to the user model.
- `services/api/src/db/models/user.py`
  - Add `notification_permission_status` column (nullable string, default null).
- `services/migrator/migrations/2026XXXX_user_notification_permission_status.py`
  - New idempotent migration: add column to `users`.

## Infrastructure changes

- `.env.example`
  - Add push-notification section. Document BOTH `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` (the service reads both; either is a valid prod/staging config):
    ```
    # Push notifications (Firebase Cloud Messaging)
    # Optional. When BOTH are unset, PushNotificationService runs in log-only mode
    # and pushes are not delivered to devices. In production, FIREBASE_CREDENTIALS_JSON
    # is provided via AWS Secrets Manager (see terraform/modules/ecs). Set
    # FIREBASE_CREDENTIALS_PATH instead if you have the service-account JSON on disk
    # (useful for staging where you mount the file).
    # FIREBASE_CREDENTIALS_JSON=
    # FIREBASE_CREDENTIALS_PATH=
    ```
- `docker-compose.yml`
  - Forward `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` into BOTH the `api` and `worker` containers when present in the shell env. Worker already consumes the var in ECS; local-dev behavior should match so a dev who *does* want real pushes (rare) can opt in by setting the var in their shell. Vars are optional — absence triggers log-only mode.
- `docs/PUSH_NOTIFICATIONS.md` — NEW. Content:
  - Firebase project setup summary.
  - **APNs auth key upload procedure:** step-by-step — go to developer.apple.com → Keys → create a new key with APNs enabled → download the `.p8` → upload to Firebase Console → Project Settings → Cloud Messaging → Apple app configuration. Include Team ID and Key ID fields and how to find them (Team ID on the membership page; Key ID on the key listing).
  - **APNs .p8 rotation procedure:** when the key is revoked or Apple access changes, the new `.p8` is generated the same way; the old one is deleted from Firebase Console AFTER the new one is uploaded and verified (Firebase supports multiple APNs keys during transition). Record the Key ID of the current key in this doc's "Last verified" header so rotation has a paper trail.
  - iOS entitlements / Info.plist requirements.
  - Local dev behavior (log-only, no creds required).
  - Production credential flow (Secrets Manager → ECS env var → service init).
  - Troubleshooting: "I tapped test push and nothing happened" checklist — registered device tokens, Firebase Console delivery logs, `error_logs` where `service="push_notifications"` rows, quiet-hours suppression logs, app foreground/background state, APNs environment mismatch (dev vs prod entitlement).
  - **Dogfood checklist** (mirror of the section at the bottom of this epic).
- Terraform: no changes. Prod already has the Firebase secret ARN `arn:aws:secretsmanager:us-east-1:592349850338:secret:palateful-firebase-prod-jy4C1N` wired into API + Worker ECS task definitions.
- Admin web dashboard:
  - Add a "Notifications" section with "Send test push to myself" button wired to the new endpoint. Display result inline (incl. `log_only`, `quiet_hours_active`, and 429 rate-limit).

## Design Principles (refined via party-mode 2026-04-17)

1. **Proof of life, not full coverage.** One push must arrive on Leo's iPhone. Event-trigger rollout is out of scope.
2. **Admin diagnostic is the verification trigger.** A deterministic path (admin test-push, rate-limited, audit-logged) beats waiting for real events to fire.
3. **Verification is codified.** The dogfood checklist at the bottom of this epic is a 4-step procedure Leo runs to prove the round-trip. It's a shipped artifact (mirrored in `docs/PUSH_NOTIFICATIONS.md`), not tribal knowledge.
4. **Native owns APNs pairing; Flutter owns permission.** The AppDelegate's only load-bearing job is forwarding the APNs device token to `Messaging.messaging().apnsToken`. `firebase_messaging` on iOS auto-calls `registerForRemoteNotifications()` post-grant; the AppDelegate's `UNUserNotificationCenter` observer is a belt-and-braces safety net, gated on authorization state to prevent first-launch races.
5. **Silent dev is free dev.** No-op-with-logs in local is the default when creds are absent. Both `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` are supported and documented.
6. **Never swallow silently.** Every send attempt logs its outcome. Quiet-hours suppression, invalid tokens, FCM 4xx/5xx — all visible in `error_logs` with `service="push_notifications"`.
7. **Admin actions audit-log separately from operational errors.** Two rows on failure: `service="audit"` for the admin action, `service="push_notifications"` for the send failure. Clean dashboards, queryable history.
8. **Test-push is rate-limited.** 10/min/admin. Audit logs and FCM quota are not punching bags for a jittery admin finger.
9. **Honest onboarding copy.** The notification-permission step describes categories of future events ("import finishes", "shared-book updates", "shared-list updates") rather than promising specific features that are OFF this epic. The in-app state reflects the OS `AuthorizationStatus`, not which button the user tapped.
10. **Docs are a shipped artifact.** `docs/PUSH_NOTIFICATIONS.md` exists with a "Last verified" header including the current APNs Key ID. Re-verification on a new device / environment is a doc lookup, not a rediscovery.
11. **iOS-first, Android-later.** Android gets `firebase_messaging` defaults.
12. **Inherit locked decisions.** No feature flags, no compat shims, inline fixes over abstractions (carries forward from home-polish).

## File structure (expected)

```
app/ios/Runner/
├── AppDelegate.swift                              # MODIFIED — Messaging delegate, UNUserNotificationCenter delegate, APNs-token forwarding, belt-and-braces registration safety net
├── Info.plist                                     # MODIFIED — UIBackgroundModes + NSUserNotificationUsageDescription
└── Runner.entitlements                            # VERIFY — aps-environment for dev+prod

app/lib/features/onboarding/
├── onboarding_controller.dart                     # MODIFIED — insert notification step before vibes
└── steps/
    └── notification_permission_step.dart          # NEW — Turn On / Not Now single-screen step

app/lib/core/services/
└── push_notification_service.dart                 # MODIFIED — debugPrint on token + permission outcome; tap-handler untouched (already path-string based)

libraries/utils/utils/services/
└── push_notification.py                           # MODIFIED — log-only mode, per-send logging, NotificationType.TEST, force flag

services/api/src/api/v1/admin/
└── notifications.py                               # NEW — POST /admin/notifications/test-push (rate-limited, two-row audit)

services/api/src/api/v1/user/
└── complete_onboarding.py                         # MODIFIED — accept notification_permission_status

services/api/src/db/models/
└── user.py                                        # MODIFIED — new column

services/migrator/migrations/
└── 2026XXXX_user_notification_permission_status.py  # NEW — idempotent add column

.env.example                                       # MODIFIED — document FIREBASE_CREDENTIALS_JSON and FIREBASE_CREDENTIALS_PATH (optional)
docker-compose.yml                                 # MODIFIED — forward FIREBASE_CREDENTIALS_{JSON,PATH} into api + worker containers
docs/PUSH_NOTIFICATIONS.md                         # NEW — APNs + Firebase + troubleshooting + dogfood + rotation guide

apps/admin/ (path to confirm)
└── src/pages/notifications.tsx                    # NEW — "Send test push to myself" button
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| notif-1 | iOS AppDelegate + Info.plist + APNs registration | 🔴 P0 | 0.5 d | None |
| notif-2 | Backend log-only mode + send-failure logging + docs | 🔴 P0 | 0.5 d | None (parallel with notif-1) |
| notif-3 | Admin test-push endpoint + dashboard button | 🔴 P0 | 0.5–1 d | notif-1 (to verify end-to-end on device), notif-2 (to log the send) |
| notif-4 | Onboarding notification-permission step | 🟡 P1 | 0.5–1 d | notif-1 (needs APNs reg path working so Turn On actually registers a token) |

**Total estimated effort: 2–3 days**

---

## Story notif-1: iOS AppDelegate + Info.plist + APNs registration

As Leo,
I want iOS to bridge APNs device tokens to Firebase Messaging correctly, without racing Flutter's permission-prompt flow,
so that Firebase has a live delivery path for any push the backend fires at me and first-launch edge cases don't trigger spurious registration.

### Acceptance Criteria

1. `AppDelegate.swift` imports `FirebaseCore` and `FirebaseMessaging`.
2. In `application(_:didFinishLaunchingWithOptions:)`:
   - Do NOT call `FirebaseApp.configure()`. Rely on the Flutter plugin's call. (If audit finds the plugin no longer auto-configures in a future version, revisit.)
   - Set `Messaging.messaging().delegate = self`.
   - Set `UNUserNotificationCenter.current().delegate = self`.
   - Do NOT call `UIApplication.shared.registerForRemoteNotifications()` here. Permission is still unknown at this point.
3. `application(_:didRegisterForRemoteNotificationsWithDeviceToken:)` is implemented and forwards `Messaging.messaging().apnsToken = deviceToken`. **This is the one load-bearing change.** Without it, FCM has no APNs pairing.
4. `application(_:didFailToRegisterForRemoteNotificationsWithError:)` is implemented and logs the error with `print("APNs register failed: \(error)")`.
5. The `UNUserNotificationCenter` delegate observes authorization-status transitions: when status becomes `.authorized` or `.provisional` AND `UIApplication.shared.isRegisteredForRemoteNotifications` is false, call `UIApplication.shared.registerForRemoteNotifications()` on the main thread. This is a belt-and-braces safety net in case the Flutter plugin regresses; it is NOT the primary trigger.
6. **First-launch race guard:** the safety-net handler above checks authorization status BEFORE calling `registerForRemoteNotifications()`. If the user killed the app mid-onboarding, the status will be `.notDetermined` and the safety net is a no-op. Add a unit-style comment on the handler explaining this.
7. `Info.plist` has `UIBackgroundModes` array containing `remote-notification`.
8. `Info.plist` has `NSUserNotificationUsageDescription` with user-facing copy.
9. `Runner.entitlements` has `aps-environment` set appropriately — verify TestFlight + dev both work. If a split entitlement is required, use build-variant entitlements.
10. APNs auth key (`.p8`) is uploaded to Firebase Console. **Ops step, not code.** Guided by `docs/PUSH_NOTIFICATIONS.md` created in notif-2. Key ID is recorded in the doc's "Last verified" header.
11. **Manual verification checklist** (explicit — this does NOT pass via CI):
    - [ ] Install TestFlight build on a real iPhone.
    - [ ] Sign in, grant notification permission (via notif-4 onboarding step or iOS Settings if notif-4 not shipped yet).
    - [ ] In Xcode console, confirm: "APNs device token received" log line from AppDelegate.
    - [ ] In Xcode console, confirm: "Messaging apnsToken set" or equivalent Firebase log.
    - [ ] In Flutter debug output, confirm: FCM token obtained (debugPrint added in `push_notification_service.dart`).
    - [ ] In backend logs, confirm: `POST /api/v1/user/push-tokens` landed with the device's FCM token.
12. No Android changes. Android continues on `firebase_messaging` defaults.

### Key Files
- Modify: `app/ios/Runner/AppDelegate.swift`
- Modify: `app/ios/Runner/Info.plist`
- Verify: `app/ios/Runner/Runner.entitlements`
- Dogfood checklist: `docs/PUSH_NOTIFICATIONS.md` (created in notif-2)

### Risks / notes

- `FirebaseApp.configure()` is called by the `firebase_messaging` Flutter plugin on first access. Calling it in AppDelegate would double-configure and log a warning. Leaving it to the plugin matches the plugin's documented behavior.
- `firebase_messaging` on iOS auto-calls `UIApplication.shared.registerForRemoteNotifications()` when `requestPermission` returns authorized. The AppDelegate's safety net exists only to survive a plugin regression; confirm the plugin behavior during dev by verifying the auto-call happens *before* the safety-net handler would fire (log both, compare order).
- APNs token vs FCM token: AppDelegate forwards APNs to `Messaging`. Flutter gets the FCM token via `FirebaseMessaging.instance.getToken()`. Both arrive via different callbacks; both must succeed for the round-trip.

---

## Story notif-2: Backend log-only mode + send-failure logging + docs

As Leo,
I want the backend's PushNotificationService to either send real pushes or log what it would have sent, never silently no-op, with both `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` supported,
so that I can tell from logs whether a missing push is a credentials problem, a quiet-hours suppression, an invalid token, an FCM rejection, or a bug — and so that local dev never requires Firebase credentials.

### Acceptance Criteria

1. `PushNotificationService.__init__`:
   - If neither `FIREBASE_CREDENTIALS_JSON` nor `FIREBASE_CREDENTIALS_PATH` is set, set `self._log_only = True`, DO NOT initialize the Firebase Admin SDK, and log once at INFO.
   - If creds are present but malformed, log ERROR with parse failure and fall back to log-only. Never raise from `__init__`.
2. `send_to_token` / `send_to_tokens` / `send_to_user` / `send_to_users`:
   - If `self._log_only`, log INFO with payload shape (`type`, `target`, `title`, `body`, `data`) and return `{log_only: True, message_id: "log-only", target: ...}`.
   - Otherwise, call FCM. On success, log INFO (`type`, `target`, `message_id`). On failure, log ERROR (`type`, `target`, FCM exception class, FCM response body) and write an `error_logs` row with `service="push_notifications"`, `error_type="PushSendFailure"`. Return structured error. Never raise out.
3. Quiet-hours suppression: when `_is_quiet_hours` suppresses, log INFO with `{type, target, reason: "quiet_hours", window: ...}`.
4. Invalid-token cleanup (`_cleanup_invalid_tokens`): log INFO with removed token IDs, user_id, reason.
5. **`force` flag:** `send_to_user(...)` accepts `force: bool = False`. When true, bypass both per-user preferences AND quiet hours. (This is the affordance notif-3's admin endpoint uses.)
6. `.env.example` documents BOTH `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` as optional, with the log-only-mode comment.
7. `docker-compose.yml` forwards `FIREBASE_CREDENTIALS_JSON` and `FIREBASE_CREDENTIALS_PATH` into `api` and `worker` services when present in shell env.
8. `docs/PUSH_NOTIFICATIONS.md` is created with:
   - Architecture overview (Flutter → FCM → backend → Firebase Admin → APNs → device).
   - **APNs auth key upload procedure.**
   - **APNs .p8 rotation procedure** (upload new, verify, delete old; record current Key ID in "Last verified" header).
   - iOS requirements (Info.plist, entitlements).
   - Local dev behavior (log-only, both env vars supported).
   - Prod credential flow (Secrets Manager ARN, ECS wiring, reference `terraform/environments/prod/main.tf`).
   - Troubleshooting checklist.
   - **Dogfood checklist** (mirror of the section at the bottom of this epic).
   - `Last verified: 2026-04-17 — APNs Key ID: <fill in during notif-1 ops step>`.
9. **Backend unit tests** (the concrete shapes):
   - Test A: instantiate service with `FIREBASE_CREDENTIALS_JSON=""` and `FIREBASE_CREDENTIALS_PATH=""` → assert `_log_only=True`, assert Firebase SDK `initialize_app` NOT called (mock it), assert INFO log emitted once.
   - Test B: send in log-only mode → assert return is `{log_only: True, ...}`, assert FCM client NOT called, assert INFO log with payload.
   - Test C: send with mocked FCM raising `FirebaseError` → assert return is structured error, assert ERROR log emitted, assert `error_logs` row written with `service="push_notifications"`, assert no raise.
   - Test D: send with `force=True` during quiet hours → assert FCM client IS called (no suppression), assert no quiet-hours-suppression log.
   - Test E: send with `force=False` during quiet hours → assert FCM NOT called, assert quiet-hours suppression log.

### Key Files
- Modify: `libraries/utils/utils/services/push_notification.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Create: `docs/PUSH_NOTIFICATIONS.md`
- Test: `libraries/utils/tests/services/test_push_notification.py` (or project equivalent)

### Risks / notes

- `NotificationType.TEST` is added here (the enum is the single source of truth; notif-3 consumes it).
- Do not log raw FCM credentials or user PII beyond user_id. Payload title/body are user-facing and fine to log.
- `docs/PUSH_NOTIFICATIONS.md` "Last verified" header is the rotation paper trail; update on every APNs-related change.

---

## Story notif-3: Admin test-push endpoint + dashboard button

As Leo,
I want a one-click, rate-limited, audit-logged way to fire a real push to my own phone from the admin dashboard,
so that I can verify the round-trip works deterministically, diagnose which layer broke if it doesn't, and not risk spamming the audit log with a jittery finger.

### Acceptance Criteria

1. New admin endpoint `POST /api/v1/admin/notifications/test-push`.
   - Auth: admin-only via existing `is_admin` dependency.
   - Request body (all optional): `{title?: str, body?: str, target_user_id?: UUID}`. Defaults: title `"Palateful test push"`, body `"If you see this, pushes work 🍽️"`, target `current_user.id`.
   - Query param: `?force=true` (DEFAULT TRUE). When true, `NotificationType.TEST` bypasses both per-user prefs and quiet hours. When explicitly `?force=false`, quiet hours apply.
   - Behavior: calls `PushNotificationService.send_to_user(target, type=NotificationType.TEST, title=..., body=..., data={"source": "admin_test", "route": "/"}, force=force)`.
   - Response 200: `{ok: true, message_id: str, target_user_id: UUID, log_only: bool, quiet_hours_active: bool, suppressed_by_quiet_hours: bool}`.
   - Response 4xx/5xx: `{ok: false, error: str, detail: dict}` — pass through FCM response body.
2. **Rate limit: 10 requests / minute / admin_user_id.** In-memory sliding window. Over-limit returns 429 `{ok: false, error: "rate_limited", retry_after_s: int}`. Does NOT write an audit row (rate-limit hits are not admin actions).
3. `NotificationType.TEST`:
   - Bypasses per-user notification preferences always (diagnostic).
   - Bypasses quiet hours when `force=True` (default).
4. **Two-row audit pattern** (on every non-rate-limited call):
   - Row 1 (always): `error_logs` with `service="audit"`, `error_type="AdminTestPushAudit"`, `user_id=target_user_id`, message string `"admin:test_push target=<uuid> by admin_user=<uuid> result=<ok|err> message_id=<id>"`. Matches `promote_admin.py` shape exactly (same INSERT columns, same `service="audit"` sentinel).
   - Row 2 (only on send failure): `error_logs` with `service="push_notifications"`, `error_type="PushSendFailure"`, context with FCM response body. Written by `PushNotificationService` on failure per notif-2 AC 2.
5. Admin web dashboard "Notifications" section with "Send test push to myself" button:
   - POSTs to the endpoint (no body — defaults fire, `force=true`).
   - Spinner while in flight.
   - 200 + `log_only: false` → "✓ Sent (msg-id: …). Check your phone."
   - 200 + `log_only: true` → "Sent in log-only mode — check the API logs. Real FCM delivery requires `FIREBASE_CREDENTIALS_JSON` in prod." with link to `docs/PUSH_NOTIFICATIONS.md`.
   - 200 + `suppressed_by_quiet_hours: true` (only possible with `force=false`) → "Suppressed by quiet hours. Use the force flag (default) to bypass."
   - 429 → "Rate-limited. Retry in N seconds."
   - Other errors → error message + link to `error_logs` row if the dashboard has one.
6. **Integration test:** mock admin user + device token; hit endpoint; assert `send_to_user` called with expected args including `force=True`, assert `service="audit"` row written with expected shape.
7. **Manual verification checklist** (APNs registration does NOT pass via CI):
    - [ ] Admin dashboard renders button.
    - [ ] Click → spinner → success message with message-id.
    - [ ] Within 5 seconds, push lands on Leo's iPhone (foreground OR background OR killed).
    - [ ] Tapping push opens app to home screen.
    - [ ] `error_logs` has one `service="audit"` row with `error_type="AdminTestPushAudit"`.
    - [ ] Click button 11 times in quick succession → 11th returns 429.

### Key Files
- Create: `services/api/src/api/v1/admin/notifications.py`
- Modify: the admin router mount point to include the new router.
- Create: admin dashboard UI component — path TBD during dev (confirm with Story 12-4).
- Test: `services/api/tests/api/v1/admin/test_notifications.py`

### Risks / notes

- Admin dashboard location: confirm the admin app's routing during dev and add the section there. If the dashboard is embedded in the main Flutter app as an admin-only screen, add it there instead.
- `?force=true` is admin-only — document in endpoint docstring. Never expose from non-admin paths.
- If Leo hits the button without granting permission on his device, FCM returns a 200 but no tokens exist. Response must surface that ("FCM returned 200 but no device tokens registered for user"). This is a common first-time-setup failure mode; the troubleshooting doc covers it.

---

## Story notif-4: Onboarding notification-permission step

As a brand-new user,
I want to be asked once during onboarding whether I want notifications, with honest copy and a clear way to skip, and I want the app's recorded state to match what I actually did at the OS prompt,
so that I opt in with full context and the app doesn't lie to itself about whether I said yes.

### Acceptance Criteria

1. New onboarding step `notification_permission_step.dart` is inserted **between sign-in and "Choose vibes"**. Single screen.
2. Copy (honest about the proof-of-life phase — describes *categories* of future events, not specific features that are OFF this epic):
   - Headline: "Stay in the loop."
   - Body: "Palateful will only ping you about things that matter — when a recipe import you kicked off finishes, when a partner updates a shared book or shopping list, or when a friend shares something with you. You can turn this off any time in Settings."
   - Primary button: "Turn on notifications".
   - Secondary button: "Not now".
3. Primary button behavior:
   - Calls `FirebaseMessaging.instance.requestPermission(alert: true, badge: true, sound: true, provisional: false)`.
   - Proceeds to next step regardless of outcome.
   - **Records `notification_permission_status` based on the OS `AuthorizationStatus` return value, NOT the button pressed:**
     - `authorized` → `"granted"`
     - `provisional` → `"provisional"`
     - `denied` → `"declined"`
     - `notDetermined` → `"declined"` (the user saw the OS prompt and backed out)
   - Sends it in the onboarding-complete payload.
4. Secondary button behavior:
   - Does NOT call `requestPermission` — no OS prompt.
   - Records `notification_permission_status = "declined"`.
   - Proceeds.
5. **In-app state accuracy on denial after "Turn On":** if the user taps "Turn On" and then denies at the OS prompt, the recorded state is `"declined"` (per AC 3), and the onboarding flow does NOT re-prompt. A future Settings screen (out of scope) can provide a re-opt-in path.
6. Step is skipped on platforms where it doesn't apply (web, if re-enabled). iOS + Android run it once.
7. After onboarding, the app never auto-prompts again. Future re-opt-in via Profile → Settings → Notifications (out of scope).
8. Backend: `complete_onboarding` accepts `notification_permission_status` and persists to `users.notification_permission_status`. Migration shipped with this story.
9. **Integration test** (no real OS prompt — mock `firebase_messaging`):
   - Test A: progress onboarding → tap "Not now" → assert `requestPermission` NOT called, assert next step reached, assert `notification_permission_status = "declined"` on the completed user payload.
   - Test B: tap "Turn on" with mocked `requestPermission` returning `authorized` → assert `notification_permission_status = "granted"`.
   - Test C: tap "Turn on" with mocked `requestPermission` returning `denied` → assert `notification_permission_status = "declined"`.
   - Test D: tap "Turn on" with mocked `requestPermission` returning `provisional` → assert `notification_permission_status = "provisional"`.
   - iOS native APNs registration is NOT asserted in this test — that's covered by notif-1's manual verification checklist.
10. **Manual verification checklist:**
    - [ ] Fresh TestFlight install, sign in → notification step appears before "Choose vibes".
    - [ ] "Not now" → no OS prompt → "Choose vibes" next.
    - [ ] "Turn on notifications" → OS prompt → "Allow" → "Choose vibes" next → backend shows `notification_permission_status="granted"`.
    - [ ] Fresh install again → "Turn on notifications" → OS prompt → "Don't Allow" → backend shows `"declined"`.

### Key Files
- Create: `app/lib/features/onboarding/steps/notification_permission_step.dart`
- Modify: `app/lib/features/onboarding/onboarding_controller.dart`
- Modify: `services/api/src/api/v1/user/complete_onboarding.py`
- Modify: `services/api/src/db/models/user.py`
- Create: `services/migrator/migrations/2026XXXX_user_notification_permission_status.py`
- Test: `app/integration_test/onboarding_notification_step_test.dart`, `services/api/tests/api/v1/user/test_complete_onboarding.py`

### Risks / notes

- Copy is intentionally about categories ("partner updates a shared book or shopping list"), not specific events (e.g., "import-complete") — because real event triggers are OFF for this epic. When the event firehose flips on, copy can tighten.
- If user says "Not now" and later triggers a push-eligible event, iOS silently drops it. A follow-up story adds an in-app banner for `declined` users; out of scope here.
- The AppDelegate safety net (notif-1 AC 5-6) handles the case where `requestPermission` grants but for some reason `firebase_messaging` doesn't auto-call `registerForRemoteNotifications()`. Verify during dev that the normal path (plugin auto-call) fires before the safety net — log both, compare ordering in Xcode console.

## Dependencies

- **notif-1 blocks notif-3 verification** — no point running the test-push if APNs pairing isn't wired.
- **notif-1 blocks notif-4's real-push value** — the step works without APNs registered (permission grants still persist), but the user won't actually receive pushes until notif-1 lands.
- **notif-2 supports notif-3** — the admin button's response includes `log_only` and failure context that comes from notif-2's logging path.
- notif-2 and notif-1 are independent and parallelizable.

## Open questions for the user

- **`firebase_messaging` plugin auto-call confirmation:** the Flutter plugin's documented behavior is to call `UIApplication.shared.registerForRemoteNotifications()` on iOS after `requestPermission` returns authorized. This epic assumes that and makes the AppDelegate's explicit call a belt-and-braces safety net. If dev verification finds the plugin does NOT auto-call on the current pinned version, notif-1 AC 2 flips: the AppDelegate's `UNUserNotificationCenter` delegate becomes the primary trigger, not the safety net. (No code change to this epic — just a doc note in `docs/PUSH_NOTIFICATIONS.md` if it happens.)
- **Admin dashboard location:** where does the "Notifications" section live? Defaults to wherever Story 12-4 shipped. Confirm during dev.
- **Follow-up events priority:** which event types turn on first once this epic proves the round-trip? Default assumption: import-complete first (most frequent dogfood event), then partner-activity. Not blocking this epic.

## Definition of Done (Epic Level)

- Leo runs a TestFlight build on his iPhone, signs in, sees the onboarding notification-permission step, taps Turn On, grants permission at the OS prompt.
- iOS device logs show APNs registration success, APNs token forwarded to `Messaging`, FCM token obtained, token POSTed to backend.
- Leo opens the admin dashboard, taps "Send test push to myself", and within seconds sees a push land on his iPhone (foreground OR background OR killed).
- The admin endpoint writes one `service="audit"` row; on failure, a second `service="push_notifications"` row captures the FCM response.
- In local dev with no `FIREBASE_CREDENTIALS_JSON` / `FIREBASE_CREDENTIALS_PATH`, triggering any push callsite logs a "log-only" line and does not raise.
- `docs/PUSH_NOTIFICATIONS.md` is checked in with APNs upload procedure, rotation procedure, Last-verified header including current Key ID, iOS requirements, local dev, prod creds, troubleshooting, and dogfood checklist.
- **The dogfood checklist below has been run successfully, end-to-end, on Leo's iPhone.**
- Android is not worse than before this epic.

## Post-epic dogfood checklist

This is the 4-step procedure Leo runs to prove the round-trip end-to-end. Also mirrored in `docs/PUSH_NOTIFICATIONS.md` so re-verification on any future device or environment is a doc lookup, not a rediscovery. If any step fails, the troubleshooting checklist in `docs/PUSH_NOTIFICATIONS.md` is the first stop.

1. **Install + permission (phone).** Install the latest TestFlight build on iPhone. Sign in with Auth0. On the new onboarding permission step, tap "Turn on notifications". Grant at the OS prompt. Finish onboarding. In Xcode console or via `Console.app`, confirm three log lines in order: (a) `APNs device token received`, (b) `Messaging apnsToken set` (Firebase), (c) `FCM token: <...>` from Flutter `debugPrint`.
2. **Backend token persisted (laptop).** Query prod DB (or tail API logs around the onboarding time): confirm `POST /api/v1/user/push-tokens` landed and a `push_tokens` row exists for Leo's user_id with a non-null `fcm_token`.
3. **Admin test-push (laptop → phone).** Open the admin dashboard, navigate to the Notifications section, tap "Send test push to myself". Dashboard shows "✓ Sent (msg-id: …)". Within 5 seconds, phone displays a push with title "Palateful test push". Tap the push — app opens to home screen.
4. **Audit row + log verification (laptop).** Query `error_logs` for the most recent row with `service="audit"` and `error_type="AdminTestPushAudit"` — confirm it references Leo's user_id and the message-id from step 3. Tail the API log around the send time — confirm an INFO line `push_notifications: sent type=TEST target=<uuid> message_id=<id>`. Confirm NO row with `service="push_notifications"` and `error_type="PushSendFailure"` for the same message-id (which would indicate a send failure).

If all four steps pass, the round-trip is proven and the epic is Done. If any step fails, the failure is localized by which step broke:

- Step 1 fail → AppDelegate wiring or permission flow (notif-1 / notif-4).
- Step 2 fail → Flutter FCM-token-registration path, or backend `push-tokens` endpoint.
- Step 3 fail → admin endpoint (notif-3), Firebase Admin SDK creds in prod, APNs `.p8` key uploaded?, or per-user device-token lookup.
- Step 4 fail → audit-row insert (notif-3 backend) or log-formatting regression (notif-2).
