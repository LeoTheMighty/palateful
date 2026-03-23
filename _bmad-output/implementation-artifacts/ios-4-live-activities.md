# Story iOS.4: Live Activities — Cooking Timer in Dynamic Island

Status: done

## Story

As a user,
I want my cooking timer to appear in the Dynamic Island and on my lock screen as a Live Activity,
so that I can see the countdown while using other apps or without unlocking my phone.

## Acceptance Criteria

1. Starting a cooking timer in cook mode launches a Live Activity
2. **Dynamic Island (compact)**: shows timer icon + countdown "04:32"
3. **Dynamic Island (expanded)**: shows timer label ("Step 3: Simmer"), countdown, progress ring, "Add 2 min" and "Cancel" buttons
4. **Lock Screen**: shows timer label, countdown, progress bar, recipe name
5. Live Activity updates every second with accurate countdown
6. When timer completes: Live Activity shows "Done!" with alert state
7. Multiple concurrent timers: each gets its own Live Activity
8. If user dismisses the Live Activity, the timer continues (notification still fires)
9. "Add 2 min" button on Dynamic Island expanded view adds time and updates the countdown
10. Live Activity ends 5 minutes after timer completion (auto-cleanup)

## Tasks / Subtasks

- [x] Task 1: Define ActivityAttributes (AC: #1)
  - [x] In Widget Extension: create `CookingTimerAttributes` struct
  - [x] Static data (set once): `timerLabel: String`, `recipeName: String`, `originalDuration: TimeInterval`
  - [x] Dynamic data (ContentState): `endTime: Date`, `isComplete: Bool`
  - [x] Register with ActivityKit

- [x] Task 2: SwiftUI — Live Activity layouts (AC: #2, #3, #4, #6)
  - [x] **Compact leading**: timer icon (SF Symbol `timer`)
  - [x] **Compact trailing**: countdown text using `Text(.endTime, style: .timer)`
  - [x] **Expanded**: timer label, countdown with progress ring, recipe name, action buttons
  - [x] **Lock screen banner**: timer label, recipe name, countdown, progress bar
  - [x] **Minimal**: small countdown number
  - [x] "Done!" state: green checkmark, "Timer Complete" text, dismiss hint

- [x] Task 3: Flutter — Start/update/end Live Activities (AC: #1, #5, #7, #10)
  - [x] In `cook_timer_notification_service.dart` or new `live_activity_service.dart`:
  - [x] `startTimerLiveActivity(label, recipeName, duration)` → starts Activity via `live_activities` package
  - [x] Pass `endTime` as `Date.now + remaining` so iOS handles countdown natively
  - [x] `endTimerLiveActivity(activityId)` → ends activity with "complete" final content
  - [x] Support multiple concurrent activities (one per timer)
  - [x] Auto-dismiss policy: `.after(TimeInterval(300))` (5 min after completion)
  - [x] Wire into existing `_startTimer()` and `_onTimerComplete()` methods in cook_mode_screen

- [x] Task 4: Interactive buttons on Dynamic Island (AC: #9)
  - [x] "Add 2 min" button in expanded Dynamic Island view
  - [x] Uses App Intent to handle the action:
    - Calculates new `endTime = currentEndTime + 120 seconds`
    - Updates the Live Activity content state
    - Schedules a new notification for the updated time
  - [x] "Cancel" button ends the Live Activity and cancels the notification

- [x] Task 5: Availability checks (AC: #1)
  - [x] Check `ActivityAuthorizationInfo().areActivitiesEnabled` before attempting to start
  - [x] Graceful fallback: if Live Activities not available (iOS <16.1 or disabled), timer still works via notifications only
  - [x] Guard all ActivityKit calls with `@available(iOS 16.1, *)`

## Dev Notes

- `live_activities` Flutter package handles the bridge to ActivityKit
- The countdown is handled natively by iOS using `Text(.endTime, style: .timer)` — no per-second updates needed from Flutter
- Dynamic Island is hardware-specific (iPhone 14 Pro+) but Live Activities still show on lock screen for all iOS 16.1+ devices
- Live Activities have an 8-hour maximum lifetime — cooking timers are typically much shorter
- The `endTime` approach is key: set the end time once, iOS counts down automatically. When adding time, just update `endTime`
- Interactive buttons require App Intents — this is the bridge between the Dynamic Island UI and app logic
- Test on both Dynamic Island devices (iPhone 14 Pro+) and non-Dynamic Island devices (Live Activity only shows on lock screen)

### References

- [Investigation: 09-ios-native-features.md — Live Activities section]
- [Epic: epic-ios-native.md]
