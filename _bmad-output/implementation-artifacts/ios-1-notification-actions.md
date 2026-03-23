# Story iOS.1: Notification Actions — Timer + Meal Reminders

Status: done

## Story

As a user,
I want to long-press a cooking timer notification and see "Add 2 Minutes", "Add 5 Minutes", and "Reset Timer" action buttons,
so that I can manage timers without opening the app while my hands are covered in flour.

## Acceptance Criteria

1. Cooking timer notifications have a `cooking_timer` category with actions: "Add 2 Minutes", "Add 5 Minutes", "Reset Timer", "Dismiss"
2. Tapping "Add 2 Minutes" schedules a new notification 2 minutes from now without opening the app
3. Tapping "Add 5 Minutes" schedules a new notification 5 minutes from now
4. Tapping "Reset Timer" restarts the timer with the original duration
5. Meal reminder notifications have a `meal_reminder` category with actions: "Start Cooking", "View Recipe", "Snooze 15 min"
6. "Start Cooking" opens cook mode for the recipe
7. "Snooze 15 min" reschedules the reminder for 15 minutes later
8. Notification grouping: shopping list notifications grouped together, partner activity grouped together
9. Timer notifications marked as time-sensitive (`interruptionLevel: .timeSensitive`)

## Tasks / Subtasks

- [x] Task 1: Register notification categories (AC: #1, #5)
  - [x] Modify `app/lib/core/services/cook_timer_notification_service.dart`
  - [x] Define `DarwinNotificationCategory('cooking_timer')` with 4 actions:
    - `DarwinNotificationAction.plain('TIMER_ADD_2_MIN', 'Add 2 Minutes')`
    - `DarwinNotificationAction.plain('TIMER_ADD_5_MIN', 'Add 5 Minutes')`
    - `DarwinNotificationAction.plain('TIMER_RESET', 'Reset Timer')`
    - `DarwinNotificationAction.destructive('TIMER_DISMISS', 'Dismiss')`
  - [x] Define `DarwinNotificationCategory('meal_reminder')` with 3 actions:
    - `DarwinNotificationAction.plain('MEAL_START_COOKING', 'Start Cooking', options: {.foreground})`
    - `DarwinNotificationAction.plain('MEAL_VIEW_RECIPE', 'View Recipe', options: {.foreground})`
    - `DarwinNotificationAction.plain('MEAL_SNOOZE_15', 'Snooze 15 min')`
  - [x] Pass categories in `DarwinInitializationSettings(notificationCategories: [...])`

- [x] Task 2: Assign categories to notifications (AC: #1, #5, #9)
  - [x] Timer notifications: set `categoryIdentifier: 'cooking_timer'`
  - [x] Timer notifications: set `interruptionLevel: InterruptionLevel.timeSensitive`
  - [x] Meal reminder notifications: set `categoryIdentifier: 'meal_reminder'`

- [x] Task 3: Handle notification actions (AC: #2, #3, #4, #6, #7)
  - [x] Implement `onDidReceiveNotificationResponse` handler for action callbacks
  - [x] `TIMER_ADD_2_MIN`: extract original notification data, schedule new notification for `DateTime.now() + 2 min`
  - [x] `TIMER_ADD_5_MIN`: same with 5 minutes
  - [x] `TIMER_RESET`: extract original duration from notification payload, schedule new notification for full duration
  - [x] `MEAL_START_COOKING`: navigate to cook mode with recipe ID from payload
  - [x] `MEAL_VIEW_RECIPE`: navigate to recipe detail with recipe ID
  - [x] `MEAL_SNOOZE_15`: schedule new notification for 15 minutes later with same payload
  - [x] For background actions (add time, snooze): handle without launching full UI

- [x] Task 4: Store timer metadata in notification payload (AC: #2, #3, #4)
  - [x] When scheduling timer notifications, include in payload:
    - `original_duration_seconds` (for reset)
    - `timer_label` (for display)
    - `recipe_id` (for navigation)
    - `step_index` (for cook mode navigation)

- [x] Task 5: Notification grouping (AC: #8)
  - [x] Set `threadIdentifier` on notifications:
    - Shopping list notifications: `'shopping_${listId}'`
    - Partner activity: `'partner_activity'`
    - Import notifications: `'import_${jobId}'`
    - Timer notifications: `'cooking_timer'`

## Dev Notes

- `flutter_local_notifications` already supports `DarwinNotificationCategory` and `DarwinNotificationAction` — this is configuration, not new infrastructure
- The trickiest part is background action handling: "Add 2 min" needs to work without launching the Dart isolate. Consider using the native iOS notification handler via `AppDelegate.swift` for simple reschedule actions
- Timer payload needs to carry enough data to recreate/modify the timer
- Existing `CookTimerNotificationService` at `app/lib/core/services/cook_timer_notification_service.dart` is the primary file to modify
- No new Xcode targets needed — this all works within the existing app target

### References

- [Investigation: 09-ios-native-features.md — Notification Actions section]
- [Epic: epic-ios-native.md]
