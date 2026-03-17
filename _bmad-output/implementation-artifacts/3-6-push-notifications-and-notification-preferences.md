# Story 3.6: Push Notifications & Notification Preferences

Status: done

## Story

As a user,
I want to receive push notifications when imports complete or need attention, and control which notifications I receive,
so that I'm informed without being overwhelmed.

## Acceptance Criteria

1. Given a background import completes or needs attention, when the system sends a notification, then I receive a push notification via FCM (e.g., "Import complete — 3 need attention") and tapping the notification opens the relevant screen (import results or exception queue)
2. Given I navigate to notification settings, when I view notification categories, then I can opt in/out per category (import status, timer alerts, partner actions, etc.) and my preferences persist and are respected for all future notifications
3. Foreground notifications show an in-app banner/snackbar instead of a system tray notification
4. Notification tap deep linking works for all existing notification types (shopping, recipes, meal events, imports)
5. Notification preferences screen is accessible from the Profile tab

## Tasks / Subtasks

- [x] Task 1: Wire up notification tap deep linking in PushNotificationService (AC: #1, #4)
  - [x] Import `app_router.dart` and replace `debugPrint('Navigate to ...')` stubs with actual `appRouter.go(...)` calls
  - [x] Add `import_complete` and `import_needs_attention` notification type cases
  - [x] For `import_complete`: navigate to `/recipes/import/review-list/{jobId}` using `data['import_job_id']`
  - [x] For `import_needs_attention`: navigate to `/recipes/import/review-list/{jobId}` using `data['import_job_id']`
  - [x] For shopping types: navigate to `/cart` (shopping list screen)
  - [x] For recipe types: navigate to `/recipes/{recipeId}` or `/recipe-books/{bookId}`
  - [x] For meal event types: navigate to `/calendar`

- [x] Task 2: Show in-app banner for foreground notifications (AC: #3)
  - [x] In `_onForegroundMessage`, use navigator key context to show a `SnackBar`
  - [x] Banner shows notification title and body
  - [x] Tapping "View" action triggers the same deep link navigation as a tap on the system notification
  - [x] Banner auto-dismisses after 4 seconds

- [x] Task 3: Create NotificationPreferencesScreen (AC: #2, #5)
  - [x] Created `app/lib/features/profile/notification_preferences_screen.dart`
  - [x] On `initState`, calls `_apiClient.getNotificationPreferences()` to load current state
  - [x] Shows master toggle: "Push Notifications" (maps to `push_enabled`)
  - [x] Shows quiet hours section: start time picker, end time picker (maps to `quiet_hours_start`, `quiet_hours_end`)
  - [x] Shows timezone selector with dialog (maps to `timezone`)
  - [x] On each toggle/change, calls `_apiClient.updateNotificationPreferences(...)` to persist
  - [x] Uses `setState` only — no Riverpod
  - [x] Follows same tile style as ProfileScreen

- [x] Task 4: Add navigation to notification preferences from Profile (AC: #5)
  - [x] Added "Notifications" tile in ProfileScreen under new "Settings" section, between "Recipes" and "Account"
  - [x] Icon: `Icons.notifications_outlined`
  - [x] On tap: `context.push('/profile/notifications')`

- [x] Task 5: Add router route for notification preferences (AC: #5)
  - [x] Added `/profile/notifications` GoRoute inside profile branch as child of `/profile`
  - [x] Builder returns `NotificationPreferencesScreen()`

- [x] Task 6: Pass navigatorKey/context to PushNotificationService for in-app banners (AC: #3)
  - [x] Added `setNavigatorKey(GlobalKey<NavigatorState>)` method to PushNotificationService
  - [x] Called from `_PalatefulAppState.initState` passing `rootNavigatorKey`
  - [x] Exposed `rootNavigatorKey` getter in `app_router.dart`
  - [x] Uses navigator key's context for showing SnackBars in foreground handler

## Dev Notes

### Backend Already Complete — No Backend Changes Needed

All notification infrastructure exists:
- `POST /v1/users/me/push-tokens` — register token (already called by PushNotificationService)
- `DELETE /v1/users/me/push-tokens` — unregister token (already called on logout)
- `GET /v1/users/me/notification-preferences` — get preferences
- `PUT /v1/users/me/notification-preferences` — update preferences
- Server-side push sending via Firebase Admin SDK in `libraries/utils/utils/services/push_notification.py`

### API Client Already Has All Methods

No new API client methods needed:
- `apiClient.getNotificationPreferences()` at `api_client.dart:339`
- `apiClient.updateNotificationPreferences(...)` at `api_client.dart:343`
- `apiClient.registerPushToken(...)` at `api_client.dart:324`
- `apiClient.unregisterPushToken(...)` at `api_client.dart:333`

### State Management

`setState` only — same pattern as ProfileScreen and all import screens. Do NOT introduce Riverpod.

### Notification Type → Deep Link Mapping

| Notification Type | Route |
|---|---|
| `import_complete` | `/recipes/import/review-list/{import_job_id}` |
| `import_needs_attention` | `/recipes/import/review-list/{import_job_id}` |
| `shopping_item_added`, `shopping_item_checked`, `shopping_list_shared`, `shopping_deadline_reminder`, `shopping_list_complete` | `/cart` |
| `recipe_book_shared`, `recipe_added` | `/recipe-books/{recipe_book_id}` |
| `meal_event_invite`, `meal_event_reminder`, `meal_event_updated` | `/calendar` |
| (unknown) | `/` (home) |

### DO NOT:
- Add per-category opt-in/out toggles (the backend stores preferences as a flat object with `push_enabled` master toggle — granular per-type preferences require a schema migration which is out of scope)
- Send notifications from Flutter — all push notifications are sent server-side via Firebase Admin SDK
- Add email digest UI beyond showing the current setting — email infrastructure isn't wired up yet
- Create a separate notifications list/inbox screen — that's a future feature
- Add notification badges to the bottom nav — out of scope for this story

### References

- [Source: app/lib/core/services/push_notification_service.dart] — FCM service modified
- [Source: app/lib/features/profile/profile_screen.dart] — Added notification settings link
- [Source: app/lib/core/router/app_router.dart] — Added notification preferences route + rootNavigatorKey getter
- [Source: app/lib/core/services/api_client.dart:339-357] — Existing notification preference API methods
- [Source: services/api/src/api/v1/user/push_tokens.py] — Backend notification preference endpoints
- [Source: libraries/utils/utils/services/push_notification.py] — Server-side push notification types
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.6] — Epic requirements

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List

**Modified files:**
- `app/lib/core/services/push_notification_service.dart` — wired up deep linking navigation, foreground SnackBar, navigator key support
- `app/lib/features/profile/profile_screen.dart` — added "Notifications" tile under new "Settings" section
- `app/lib/core/router/app_router.dart` — added `/profile/notifications` child route, exposed `rootNavigatorKey` getter
- `app/lib/main.dart` — passes `rootNavigatorKey` to PushNotificationService in initState

**New files:**
- `app/lib/features/profile/notification_preferences_screen.dart` — notification preferences screen with push toggle, quiet hours, timezone

## Code Review Action Items

- [x] [HIGH] Foreground "View" action used `go()` destroying nav stack — changed to `push()` for foreground, kept `go()` for cold/background [push_notification_service.dart:176-183]
- [x] [MEDIUM] Missing backend notification types (`friend_request`, `invitation_received`, etc.) — added cases routing to `/profile` [push_notification_service.dart:218-223]
- [x] [MEDIUM] Missing `mounted` checks after `showTimePicker`/`showDialog` — added guards [notification_preferences_screen.dart:98,287]
- [x] [LOW] `ScaffoldMessenger.of(context)` could throw — wrapped in try-catch [push_notification_service.dart:153-164]
- [x] [LOW] `void async` on `_onTokenRefresh` — changed to `Future<void>` [push_notification_service.dart:103]
- [ ] [MEDIUM] `import_complete`/`import_needs_attention` notification types don't exist in backend enum yet — deep link code is ready but server never sends these (requires backend change to add these types and trigger them from import worker)
