<!-- refined via party-mode 2026-04-18 -->
# Epic: Notifications — Push Diagnostics & Hardening

## Overview

The iOS proof-of-life epic (`epic-notifications-ios-proofoflife.md`) shipped the plumbing: AppDelegate APNs forwarding, `firebase_messaging` wiring, log-only backend mode, admin test-push endpoint, onboarding permission step. All four stories are `done` in `sprint-status.yaml`. Yet Leo — the primary admin/dogfood user — has **never been asked for notification permissions on iOS** and gets nothing from sign-out/sign-in cycles or toggling iOS Settings.

The trace that explains this:

1. **Onboarding one-time gate.** The permission step only runs for brand-new accounts (`has_completed_onboarding=false`). `onboarding_welcome_screen.dart:39-48` and `app_router.dart:103-106` auto-skip the entire onboarding flow for users who already finished it. Leo's account completed onboarding before notif-4 landed (or on a Not-Now tap), so he is permanently locked out of the prompt there.
2. **Boot-time prompt already exists — but fails silently.** `main.dart:135` calls `pushService.initialize()` (alias for `ensureRegistered()`) after auth. `ensureRegistered()` at `push_notification_service.dart:74` DOES prompt when status is `notDetermined`. In theory this should fire for Leo on every launch. In practice it's either (a) never being called (auth race, gate upstream), (b) swallowed silently at `push_notification_service.dart:104-107` (`debugPrint` is stripped in TestFlight release builds), or (c) being called but with a state that isn't `notDetermined` (Firebase reports something else pre-registration).
3. **Every failure is `debugPrint`.** `push_notification_service.dart` lines 83, 105, 124, 136, 140, 143, 149, 162, 164, 173, 175, 183, 213, 219, 229, 299, 301, 309, 311. Plus the iOS `AppDelegate.swift:39` `print(...)` for `didFailToRegisterForRemoteNotifications`. None of these reach Crashlytics. In a TestFlight build, there is zero observability into what actually went wrong.
4. **`denied` state has a UI path already** — `notification_preferences_screen.dart:474-525` renders a warning card with an "Open Settings" CTA. But (a) it only appears if the user navigates there, and (b) the user has no reason to navigate there if they were never asked in the first place.

**Goal:** make push notification failures *never silent*, and make the boot-time auto-prompt path robust enough that Leo gets the OS prompt on his next TestFlight launch. Every failure writes to Crashlytics via the existing `ErrorReporter` pipeline. Per-user push health is queryable by admin. No new user-facing UI beyond what already exists (the existing `_buildOsPermissionWarning` in Profile is the only user-visible surface this epic leaves in place).

## Locked Decisions (inherited + added)

**Inherited from `epic-notifications-ios-proofoflife` (do not re-litigate):**
- iOS-first scope. Android continues on `firebase_messaging` defaults.
- Admin test-push button is the canonical verification trigger.
- No feature flags, no backwards-compat shims, inline fixes.
- Two-row audit pattern for admin actions: `service="audit"` row + `service="push_notifications"` operational row on failure.
- `FIREBASE_CREDENTIALS_JSON` / `FIREBASE_CREDENTIALS_PATH` — both supported.

**Locked for this epic (from the pre-drafting user batch):**
- **Loud on `notDetermined`.** When an authed user past onboarding launches the app with OS permission status `notDetermined`, the app fires the OS prompt automatically. No banner, no ceremony, no gate. Today's `ensureRegistered()` already aims at this; the hardening is making sure it actually happens and doesn't silently drop.
- **`denied` state lives in Profile only.** No home-screen banner, no modal, no nag. The existing `_buildOsPermissionWarning` at `notification_preferences_screen.dart:474-525` is the sole user-visible surface. If a user is `denied` and never navigates to Profile → Notifications, that is an accepted outcome — the app does not chase them.
- **Admin-only diagnostic.** Per-user push health is queryable from the admin dashboard. No user-facing diagnostic screen. The existing admin "Send test push" panel grows to include health lookup for arbitrary users.
- **Errors route through `ErrorReporter`, not user toasts.** Every failure path (`push_notification_service.dart` + `AppDelegate.swift`) calls `ErrorReporter.report(...)` with an `area: "push"` tag. Users do NOT see toasts, dialogs, or banners for registration/token/permission failures. The only user-visible surface is the existing Profile → Notifications warning card for `denied`.

**Added by party-mode 2026-04-18:**
- **Boot-time auto-prompt is gated on `has_completed_onboarding == true`.** The party-mode UX lens surfaced a race: on a brand-new user's FIRST launch, auth succeeds before they reach the notif-4 onboarding step; `main.dart:135` calls `ensureRegistered()` which would see `notDetermined` and auto-prompt, preempting notif-4's carefully-designed onboarding flow. Fix: the boot-time `ensureRegistered()` call only *auto-prompts* when `has_completed_onboarding` is true. New users get notif-4; past-onboarding users (Leo's case) get the boot-time prompt. On the new-user path, `ensureRegistered()` still registers listeners + fetches the FCM token if permission was already granted — just doesn't itself call `requestPermission()`.
- **`PushNotificationService` singleton-scope retry counter.** The 3-attempt retry budget lives on the service instance registered in `getIt`. That instance is constructed once per process, so the counter correctly persists across `main.dart` boot call + `didChangeAppLifecycleState` resume calls + any Profile-screen-triggered calls within the same app-launch. Confirmed singleton in the existing DI setup; if a future refactor makes it non-singleton, this AC breaks and must be revisited.
- **`ensureRegistered` split into two behaviors.** A parameterized `autoPrompt: bool` is introduced: `ensureRegistered(autoPrompt: <bool>)`. Only the boot-path + resume-path callers with `has_completed_onboarding=true` pass `autoPrompt: true`. The Profile → Notifications toggle and notif-4 onboarding step pass `autoPrompt: false` (they call `requestPermission` directly elsewhere, or only want listener wiring + token refresh). This avoids accidental prompt-spam from non-onboarding call sites.
- **Crashlytics breadcrumb rate is acceptable.** ~8 breadcrumbs per `ensureRegistered` invocation × a handful of invocations per session is well within Crashlytics' in-memory breadcrumb budget (default 200 kept; cheap to emit; only flushed on crash/non-fatal). No throttling needed.
- **`error_logs` query for `recent_errors` uses `(user_id, created_at DESC)` composite ordering.** Confirm the existing index supports this; if only `(user_id)` exists, the query is still O(N per user) which is fine at the user-scoped scale (a single user has dozens of error rows, not millions). No new index in this epic.

## End-user flow

### Flow A — Leo (existing account, past-onboarding, `notDetermined` state) launches the next TestFlight build

1. Leo opens the app from TestFlight.
2. Auth rehydrates; he's already signed in, `has_completed_onboarding=true`.
3. `main.dart:135` calls `pushService.initialize()` after auth succeeds, which internally invokes `ensureRegistered(autoPrompt: hasCompletedOnboarding)`. Because Leo is past onboarding, `autoPrompt=true`.
4. `ensureRegistered()` queries OS permission status → `notDetermined`.
5. `ensureRegistered()` calls `FirebaseMessaging.instance.requestPermission(...)` → **OS prompt appears.**
6. Leo taps Allow → status becomes `authorized` → APNs registration fires → APNs token forwarded to FCM → FCM token obtained → `POST /v1/users/me/push-tokens` → backend stores token.
7. If any step after 5 fails (permission granted but token null, backend 4xx/5xx, etc.), the specific failure is reported to Crashlytics under `area: "push"` with a precise `operation:` tag (e.g. `"ensureRegistered.getToken"`, `"ensureRegistered.backendRegister"`). No toast, no banner. Admin can find it in Crashlytics dashboard.
8. If the prompt itself fails to appear (e.g. Firebase not ready, `requestPermission` returns `notDetermined` a second time), a Crashlytics non-fatal is recorded with the pre-prompt `AuthorizationStatus` + Firebase readiness state. On app resume, `ensureRegistered()` retries — up to 3 total attempts per app-launch. This is the "specifically ask for permissions if it would fail" from the requirements, translated into a concrete retry policy.

### Flow A' — Brand-new user's FIRST launch (onboarding race prevention)

1. Fresh TestFlight install, new account, sign in for the first time.
2. Auth rehydrates; `has_completed_onboarding=false`.
3. `main.dart:135` calls `pushService.initialize()` → `ensureRegistered(autoPrompt: false)` (because the user is pre-onboarding).
4. `ensureRegistered()` wires listeners, reads status (`notDetermined`), does NOT call `requestPermission()`. No OS prompt.
5. Router routes the user into onboarding. They reach the notif-4 step (already shipped). Notif-4 calls `requestPermission()` directly as designed.
6. After the user completes onboarding, `has_completed_onboarding=true` is persisted. On the next `didChangeAppLifecycleState: resumed` or next cold start, `ensureRegistered(autoPrompt: true)` sees the user is past onboarding; if they somehow ended up at `notDetermined` (unlikely but possible), the boot-path auto-prompt catches them.
7. This flow preserves notif-4's owned prompt UX while still hardening the past-onboarding path.

### Flow B — Leo (existing account, `denied` state — the worst case) launches

1. Leo opens the app. Auth rehydrates.
2. `ensureRegistered()` queries OS permission status → `denied`.
3. The service does NOT call `requestPermission()` (iOS will not re-prompt on `denied`; the call is a no-op).
4. A Crashlytics breadcrumb is recorded: `push.ensureRegistered: status=denied (skipping prompt)`. No error row — `denied` is a legitimate state.
5. Nothing user-visible happens on Home or Activity.
6. When Leo navigates to Profile → Notifications, the existing `_buildOsPermissionWarning` card appears (already shipped). It has an "Open Settings" button that deep-links to iOS Settings.
7. Leo flips notifications on in iOS Settings, returns to the app. `didChangeAppLifecycleState` at `main.dart:196-203` fires `ensureRegistered()` on resume. Status is now `authorized` → registration proceeds normally. A Crashlytics breadcrumb records the state transition.

### Flow C — Leo diagnoses a user reporting no pushes (admin)

1. A user (or Leo himself) reports "I'm not getting pushes".
2. Leo opens the admin dashboard → Notifications section.
3. In the new "Check user health" panel, he pastes the user's UUID (or email — the endpoint resolves either) and hits Check.
4. The panel renders:
   - **OS permission state** (from `users.notification_permission_status`): `granted` / `declined` / `provisional` / `null`.
   - **Push tokens registered**: count by device_type, with `last_seen_at` for each. "0 tokens registered" is a common root cause.
   - **Recent push errors** (last 10 `error_logs` where `service="push_notifications"` and `user_id = target`): error_type, message, timestamp. Includes `PushSendFailure` rows from the existing notif-2 code.
   - **Recent Crashlytics events for this user**: NOT queryable from backend (Crashlytics is a separate system). The panel instead shows a link-out to Crashlytics with the user's Auth0 ID pre-filtered.
   - **Last successful send** (if any): timestamp, notification type, FCM message-id — scanned from INFO logs if we're keeping a short ring buffer (TBD in party-mode) OR from a new `push_send_log` table if the log-ring approach is too fragile.
5. Leo hits "Send test push to this user" — reuses the existing notif-3 endpoint with `target_user_id=<UUID>`.
6. If the test push succeeds, the panel shows the message-id. If it fails, the panel shows the FCM response body and writes the usual two-row audit pattern.

### Flow D — Leo works on the app locally

1. Local dev unchanged from the proof-of-life epic. `FIREBASE_CREDENTIALS_JSON` unset → log-only mode.
2. Flutter-side `ErrorReporter.report(...)` calls still fire — they route to Crashlytics when Firebase is initialized, and to a `debugPrint` fallback when not (already the behavior of `error_reporter.dart:18`). Local dev sees the fallback prints; prod/TestFlight sees Crashlytics non-fatals.

## Key design calls

### 1. "Loud" means auto-prompt on boot when `notDetermined` AND past onboarding, plus bounded retry on resume

The parent epic already aimed at this. The hardening is:
- **Gate auto-prompt on `has_completed_onboarding == true`.** Added by party-mode. The new `ensureRegistered(autoPrompt: bool)` signature makes this explicit: callers decide whether the call may trigger the OS prompt or merely wires listeners and fetches the token. `main.dart` passes `autoPrompt: currentUser.has_completed_onboarding`. `didChangeAppLifecycleState: resumed` does the same. The Profile notifications toggle and notif-4 onboarding step pass `autoPrompt: false` (they own their own `requestPermission` path).
- **Guarantee `ensureRegistered()` is called even when Firebase initialization races auth rehydration.** Today it's called at `main.dart:135` after the auth-check block, which is correct, BUT if Firebase hasn't finished booting the `firebase_messaging` channel by the time `getNotificationSettings()` is awaited, the call may throw or return a stale state. The fix is to await `Firebase.initializeApp()` explicitly before `ensureRegistered()` in the boot sequence (or confirm it's already awaited upstream and assert that invariant via a `StateError` reported to Crashlytics).
- **Retry on resume, with a cap.** On `didChangeAppLifecycleState: resumed`, `ensureRegistered()` is already called. If status is still `notDetermined` AND `_requestAttempts < 3` AND `autoPrompt: true`, call `requestPermission` again. After 3 in-session attempts, stop retrying this launch (prevents prompt-spam if Firebase is broken). Counter lives on the `PushNotificationService` singleton, resets on cold start (process restart reconstructs the instance).
- **Report every transition to Crashlytics as a breadcrumb.** `ErrorReporter.log("push.ensureRegistered: status=<X> action=<Y>")` — free-form breadcrumbs so a Crashlytics non-fatal has context. Breadcrumb rate is acceptable per party-mode infra review (~8 per invocation, in-memory, only flushed on crash/non-fatal).

### 2. Errors: map every `debugPrint` to an `ErrorReporter.report` call with precise tags

The existing `ErrorReporter.report(error, stack, area:, operation:, extras:)` signature already supports the distinctions we need. For every `try / catch` in `push_notification_service.dart` and adjacent service methods, replace the bare `debugPrint` with:

```dart
ErrorReporter.report(
  e, st,
  area: 'push',
  operation: '<specific.operation>',
  extras: {
    'platform': Platform.isIOS ? 'ios' : 'android',
    'auth_status': <current AuthorizationStatus name>,
    // additional per-call-site context
  },
);
```

Specific call sites and their `operation:` tags (all in `push_notification_service.dart`):

| Line(s) | Today | Operation tag |
|---|---|---|
| 104-107 | `debugPrint('ensureRegistered failed: $e')` | `ensureRegistered.outer` |
| 140 | `debugPrint('FCM token: null (getToken returned nothing)')` | `getToken.nullAfterGranted` (NEW — today this is just a log; should be an error if permission was granted) |
| 142-144 | `debugPrint('Failed to get FCM token: $e')` | `getToken.exception` |
| 162-165 | `debugPrint('Failed to register push token: $e')` | `registerToken.backend` |
| 173-176 | `debugPrint('Failed to unregister push token: $e')` | `unregisterToken.backend` |
| 212-214 | `debugPrint('Failed to show foreground notification banner: $e')` | `foregroundBanner.show` |
| 299-302 | `subscribeToTopic` catch | `subscribeToTopic` |
| 309-312 | `unsubscribeFromTopic` catch | `unsubscribeToTopic` |
| 123-126 | `openOsSettings` catch | `openOsSettings` |

Plus the iOS native side (`app/ios/Runner/AppDelegate.swift`):

- `didFailToRegisterForRemoteNotificationsWithError` (currently `print(...)` at line ~39): add a Flutter MethodChannel call `push.apnsRegistrationFailed` with the NSError domain/code/description, handled on the Flutter side by a listener that reports to `ErrorReporter` with `area: 'push', operation: 'apns.registrationFailed'`.
- The `ensureAPNsRegistered()` safety net at ~line 44-65: if a registration attempt is made but no `didRegisterForRemoteNotificationsWithDeviceToken` callback fires within 10s, MethodChannel-report `apns.registrationTimeout`. This catches the silent-hang case where APNs is unreachable.

### 3. Admin diagnostic: one endpoint, one panel, no new tables

New endpoint `GET /api/v1/admin/notifications/health/:user_id` returns a single JSON blob:

```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "notification_permission_status": "granted" | "declined" | "provisional" | null,
  "push_tokens": [
    {"id": "uuid", "device_type": "ios", "fcm_token_prefix": "dX8k_3n...", "created_at": "...", "last_seen_at": "..."}
  ],
  "recent_errors": [
    {"timestamp": "...", "error_type": "PushSendFailure", "message": "...", "request_id": "..."}
  ],
  "last_successful_send_at": "..." | null,
  "last_successful_send_type": "import_complete" | null,
  "crashlytics_query_url": "https://console.firebase.google.com/.../crashlytics?user_id=<auth0_id>"
}
```

Two data sources:

- `users.notification_permission_status` — exists from notif-4.
- `push_tokens` table — already in schema.
- `error_logs` filtered by `user_id` AND `service="push_notifications"` — existing table, just a scoped query.
- `last_successful_send_*` — NOT stored today. Two options for party-mode to lock:
  - **Option A (preferred — cheap):** scan the last 7 days of INFO-level logs via CloudWatch Logs Insights and expose as `null` today; the endpoint returns `null` and the admin panel says "not tracked yet; see Crashlytics / FCM console". Ship without it; add later if actually useful.
  - **Option B:** new `push_send_log` table (user_id, type, message_id, sent_at, status). Writes on every non-log-only send via notif-2's pipeline. More ops load.
  - **Default: Option A.** Keep this epic scoped; ship "not tracked yet" and revisit if diagnosis calls actually need it.

Admin dashboard: extend the existing Notifications panel (from notif-3) with:
- An input: "User UUID or email".
- A "Check" button → GET /v1/admin/notifications/health/<id>.
- Render the JSON blob in a readable layout.
- Keep the existing "Send test push to myself" button; add a "Send test push to this user" button that appears after a health lookup. Reuses the existing endpoint with `target_user_id`.

## Frontend changes

- `app/lib/core/services/push_notification_service.dart` (MODIFIED):
  - Replace every `debugPrint` in a `catch` block with `ErrorReporter.report(e, st, area: 'push', operation: '<tag>', extras: {...})`. See the table above for tags.
  - Add breadcrumbs via `ErrorReporter.log(...)` at each state transition in `ensureRegistered` (e.g., "status=notDetermined → calling requestPermission", "status=authorized → getting FCM token", "status=denied → skipping").
  - In `ensureRegistered`, wrap the permission query + request in a retry loop bounded to 3 attempts per app-launch, separated by exponential backoff (1s, 2s, 4s). Counter is a `_requestAttempts` instance field; reset nowhere explicitly (it resets when the service is reconstructed on cold start, which is the intended scope).
  - Add explicit error path: if permission is granted but `getToken()` returns null (line 139-141), this is NOT a happy path — report it via `ErrorReporter.report` as `operation: 'getToken.nullAfterGranted'`.
  - Ensure `ensureRegistered` awaits `Firebase.initializeApp()` before the first `FirebaseMessaging` call — or explicitly asserts Firebase is initialized, raising a `StateError` caught and reported if not.
- `app/lib/core/services/push_notification_method_channel.dart` (NEW, or folded into `push_notification_service.dart`):
  - MethodChannel name: `palateful/push`.
  - Method: `apnsRegistrationFailed` — payload `{domain: String, code: Int, description: String}`. Handler reports via `ErrorReporter` with `area: 'push', operation: 'apns.registrationFailed'`.
  - Method: `apnsRegistrationTimeout` — payload `{}` (timer fired without `didRegisterForRemoteNotifications`). Handler reports via `ErrorReporter` with `area: 'push', operation: 'apns.registrationTimeout'`.
- `app/lib/features/profile/notification_preferences_screen.dart` — no UI changes, but `_handlePushToggle` at line 95-118 should also route failures through `ErrorReporter` (currently uses a SnackBar for backend save failures at line 165, which is fine — that's a user-visible action; keep it but ALSO call ErrorReporter).
- `app/lib/main.dart` — no structural changes. Confirm the boot order: `Firebase.initializeApp()` must complete before `pushService.initialize()` at line 135. Today it's called earlier in `main()`; assert/await.

## Backend changes

- `services/api/src/api/v1/admin/notifications.py` (MODIFIED — existing file from notif-3):
  - Add `GET /api/v1/admin/notifications/health/{user_id}` handler.
    - Auth: admin-only via existing `is_admin` dependency.
    - Accept UUID or email in the path (detect by format, query `users.id` or `users.email`).
    - Assemble and return the JSON blob described above.
    - No DB writes. Read-only query.
  - Optional: support `?limit=` on `recent_errors` (default 10, max 50).
- `libraries/utils/utils/services/push_notification.py` — no changes required for this epic. The `service="push_notifications"` error rows it writes today (from notif-2 AC 2) are what the admin endpoint queries.
- No new migrations. `users.notification_permission_status`, `push_tokens`, `error_logs` all exist.

## Infrastructure changes

- **None required.** Firebase project, APNs key, ECS env vars, Terraform — all already in place from the proof-of-life epic. Crashlytics is already configured (used by `ErrorReporter`).
- **Ops docs update:** `docs/PUSH_NOTIFICATIONS.md` gains a new "Diagnosing a user who reports no pushes" runbook section:
  1. Look up `GET /v1/admin/notifications/health/<user_id_or_email>` in the admin dashboard.
  2. Check `notification_permission_status`. If `declined` or `null`, the user needs to grant in-app (auto-prompt on next launch if `null`, Profile → Notifications → Open Settings if `denied`).
  3. Check `push_tokens` count. If 0, token registration is broken — see Crashlytics for `area: push, operation: registerToken.backend` events.
  4. Check `recent_errors`. `PushSendFailure` with FCM `UNREGISTERED` response → stale token; service will self-heal on next send via existing invalid-token cleanup.
  5. Open the `crashlytics_query_url` for this user's Auth0 ID — look at `area: push` events around the reported time.
  6. If still unclear, send a test push via the admin endpoint with `target_user_id=<id>`; diagnose based on the response.

## Design Principles (pre-party-mode)

1. **Never silent.** Every failure path in push registration / token / send calls `ErrorReporter.report` with precise tags. `debugPrint` is not an error-handling strategy in a production pipeline.
2. **Loud but not annoying.** Auto-prompt on `notDetermined` at boot. Do NOT nag `denied` users outside Profile.
3. **Admin-only diagnostic.** No user-facing health screen. Existing Profile → Notifications warning is the only user surface.
4. **No new tables in this epic.** All diagnostic data assembled from existing schema. `last_successful_send` ships as `null` initially; revisit if actually needed.
5. **Inherit from parent.** iOS-first, no feature flags, inline fixes, two-row audit pattern for admin actions, log-only mode in local dev.
6. **Retry, but bounded.** 3 in-session attempts on `ensureRegistered` if `notDetermined` persists. Breadcrumbs on every transition. No infinite loops.
7. **Native errors reach Crashlytics.** AppDelegate APNs failures MethodChannel-forward to Flutter, then to `ErrorReporter`. The iOS `print` statement is not a log destination.
8. **Docs are a shipped artifact.** The runbook in `docs/PUSH_NOTIFICATIONS.md` is how the next push-not-arriving report gets diagnosed in minutes, not days.

## File structure (expected)

```
app/lib/core/services/
├── push_notification_service.dart                   # MODIFIED — ErrorReporter integration, retry, breadcrumbs, MethodChannel listener
└── push_notification_method_channel.dart            # NEW (or folded in) — listener for iOS apns.* failures

app/lib/features/profile/
└── notification_preferences_screen.dart             # MODIFIED — ErrorReporter call on save-failure path

app/ios/Runner/
└── AppDelegate.swift                                # MODIFIED — didFailToRegisterForRemoteNotifications + APNs-timeout MethodChannel calls

services/api/src/api/v1/admin/
└── notifications.py                                 # MODIFIED — new GET /health/{user_id} handler

docs/
└── PUSH_NOTIFICATIONS.md                            # MODIFIED — "Diagnosing a user who reports no pushes" runbook
```

No new files (unless the Flutter MethodChannel listener is split out — stylistic; keep it folded into `push_notification_service.dart` for minimal surface area).

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| push-diag-1 | Flutter + iOS: route every push failure through `ErrorReporter` | 🔴 P0 | 0.5–1 d | None |
| push-diag-2 | Harden loud-on-boot prompt: retry, race-safe Firebase init, breadcrumbs | 🔴 P0 | 0.5 d | push-diag-1 (so the failures this exposes get reported) |
| push-diag-3 | Admin per-user push health endpoint + dashboard panel + runbook docs | 🟡 P1 | 0.5–1 d | None (parallelizable with push-diag-1/2) |

**Total estimated effort: 1.5–2.5 days**

---

## Story push-diag-1: Flutter + iOS — route every push failure through `ErrorReporter`

As Leo,
I want every failure in the push-notification pipeline (permission query, registration, token fetch, backend POST, APNs registration on native) to be reported to Crashlytics via `ErrorReporter` with precise `area:` / `operation:` tags,
so that the next TestFlight build's push silence is never a mystery — every dropped token, swallowed exception, or APNs failure surfaces in Crashlytics with enough context to diagnose.

### Acceptance Criteria

1. Every `catch` block in `app/lib/core/services/push_notification_service.dart` that currently uses `debugPrint` is replaced with a call to `ErrorReporter.report(e, st, area: 'push', operation: '<tag>', extras: {...})`. Specific tags per the table in the epic body. At least these sites:
   - `ensureRegistered` outer catch → `ensureRegistered.outer`
   - `_getAndRegisterToken` catch → `getToken.exception`
   - `_registerTokenWithBackend` catch → `registerToken.backend`
   - `unregisterToken` catch → `unregisterToken.backend`
   - `_onForegroundMessage` catch → `foregroundBanner.show`
   - `subscribeToTopic` catch → `subscribeToTopic`
   - `unsubscribeFromTopic` catch → `unsubscribeTopic`
   - `openOsSettings` catch → `openOsSettings`
2. Add an explicit error path when permission is granted but `getToken()` returns `null`:
   - `push_notification_service.dart:139-141` (`debugPrint('FCM token: null …')`) becomes `ErrorReporter.report(StateError('FCM token null after granted permission'), StackTrace.current, area: 'push', operation: 'getToken.nullAfterGranted', extras: {'platform': ...})`.
3. Every `ErrorReporter.report` call above includes `extras` with at minimum:
   - `platform`: `'ios'` or `'android'`.
   - `auth_status`: the current `AuthorizationStatus` name (call `getPermissionStatus()` if not already known in scope).
   - Where applicable: `fcm_token_prefix` (first 8 chars of current token, or `null`), `backend_status_code` (for backend 4xx/5xx).
4. `app/ios/Runner/AppDelegate.swift`:
   - `application(_:didFailToRegisterForRemoteNotificationsWithError:)` — the existing `print(...)` is replaced (or supplemented) with a MethodChannel invocation: `FlutterMethodChannel(name: "palateful/push", binaryMessenger: ...).invokeMethod("apnsRegistrationFailed", arguments: ["domain": nserror.domain, "code": nserror.code, "description": nserror.localizedDescription])`.
   - Add a timeout handler: after `ensureAPNsRegistered()` triggers `registerForRemoteNotifications()`, start a 10-second timer. If `didRegisterForRemoteNotificationsWithDeviceToken` has not fired, invoke `apnsRegistrationTimeout` on the same MethodChannel. Cancel the timer if the success callback fires first.
5. Flutter MethodChannel listener (in `push_notification_service.dart` or a sibling file `push_notification_method_channel.dart`):
   - Listens on `palateful/push` channel.
   - On `apnsRegistrationFailed` → `ErrorReporter.report(PlatformException(code: 'apns.registrationFailed', message: desc, details: {domain, code}), StackTrace.current, area: 'push', operation: 'apns.registrationFailed', extras: {'ios_error_domain': domain, 'ios_error_code': code})`.
   - On `apnsRegistrationTimeout` → `ErrorReporter.report(TimeoutException('APNs registration did not complete within 10s'), StackTrace.current, area: 'push', operation: 'apns.registrationTimeout', extras: {'auth_status': <current>})`.
   - Listener is registered in `ensureRegistered` (idempotent — guarded by `_listenersAttached`).
6. `notification_preferences_screen.dart:163-170` (save-preference failure catch) — supplement the existing SnackBar with an `ErrorReporter.report(e, st, area: 'push', operation: 'preferences.save')` call. Do not remove the SnackBar (user-visible action warrants user-visible feedback).
7. Flutter unit tests:
   - Test A: mock `FirebaseMessaging` to throw on `requestPermission` → assert `ErrorReporter.report` called with `area: 'push', operation: 'ensureRegistered.outer'`, assert the thrown object is passed through.
   - Test B: mock `getToken()` to return null after granted permission → assert `ErrorReporter.report` called with `operation: 'getToken.nullAfterGranted'`.
   - Test C: mock the backend API to throw → assert `operation: 'registerToken.backend'` with `extras.backend_status_code` populated (when the thrown exception is a DioException with a response).
   - `ErrorReporter` can be mocked via a test-only override or a `ReporterFacade` wrapper — whichever matches existing test patterns in the codebase (grep for `ErrorReporter` test usage; if no pattern exists, introduce one minimally in this story and reuse in push-diag-2).
8. iOS side: no unit tests (no unit-test harness for native iOS in this repo). Manual verification: induce an APNs failure (e.g., build on a simulator without APNs entitlement, or toggle airplane mode mid-registration) and confirm the Crashlytics dashboard shows a non-fatal with `area: push, operation: apns.registrationFailed` or `apns.registrationTimeout`.
9. **Manual verification checklist** (TestFlight build on Leo's iPhone):
   - [ ] Install TestFlight build with all push-diag-1 changes.
   - [ ] Sign in. Observe Xcode console or Crashlytics for `push.*` breadcrumbs/events.
   - [ ] Force a backend 5xx (e.g., temporarily break the `/v1/users/me/push-tokens` route in a dev branch) → confirm Crashlytics shows a `push, registerToken.backend` event.
   - [ ] Revoke the Firebase config JSON in the test build → confirm `getToken` errors surface in Crashlytics.
10. No user-visible behavior change in this story (no new toasts, no new banners). Pure observability improvement.

### Key Files
- Modify: `app/lib/core/services/push_notification_service.dart`
- Modify: `app/lib/features/profile/notification_preferences_screen.dart`
- Modify: `app/ios/Runner/AppDelegate.swift`
- (Maybe create): `app/lib/core/services/push_notification_method_channel.dart`
- Test: `app/test/services/push_notification_service_test.dart` (or project equivalent)

### Risks / notes
- `ErrorReporter.report` is Crashlytics-backed in prod; in E2E/test modes it falls back to `debugPrint`. This is fine — the test assertion is "report was called with the right args", not "Crashlytics received it".
- Don't log full FCM tokens. Prefix-only (first 8 chars + ellipsis), mirroring the existing `push_notification_service.dart:136` style.
- MethodChannel name `palateful/push` — confirm no collision with existing channels (grep `FlutterMethodChannel` in `app/ios/Runner/`).
- If any `ErrorReporter.report` call fails (e.g., Firebase not initialized), the existing fallback to `debugPrint` in `error_reporter.dart` preserves today's behavior. Do NOT nest catches around the report calls — that defeats the point.

---

## Story push-diag-2: Harden loud-on-boot prompt — retry, race-safe Firebase init, breadcrumbs

As Leo,
I want the OS permission prompt to reliably appear on my next TestFlight launch when my status is `notDetermined`, with resilience against Firebase init races, permission query hiccups, and transient failures,
so that my pre-notif-4 account (and anyone else who was locked out of the onboarding prompt) actually gets asked — and every state transition is traceable in Crashlytics.

### Acceptance Criteria

1. `ensureRegistered({bool autoPrompt = false})` is the new signature. `autoPrompt` defaults to `false` so existing call sites are forced to consider the decision explicitly. `main.dart` passes `autoPrompt: currentUser.has_completed_onboarding` after auth rehydration; `didChangeAppLifecycleState: resumed` does the same. `notification_preferences_screen.dart`'s `_handlePushToggle` (line 104) passes `autoPrompt: true` (user explicitly tapped the toggle). Notif-4's onboarding step does NOT call `ensureRegistered` — it calls `FirebaseMessaging.instance.requestPermission` directly, unchanged.
2. `ensureRegistered` awaits `Firebase.initializeApp()` (or confirms via an assertion that `Firebase.apps.isNotEmpty`) before calling any `FirebaseMessaging` method. If Firebase isn't initialized, `ErrorReporter.report(StateError('Firebase not initialized in ensureRegistered'), StackTrace.current, area: 'push', operation: 'ensureRegistered.firebaseNotReady')` and return `notDetermined` without attempting.
3. **Retry policy** — bounded, in-session, only when `autoPrompt: true`:
   - New instance field `int _requestAttempts = 0` on `PushNotificationService` (singleton — confirmed via DI, constructed once per process).
   - When `ensureRegistered(autoPrompt: true)` observes `notDetermined` and `_requestAttempts < 3`:
     - Call `requestPermission`.
     - Increment `_requestAttempts`.
     - If the resulting status is STILL `notDetermined` (the OS prompt was suppressed or errored), `ErrorReporter.log('push: requestPermission returned notDetermined, attempts=$_requestAttempts')` and defer retry to next `didChangeAppLifecycleState: resumed` or cold start.
   - When `ensureRegistered(autoPrompt: true)` is re-entered on resume and `_requestAttempts >= 3`:
     - Do NOT retry this launch.
     - `ErrorReporter.log('push: max retry attempts reached this launch')`.
     - Return the current status.
   - When `ensureRegistered(autoPrompt: false)` is called and status is `notDetermined`, DO NOT call `requestPermission`. Wire listeners, return status. Breadcrumb: `'push: autoPrompt=false, skipping requestPermission'`.
   - Counter resets on cold start (singleton reconstructed when process restarts).
3. **Breadcrumbs on every transition** in `ensureRegistered`:
   - `ErrorReporter.log('push.ensureRegistered: entered, platform=<p>, attempts=$_requestAttempts')`.
   - `ErrorReporter.log('push.ensureRegistered: status=<X>')` after the initial query.
   - `ErrorReporter.log('push.ensureRegistered: calling requestPermission')` before the prompt.
   - `ErrorReporter.log('push.ensureRegistered: post-prompt status=<Y>')` after.
   - `ErrorReporter.log('push.ensureRegistered: granted, fetching token')` on the granted branch.
   - `ErrorReporter.log('push.ensureRegistered: denied, no-op')` on the denied branch.
   - `ErrorReporter.log('push.ensureRegistered: completed, final_status=<Z>, attempts=$_requestAttempts')` at the end.
4. `main.dart`:
   - Confirm `Firebase.initializeApp()` is awaited BEFORE the `pushService.initialize()` call at line 135. If not currently ordered correctly, reorder. Write a one-line comment referencing this story.
   - Change the call at line 135 from `pushService.initialize()` (no args) to `pushService.ensureRegistered(autoPrompt: currentUser.has_completed_onboarding)`. Remove `initialize()` or keep it as a thin shim that delegates with `autoPrompt: false` for non-opinionated callers.
   - The `didChangeAppLifecycleState: resumed` handler at line 196-203 is updated to pass `autoPrompt: currentUser.has_completed_onboarding`.
   - Access to `currentUser.has_completed_onboarding` in both call sites uses the existing `AuthService` state. If `AuthService` has not yet loaded the user profile at boot (pre-`/users/me` response), default `autoPrompt: false` and let the resume-path re-evaluate.
5. Flutter unit tests:
   - Test A: `Firebase.initializeApp` not called → `ensureRegistered(autoPrompt: true)` returns `notDetermined` AND reports `ensureRegistered.firebaseNotReady`.
   - Test B: Fresh service, permission starts at `notDetermined`, mock `requestPermission` to return `notDetermined` three times → assert `requestPermission` called exactly 3 times across 3 invocations of `ensureRegistered(autoPrompt: true)`, assert the 4th invocation does NOT call `requestPermission`.
   - Test C: Fresh service, permission starts at `notDetermined`, mock `requestPermission` to return `authorized` on first call → assert `requestPermission` called once, `_requestAttempts == 1`, subsequent `ensureRegistered(autoPrompt: true)` calls do NOT re-prompt (status is now authorized).
   - Test D: Permission at `denied` → assert `requestPermission` is NOT called, `_requestAttempts` stays at 0, and a breadcrumb with "denied, no-op" is emitted.
   - Test E: Breadcrumb ordering — mock `ErrorReporter.log` captures, run `ensureRegistered(autoPrompt: true)` with `notDetermined` → `authorized`, assert breadcrumbs fire in the documented order.
   - Test F: `ensureRegistered(autoPrompt: false)` with status `notDetermined` → assert `requestPermission` is NOT called, assert breadcrumb `'push: autoPrompt=false, skipping requestPermission'` emitted. Listeners still wired.
   - Test G: `ensureRegistered(autoPrompt: false)` with status `authorized` → assert `getToken` IS called and token registered with backend. `autoPrompt: false` does not block token refresh for already-granted users.
6. **Manual verification checklist** (this is the actual fix for Leo's reported issue):
   - [ ] Install TestFlight build with push-diag-1 + push-diag-2.
   - [ ] On Leo's iPhone (account already past onboarding, never prompted): open the app.
   - [ ] **OS permission prompt appears within 2 seconds of the home screen rendering.**
   - [ ] Grant → Xcode console / Crashlytics shows the full breadcrumb sequence.
   - [ ] Open admin dashboard, fire test-push to self, push lands.
   - [ ] Regression check 1: fresh install + new account → the boot-path does NOT prompt before onboarding (notif-4 owns the prompt). Onboarding permission step still fires as designed.
   - [ ] Regression check 2: existing user who already denied → no prompt fires (boot-path respects `denied`). Profile → Notifications still shows the Open Settings warning card.
7. No changes to `denied`-state handling — that's covered by the existing Profile warning (out of scope for this story, already works).

### Key Files
- Modify: `app/lib/core/services/push_notification_service.dart` (same file as push-diag-1; coordinate)
- Modify: `app/lib/main.dart` (if Firebase init ordering needs reordering — confirm first)
- Test: `app/test/services/push_notification_service_test.dart`

### Risks / notes
- The retry cap is deliberately low (3). Higher values risk looking like a prompt-spam loop if Firebase is permanently misbehaving.
- `_requestAttempts` is per-instance, not persisted. That's intentional — if the user force-quits and re-opens, a fresh attempt is warranted.
- If `requestPermission` returns `notDetermined` (which would be unusual — iOS typically returns `authorized` or `denied`), the OS prompt was effectively declined or suppressed. The breadcrumb captures this; no user-facing change.
- Do NOT prompt if the user is NOT authenticated. The existing `main.dart:133-135` gates on `authService.isAuthenticated`; keep that gate.

---

## Story push-diag-3: Admin per-user push health endpoint + dashboard panel + runbook docs

As Leo,
I want a single admin-panel query that tells me, for any user, their OS permission state, registered push tokens, recent push errors, and a link to their Crashlytics events,
so that the next "I'm not getting pushes" report is diagnosed in minutes — not by spelunking through `error_logs` with raw SQL.

### Acceptance Criteria

1. New backend endpoint: `GET /api/v1/admin/notifications/health/{user_id_or_email}`.
   - Auth: admin-only via existing `is_admin` dependency.
   - Path parameter: accepts either UUID or email (route parses; if parseable as UUID, queries `users.id`; else queries `users.email`).
   - 404 if no user matches.
   - Query params: `?error_limit=` (default 10, max 50).
   - Response 200:
     ```json
     {
       "user_id": "<uuid>",
       "email": "<email>",
       "notification_permission_status": "granted" | "declined" | "provisional" | null,
       "push_tokens": [
         {"id": "<uuid>", "device_type": "ios", "fcm_token_prefix": "<first 8 chars>...", "created_at": "<iso>", "last_seen_at": "<iso>"}
       ],
       "push_tokens_count": <int>,
       "recent_errors": [
         {"timestamp": "<iso>", "error_type": "PushSendFailure", "message": "<first 500 chars>", "request_id": "<str or null>"}
       ],
       "recent_errors_count": <int>,
       "last_successful_send_at": null,
       "last_successful_send_type": null,
       "crashlytics_query_url": "<https link with auth0_id filter>"
     }
     ```
     `last_successful_send_*` is explicitly `null` in this story (see Risks). The field exists in the schema so future additions don't break clients.
2. Endpoint is read-only. Writes ONE audit row to `error_logs` per request: `service="audit"`, `error_type="AdminPushHealthCheck"`, `user_id=<target>`, `error_message="admin:push_health_check target=<uuid> by admin_user=<uuid>"`. Matches the `promote_admin.py` and `notif-3` audit pattern exactly.
3. Admin dashboard extension (in the existing Notifications section from notif-3):
   - Input: text field labeled "User UUID or email".
   - "Check" button → GET `/v1/admin/notifications/health/<input>`.
   - Render the JSON in a readable two-column layout:
     - Left: labels — Permission, Token count, Error count, Last successful send.
     - Right: values, color-coded (green for granted/tokens-present; red for declined/zero-tokens/recent errors).
   - Expandable sections for the `push_tokens` array and `recent_errors` array.
   - A "Send test push to this user" button appears after a successful health lookup; wires to the existing notif-3 endpoint with `target_user_id=<looked-up user>`.
   - 404 → user-friendly "No user found with that UUID or email".
   - 5xx → error message + link to `error_logs` where `service="api"` and `path` contains `/admin/notifications/health`.
4. `docs/PUSH_NOTIFICATIONS.md` gains a new section: **"Diagnosing a user who reports no pushes"** runbook:
   1. Admin dashboard → Notifications → Check user's health.
   2. Interpret `notification_permission_status`:
      - `null` or `declined` → user was never asked OR declined. If `null`, the push-diag-2 auto-prompt will fire on their next launch. If `declined`, they need Profile → Notifications → Open Settings.
      - `granted` / `provisional` → permission's fine, continue.
   3. Interpret `push_tokens_count`:
      - `0` → token registration is broken. Check Crashlytics `area: push` events for this user. Likely culprits: APNs failure, FCM token null, backend POST failing.
      - `>0` → tokens exist, send path is the culprit.
   4. Interpret `recent_errors`:
      - `PushSendFailure` with FCM response containing `UNREGISTERED` → stale token; self-heals on next send cycle.
      - `PushSendFailure` with FCM response containing `INVALID_ARGUMENT` → likely payload issue; check the send callsite.
      - No errors + granted + tokens present + no pushes arriving → send a test push via the admin panel. If the test succeeds but real events don't, the event-side plumbing is broken (not this epic).
   5. Last resort: open `crashlytics_query_url` for the user and look at the last week of `area: push` events.
5. Backend integration tests:
   - Test A: admin hits endpoint with UUID → 200, response matches schema.
   - Test B: admin hits endpoint with email → 200, same user resolved.
   - Test C: admin hits endpoint with nonexistent UUID → 404.
   - Test D: non-admin hits endpoint → 403.
   - Test E: assert one `service="audit"` row written per call with correct shape.
6. **Manual verification checklist** (Leo on his laptop + phone):
   - [ ] Open admin dashboard → Notifications.
   - [ ] Paste his own user_id → Check → panel renders his status (`granted` after push-diag-2 fix), `push_tokens_count >= 1`, recent errors (if any).
   - [ ] Paste a nonexistent UUID → friendly 404 message.
   - [ ] Click "Send test push to this user" → push lands on his phone.
   - [ ] Verify one `service="audit"` row per health check + one per test-push.

### Key Files
- Modify: `services/api/src/api/v1/admin/notifications.py`
- Modify: admin dashboard Notifications component (path TBD — confirm during dev against whatever notif-3 shipped).
- Modify: `docs/PUSH_NOTIFICATIONS.md`
- Test: `services/api/tests/api/v1/admin/test_notifications.py` (extend the notif-3 test file).

### Risks / notes
- `last_successful_send_*` is `null` in this story. The fields are in the response schema for forward-compat. A follow-up story (not in this epic) can populate them by either scanning CloudWatch Logs Insights or adding a `push_send_log` table. **Do not add the table in this epic** — keep scope tight.
- Email lookup is case-insensitive (use `func.lower(users.email) == func.lower(<input>)`).
- `push_tokens.fcm_token_prefix` is first 8 characters; never return the full token.
- `recent_errors.message` is truncated to 500 characters server-side to keep the payload small.

## Dependencies

- **push-diag-1 supports push-diag-2.** push-diag-2 relies on `ErrorReporter` being wired into the push flow (push-diag-1) so its breadcrumbs actually land in Crashlytics. push-diag-1 CAN ship alone; push-diag-2 without push-diag-1 would still work but the breadcrumbs would only hit `debugPrint`.
- **push-diag-3 is independent.** Can be developed in parallel with 1+2.
- Depends on `epic-notifications-ios-proofoflife` (done) — the `notification_permission_status` column, `push_tokens` table, `error_logs` schema, `is_admin` dependency, and admin test-push endpoint all come from there.

## Open questions for the user

- **`last_successful_send` tracking: ship as `null` this epic, revisit later?** The epic proposes `null` for now (no new table, no CloudWatch scan). The field exists in the response schema so we don't break clients when it's populated. Confirm this is the right call, or escalate to "add the `push_send_log` table now so diagnosis is complete from day one".
- **MethodChannel name `palateful/push`** — any existing channel collision? (Will confirm via grep during dev if the user has no strong opinion; this is mostly a naming stylistic.)
- **Runbook ownership.** `docs/PUSH_NOTIFICATIONS.md` exists from notif-2. This epic appends a new section. If there's a preferred structure (e.g., runbook-as-separate-file), flag it before drafting the section.

## Definition of Done (Epic Level)

- On Leo's next TestFlight launch of his existing account, the iOS OS permission prompt appears within 2 seconds of the home screen rendering.
- If anything fails between permission grant and a successful backend push-token registration, a Crashlytics non-fatal event appears with `area: push` and a precise `operation:` tag.
- The iOS AppDelegate's APNs failures (both `didFailToRegister` and 10s registration timeout) reach Crashlytics via the MethodChannel bridge.
- Leo can, from the admin dashboard, look up any user's push health in one click and see their permission state, token count, recent errors, and a Crashlytics link.
- `docs/PUSH_NOTIFICATIONS.md` has a "Diagnosing a user who reports no pushes" runbook.
- Zero new user-facing UI surfaces beyond the existing Profile → Notifications warning.
- Retrospective acknowledges: if Leo's `notDetermined` → `granted` flow didn't work, the epic failed. The test is on his phone, not in CI.
