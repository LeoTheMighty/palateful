# Push notifications

**Last verified: 2026-04-17 — APNs Key ID: _&lt;fill in during notif-1 ops step&gt;_**

This doc is the runbook for Palateful's push-notification pipeline: architecture, local dev, production wiring, troubleshooting, and the end-to-end dogfood checklist that proves a push actually lands on a real device.

## Architecture

```
Flutter app (iOS)                    Backend (ECS: api + worker)
─────────────────                    ───────────────────────────
firebase_messaging plugin    ───▶    PushNotificationService
  · requestPermission               · send_to_user / send_to_users
  · getToken (FCM)                  · log-only fallback when no creds
  · onTokenRefresh                  · writes error_logs rows on failure
  · onMessage / onMessageOpenedApp
       │                                    │
       ▼                                    ▼
iOS native (AppDelegate.swift)       Firebase Admin SDK ──▶ FCM ──▶ APNs ──▶ device
  · didRegisterForRemoteNotifications
    forwards APNs token to Messaging.apnsToken
```

The backend never touches APNs directly. It calls Firebase Admin SDK (Python) with an FCM device token; Firebase forwards to APNs on iOS and to Google's push service on Android. The service is sync and fire-and-forget — send failures are logged but never raise to the caller.

## Local dev (no credentials, no real pushes)

The backend runs in **log-only mode** by default. If neither `FIREBASE_CREDENTIALS_JSON` nor `FIREBASE_CREDENTIALS_PATH` is set, `PushNotificationService.__init__` emits one INFO log:

```
push_notifications: running in log-only mode (no FIREBASE_CREDENTIALS_JSON / FIREBASE_CREDENTIALS_PATH); no pushes will be delivered
```

Every `send_*` call then logs what it **would have** sent and returns `{"log_only": true, "message_id": "log-only", ...}` without initializing the Firebase SDK. No creds needed to run the rest of the stack.

To opt-in to real pushes locally (rare — usually for iOS push UX work), set the env var in your shell (forwarded into `api` and `worker` by `docker-compose.yml`) or add to your `.env`:

```sh
export FIREBASE_CREDENTIALS_PATH=/abs/path/to/service-account.json
docker compose up
```

## Production (ECS)

`FIREBASE_CREDENTIALS_JSON` is injected into the `api` and `worker` ECS task definitions from AWS Secrets Manager. The secret ARN is:

```
arn:aws:secretsmanager:us-east-1:592349850338:secret:palateful-firebase-prod-jy4C1N
```

Terraform wires the secret into the task definition via `secrets = [{ name = "FIREBASE_CREDENTIALS_JSON", valueFrom = <secret_arn> }]`. No service-code change needed on rotation — the ECS task picks up the new secret on next deploy.

## iOS requirements

### Code (checked in)

- `app/ios/Runner/AppDelegate.swift` — forwards APNs device token to `Messaging.messaging().apnsToken`; safety-net `registerForRemoteNotifications()` in `applicationDidBecomeActive`.
- `app/ios/Runner/Info.plist`:
  - `UIBackgroundModes` array contains `remote-notification`
  - `NSUserNotificationUsageDescription` user-facing reason string
- `app/ios/Runner/Runner.entitlements`:
  - `aps-environment` = `production` (Xcode Cloud TestFlight + App Store). Dev builds via Xcode's "Capabilities → Push Notifications" auto-inject the dev entitlement.

### Manual config (Firebase Console)

The `.p8` APNs auth key MUST be uploaded to Firebase Console once. Firebase uses this key to authenticate with Apple's push service on our behalf. Without it, Firebase returns a 200 OK but the push never leaves the FCM-to-APNs bridge.

#### Upload procedure

1. Sign in to [developer.apple.com](https://developer.apple.com/account) with an account that has Admin or App Manager role on the Palateful team.
2. Navigate to **Certificates, Identifiers & Profiles → Keys**.
3. Click **+** to create a new key. Name: `Palateful APNs (<year-month>)`. Check **Apple Push Notifications service (APNs)**. Click Continue, then Register.
4. Download the `.p8` file. **Keep it safe — Apple only lets you download it once.** Note the **Key ID** shown on the key detail page.
5. Find the **Team ID** at [developer.apple.com → Membership](https://developer.apple.com/account#MembershipDetailsCard). It's the 10-character string.
6. Sign in to [console.firebase.google.com](https://console.firebase.google.com) → Palateful project.
7. Go to **Project Settings (gear icon) → Cloud Messaging** tab.
8. Under **Apple app configuration → APNs Authentication Key**, click **Upload**. Upload the `.p8`, enter the Key ID and Team ID, click Upload.
9. Update the "Last verified" header at the top of this doc with the new Key ID.

### Rotation procedure

When the current `.p8` key is revoked, Apple access changes, or the key is compromised:

1. Generate a NEW key following steps 2-5 of the Upload procedure above.
2. Upload the new key to Firebase Console **alongside the old one**. (Firebase supports up to two concurrent APNs keys during rotation.)
3. Verify pushes still work: run the dogfood checklist below end-to-end with the new key active. Wait at least 24h of normal traffic to catch any delivery regressions.
4. Once confident, delete the old key from Firebase Console first, then revoke it in Apple's developer portal (`developer.apple.com → Keys → select old key → Revoke`).
5. Update the "Last verified" header at the top of this doc with the new Key ID.

The "Last verified" header is the paper trail — every rotation updates it.

## Admin test-push (dogfood)

Production admins (`users.is_admin = true`) can fire a test push from the admin dashboard via `POST /api/v1/admin/notifications/test-push`. The endpoint:

- Sends `NotificationType.TEST` to the admin's own devices by default (or a target user if specified).
- Defaults to `?force=true` — bypasses quiet hours for diagnostic purposes.
- Rate-limited to 10 requests / minute / admin user.
- Writes an `error_logs` row with `service="audit"` on every call. Send failures additionally write a `service="push_notifications"` row with the FCM response body.

If the dashboard reports `log_only: true`, the API is running without Firebase credentials — check the ECS task definition's Secrets panel.

## Troubleshooting

"I tapped the test-push button and nothing happened."

Walk these in order:

1. **Dashboard response** — what did it say?
   - `log_only: true` → backend has no Firebase creds. Check ECS task env.
   - `suppressed_by_quiet_hours: true` → admin passed `?force=false` during your quiet hours. Retry with default (`?force=true`).
   - 429 → rate-limited. Wait a minute.
   - 4xx/5xx → inspect the `error_logs` row where `service="push_notifications"` and `error_type="PushSendFailure"`. The message contains the FCM exception class and response body.
2. **Push tokens registered** — query `users.push_tokens` for your user_id. If empty, the app never successfully registered a token. Check Xcode console for "APNs device token received" and "FCM token: …" lines. If missing, notification permission isn't granted (iOS Settings → Palateful → Notifications).
3. **Firebase Console delivery log** — Firebase Console → Cloud Messaging → look for a recent delivery attempt. If Firebase accepted the send but APNs returned an error, the log will show it.
4. **APNs environment mismatch** — TestFlight/App Store builds require `aps-environment=production`; dev builds signed locally require `development`. A mismatch = Apple silently drops the push. Verify `Runner.entitlements` matches the build signing.
5. **App foreground vs background** — confirm the app is in background OR killed. iOS does deliver pushes in the foreground, but iOS 15+ surfaces them as in-app banners rather than system alerts unless `UNUserNotificationCenter.willPresent` returns `[.banner, .sound]` (which the firebase_messaging plugin does). If a foreground push isn't visible, check the Flutter `_onForegroundMessage` handler.
6. **.p8 not uploaded** — if the Firebase Console shows the APNs key as missing, pushes never leave the FCM-to-APNs bridge. Upload per the procedure above.

If none of the above reveals the issue, grep the API log for `push_notifications:` around the send time — every send attempt logs its outcome.

## Dogfood checklist

The 4-step procedure to prove the round-trip end-to-end on a real device. If any step fails, the failing step narrows the layer.

1. **Install + permission (phone).** Install the latest TestFlight build on iPhone. Sign in with Auth0. On the onboarding permission step, tap "Turn on notifications". Grant at the OS prompt. Finish onboarding. In Xcode console (or Console.app with device filter = Palateful), confirm three log lines in order: (a) `APNs device token received`, (b) `FCM registration token` (Firebase), (c) `FCM token: <prefix>…` from Flutter.
2. **Backend token persisted (laptop).** Query prod DB (or tail API logs around the onboarding time): confirm `POST /api/v1/user/push-tokens` landed and `users.push_tokens` contains your device's FCM token for your user_id.
3. **Admin test-push (laptop → phone).** Open admin dashboard → Notifications → tap "Send test push to myself". Dashboard shows `✓ Sent (msg-id: …)`. Within 5 seconds, phone displays a push with title "Palateful test push". Tap the push — app opens to home screen.
4. **Audit row + log verification (laptop).** Query `error_logs` for the most recent row where `service="audit"` and `error_type="AdminTestPushAudit"` — confirm it references your user_id and the message-id from step 3. Tail the API log around the send time — confirm an INFO line `push_notifications: sent type=test message_id=<id>`. Confirm NO row with `service="push_notifications"` and `error_type="PushSendFailure"` for the same send (which would indicate a delivery failure).

If all four steps pass, the round-trip is proven. Failure localisation:

- **Step 1 fail** → AppDelegate wiring or Flutter permission flow. See `app/ios/Runner/AppDelegate.swift`, `app/lib/core/services/push_notification_service.dart`.
- **Step 2 fail** → Flutter FCM-token registration path, or backend `push-tokens` endpoint. See `services/api/src/api/v1/user/push_tokens.py`.
- **Step 3 fail** → admin endpoint, Firebase Admin SDK creds in prod, APNs `.p8` uploaded?, or user has no push tokens. See troubleshooting checklist.
- **Step 4 fail** → audit-row insert in admin endpoint, or log-formatting regression in `push_notification.py`.
