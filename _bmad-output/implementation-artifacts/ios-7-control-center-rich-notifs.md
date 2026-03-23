# Story iOS.7: Control Center + Rich Notifications

Status: done

## Story

As a user,
I want a quick timer button in Control Center and recipe photos in my notifications,
so that I can start a timer without opening the app and see what I'm cooking in notification previews.

## Acceptance Criteria

1. Control Center has a "Quick Timer" control: tap to start a 5-minute timer (or configurable)
2. Control Center has a "Shopping List" control: shows item count, tap opens shopping list
3. Import completion notifications include the recipe photo as a rich notification image
4. Meal reminder notifications include the recipe photo
5. Partner activity notifications ("Alex added Banana Bread") include the recipe thumbnail
6. Rich notifications fall back gracefully if image download fails (show text-only)

## Tasks / Subtasks

- [x] Task 1: Control Center — Quick Timer (AC: #1)
  - [x] Create WidgetKit `ControlWidget` for quick timer (iOS 18+)
  - [x] Uses `StartTimerIntent` from Story 6 with default 5 minutes
  - [x] Guard with `@available(iOS 18.0, *)`
  - [x] Circular control with timer SF Symbol

- [x] Task 2: Control Center — Shopping List (AC: #2)
  - [x] Create WidgetKit `ControlWidget` for shopping list count
  - [x] Reads count from UserDefaults (App Group)
  - [x] Tap opens app to shopping list
  - [x] Guard with `@available(iOS 18.0, *)`

- [x] Task 3: Rich notifications — Notification Service Extension (AC: #3, #4, #5, #6)
  - [x] Create Notification Service Extension target in Xcode
  - [x] When push notification arrives with `image_url` in payload:
    - Download image from URL
    - Create `UNNotificationAttachment` with downloaded image
    - Attach to notification
  - [x] Handle download failures gracefully — show notification without image
  - [x] Apply to notification types: import_complete, meal_reminder, partner_activity

- [x] Task 4: Backend — Include image URLs in push payloads (AC: #3, #4, #5)
  - [x] When creating push notifications for import completion: include recipe `photo_url`
  - [x] Meal reminders: include recipe `photo_url`
  - [x] Partner activity (new recipe added): include recipe `photo_url`
  - [x] Use a consistent key: `image_url` in the notification payload

- [x] Task 5: Add Notification Service Extension to Xcode project (AC: #3)
  - [x] Create new target: Notification Service Extension
  - [x] Add App Group capability (same group)
  - [x] Update Podfile if needed
  - [x] Update signing/provisioning

## Dev Notes

- Control Center controls (iOS 18+) are built on WidgetKit — if widgets from Story 3 are done, this is incremental
- Notification Service Extension runs before the notification is displayed — it can modify content (add images)
- Image download in the extension has a ~30 second time limit — recipe thumbnails should be small enough
- The `mutable-content: 1` flag must be set on the push notification for the extension to intercept it
- Firebase Cloud Messaging supports `image` field directly — check if `firebase_messaging` handles this automatically before building a custom extension
- Control Center controls are very new (iOS 18) — test availability carefully

### References

- [Investigation: 09-ios-native-features.md — Control Center + Rich Notifications sections]
- [Epic: epic-ios-native.md]
