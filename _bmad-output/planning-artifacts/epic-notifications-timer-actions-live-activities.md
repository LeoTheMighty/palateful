<!-- refined via party-mode 2026-04-21 -->
# Epic: Cooking Timer Quick Actions + Live Activities

## Overview

Phase 2 audit found that cooking timers are surprisingly mature on iOS and surprisingly bare on Android, with one very rich UI surface (`CookingTimerLiveActivity.swift`) sitting completely dead because Flutter never calls it.

What's already wired in `app/lib/core/services/cook_timer_notification_service.dart`:
- `flutter_local_notifications.zonedSchedule` schedules an OS-level notification when each timer is created — fires regardless of app state.
- iOS `DarwinNotificationCategory` registers four actions on the cook-timer category: `TIMER_ADD_2_MIN`, `TIMER_ADD_5_MIN`, `TIMER_RESET`, `TIMER_DISMISS`. Foreground + background handlers route the action IDs and reschedule appropriately.
- `_activeTimers` list in `cook_mode_screen.dart` holds in-memory timer state with `startTime` so background-resume reconciliation recomputes `remaining` correctly.

What's missing (per the user's explicit ask):
- **Android has zero notification actions.** Android users tap the notification → app opens; they cannot tap "+ 2 min" / "Reset" / "Stop" from the lock screen.
- **The in-app foreground experience is just a SnackBar.** When app is in cook-mode and a timer expires, today the SnackBar appears (small, dismissable, no quick-actions). The user explicitly wants the Apple-style timer-completion overlay with the same four actions.
- **Live Activities (Dynamic Island + lock screen countdown) is dead code.** `CookingTimerLiveActivity.swift` renders compact / expanded / minimal Dynamic Island regions and a lock-screen banner with countdown — but `LiveActivityService` in Flutter has the start/update/end methods and they're never called from the timer lifecycle.
- Timer state is purely in-memory. App force-killed mid-timer → state lost. The OS notification still fires (it's scheduled by the OS) but no in-app representation can be reconstructed. Probably out of scope for this epic; flag as optional follow-up.

**Goal:** parity-of-actions across iOS and Android lock-screen, an in-app overlay matching the OS look-and-feel for cook-mode timer expiration, and a live Dynamic Island / lock-screen countdown for active iOS timers.

## Locked Decisions (inherited + added)

**Inherited (do not re-litigate):**
- iOS-first; Android continues on `firebase_messaging` defaults — but this epic explicitly extends Android support for *local* notification actions (different surface from FCM pushes).
- ErrorReporter for failures; no user toasts on action-handler errors.
- Per-category prefs (Epic A) — timer alerts sit under `prefs.categories.timers`. The OS notification still fires (scheduled locally) regardless, but the in-app overlay respects the toggle. (Rationale: a user who turns off timer notifications still wants the OS alarm; they're saying "don't make a banner appear in the app".) Reconsider in party-mode if this split is wrong.

**Locked for this epic (from 2026-04-21 user batch + sensible defaults):**
- **Android notification actions parity with iOS.** Wire `AndroidNotificationAction` for TIMER_ADD_2_MIN, TIMER_ADD_5_MIN, TIMER_RESET, TIMER_DISMISS (or call it TIMER_STOP for clarity — see open question). Same action IDs across platforms so the existing background handler routes correctly.
- **In-app foreground overlay is cooking-mode-specific.** When the timer fires AND `cook_mode_screen` is the current route, render a Cupertino-style modal overlay with the recipe / step name and four big buttons (+2 min, +5 min, Reset, Stop). Other notifications keep the existing `SnackBar` from `_onForegroundMessage`. No generic "rich foreground banner" framework — too much scope.
- **Live Activities wired into the timer lifecycle.** When user starts a timer in cook mode: `LiveActivityService.startTimerActivity(...)` immediately. Updates every minute (countdown precision is OK at the minute mark for Dynamic Island; second-by-second would be visually noisy and battery-costly). On expiration: `completeTimerActivity` shows the "Done!" state with a 5-minute auto-dismiss.
- **Multiple timers in Live Activity:** show the *next-to-fire* timer in Dynamic Island (one Live Activity at a time per app per Apple's limits). The full list stays in cook mode. Document this in the epic.
- **Stop = cancel the scheduled notification + remove from `_activeTimers`.** No "soft stop" or "pause" semantics in this epic; user can re-create a timer if they want.
- **"Long press"** on iOS is actually swipe-down or long-press from the lock screen / notification center, depending on iOS version. The user's wording is loose — we're delivering "actions accessible from the notification surface". On Android, actions appear inline in the notification (not behind a long-press gesture).
- **Timer state persistence is OUT OF SCOPE** for this epic. App force-kill → cook-mode timers are lost in-app, but the OS notifications still fire (already the case). Document as a follow-up epic.

## Refinements via party-mode 2026-04-21

**Lens-by-lens cross-examination findings — incorporated into ACs below:**

- **PM:** The user said "long press" but iOS notification actions are accessed via swipe-down / pull-down, NOT long-press. Android shows action buttons inline below the notification body. Both are within the spirit of "actions at the notification surface" — wording should clarify in shipped copy / docs that "actions are accessed via your platform's notification gesture (swipe on iOS, inline buttons on Android)".
- **UX:** The Cupertino-style modal overlay must match cook-mode's dark chocolate/ivory theme (per Story 6.1's design system). Don't use system Cupertino blue; use the cook-mode primary color for action buttons. Folded into timer-3 AC 6.
- **UX:** Action button labels are short ("+ 2 min", "+ 5 min", "Reset", "Stop") to fit notification banner constraints across screen sizes. Confirmed under 8 chars each.
- **Frontend:** Live Activity update cadence — minute precision strikes the right battery/freshness balance. Don't tighten to second-cadence. Multiple concurrent timers exist in `_activeTimers`; Dynamic Island shows next-to-expire (Apple's prioritization).
- **Backend:** None for code, but the per-category prefs read happens client-side from the cached `notification_preferences`. If user toggles "Timers" off and immediately starts a cook, the cache may be stale until next app foreground. Acceptable lag — toggle-then-immediately-trigger is a rare path. Folded into timer-3 risks.
- **Infra/Devops:** Android killed-app action delivery (Phase 2 flagged this as unverified). Add an explicit manual verification AC for "schedule a 1-min timer, force-quit the app, wait, tap action button on notification → action handler fires → new timer scheduled". Folded into timer-1.
- **QA:** Manual verification per platform: iPhone for Live Activities + iOS actions, Android emulator + Pixel for Android actions including killed-app path. Document in epic DoD.

**Cross-epic locked decisions added by this workshop (propagate to D/E):**

1. **"Long press" / "long tap" UX wording in user-facing copy refers to platform-appropriate gesture (swipe on iOS, inline on Android).** Don't promise a literal long-press in any notification copy.
2. **Action IDs are platform-agnostic strings** (TIMER_ADD_2_MIN, TIMER_RESET, TIMER_STOP, etc.). Same string, same handler routing across platforms. New action-bearing notifications in future epics follow this convention.
3. **Cook-mode-specific overlays don't generalize to a foreground-banner system this round.** SnackBar stays the default for non-timer foreground pushes.

## End-user flow

### Flow A — Leo starts a timer in cook mode (iOS)

1. Leo is in cook mode for "Sweet Potato Quiche", taps step 3's "30 min" timer chip → `_startTimer(label: "Bake — step 3", duration: 30 min)`.
2. Cook timer service:
   - Schedules an OS notification 30 min from now via `flutter_local_notifications.zonedSchedule` (existing behavior).
   - **NEW:** Calls `LiveActivityService.startTimerActivity(notifId, label, durationSeconds, ...)` → Swift side starts an `Activity<TimerAttributes>`.
3. iPhone immediately shows:
   - The countdown in Dynamic Island compact view (e.g., "🍳 29:59").
   - On lock screen, a Live Activity banner with the timer label + countdown bar.
4. Periodic update from Flutter: every minute, `LiveActivityService.updateTimerActivity(notifId, remainingSeconds)`. Dynamic Island re-renders.
5. At 0:00:
   - OS notification fires (existing).
   - `LiveActivityService.completeTimerActivity(notifId)` updates the activity to "Done!" state; auto-dismisses after 5 min.

### Flow B — Timer expires while Leo is on the lock screen (iOS)

1. Lock screen shows the Live Activity in the "Done!" state. Pull-down on the notification or swipe right shows actions: +2 min, +5 min, Reset, Stop.
2. Leo taps "+2 min".
3. Background notification handler `_handleBackgroundAction` (existing) catches `TIMER_ADD_2_MIN`, schedules a new OS notification for +2 min, and starts a new Live Activity for the new timer.
4. After 2 min, OS notification fires again → user can repeat.

### Flow C — Timer expires while Leo is in cook mode (foreground)

1. Cook mode is open. Foreground notification fires.
2. **NEW:** Instead of the SnackBar, a Cupertino-style modal sheet slides up from the bottom (full width, ~40% screen height) with:
   - Title "Time's up — {timer.label}".
   - Subtitle "{recipe.name} · step {n}" if context available.
   - Four big buttons in a 2×2 grid: +2 min, +5 min, Reset, Stop.
3. Leo taps "+5 min". Sheet dismisses; new timer chip appears in the cook-mode header strip with 5:00 remaining; OS notification rescheduled.
4. Other notifications (e.g., a partner-activity push that arrives while cook mode is open) still use the existing SnackBar — only timer expiration gets the overlay.

### Flow D — Same flow on Android

1. Leo on a Pixel; same cook-mode flow. OS notification fires.
2. Notification banner shows the title + body PLUS four action buttons inline (+2, +5, Reset, Stop) — NEW. He taps "+2 min" without opening the app.
3. The action ID `TIMER_ADD_2_MIN` is routed by the existing background handler (unchanged) — schedules a new OS notification for +2 min.
4. Foreground overlay (same as iOS) appears if the app is in cook-mode at the time.

### Flow E — Live Activity for multiple concurrent timers

1. Leo has three timers running: "Bake — 30 min", "Simmer — 10 min", "Cool — 5 min".
2. Live Activity shows the *next-to-expire* (Cool — 5 min) in Dynamic Island.
3. When Cool finishes, Live Activity transitions to Simmer.
4. The cook-mode header strip in-app shows all three timers as chips (existing UX, unchanged).

## Frontend changes

- **`app/lib/core/services/cook_timer_notification_service.dart`** (MODIFIED)
  - In `_scheduleNotification` / `scheduleTimerNotification`, when constructing `AndroidNotificationDetails`, add `actions: [...]` with four `AndroidNotificationAction` entries: id `TIMER_ADD_2_MIN` / `TIMER_ADD_5_MIN` / `TIMER_RESET` / `TIMER_DISMISS` (or `TIMER_STOP`), each with a label matching the iOS category.
  - Confirm `AndroidNotificationAction` constructor params: `id`, `title`, `showsUserInterface=false`, `cancelNotification=true` (we cancel the original on tap of any action).
  - Background handler `_backgroundNotificationHandler`'s switch-case routes Android action IDs the same way as iOS — confirm the existing handler treats actions identically across platforms (it should; the action IDs are platform-agnostic strings).

- **`app/lib/core/services/live_activity_service.dart`** (MODIFIED — already exists with method stubs)
  - Confirm `startTimerActivity(notifId, label, durationSeconds, recipeName)`, `updateTimerActivity(notifId, remainingSeconds)`, and `completeTimerActivity(notifId)` work as advertised.
  - Add a periodic-update helper: a `Timer.periodic(Duration(minutes: 1), ...)` that loops over active timers and calls `updateTimerActivity` for each. Single timer per cook-mode session is the common case; with multiple, we track one Live Activity per timer (Apple supports multiple but Dynamic Island shows one at a time — the OS picks based on priority).

- **`app/lib/features/recipes/cook_mode/cook_mode_screen.dart`** (MODIFIED)
  - In `_startTimer`: after scheduling the notification, call `LiveActivityService.startTimerActivity(notifId, label, durationSeconds, recipeName)`.
  - In `_onTimerComplete` / when the in-foreground Dart timer hits 0:
    - Call `LiveActivityService.completeTimerActivity(notifId)`.
    - Render the new `TimerCompletionOverlay` (Cupertino modal sheet).
  - In `_cancelTimer` / Stop action: call `LiveActivityService.endTimerActivity(notifId)` (or equivalent).
  - Add a `Timer.periodic(Duration(minutes: 1))` while any timer is active that pings `LiveActivityService.updateTimerActivity` for each. Cancel when no timers active.

- **`app/lib/features/recipes/cook_mode/widgets/timer_completion_overlay.dart`** (NEW)
  - Cupertino-style modal sheet (`showModalBottomSheet` with rounded top corners, blurred backdrop, ~40% screen height).
  - Layout: large emoji or icon at top, "Time's up — {label}" title, "{recipe.name} · Step {n}" subtitle, then a 2×2 grid of buttons:
    - "+ 2 min" (primary blue)
    - "+ 5 min" (primary blue)
    - "Reset" (secondary)
    - "Stop" (destructive red)
  - Button taps: dismiss sheet AND invoke the corresponding action (reschedule OR cancel + remove from `_activeTimers`).
  - Subject to `prefs.categories.timers` — if the user toggled off, the overlay does NOT appear (OS notification still fires; that's a system-level alarm).
  - Integration test: simulate timer completion in cook mode, confirm overlay appears, tap "+5 min", confirm new notification scheduled.

- **`app/lib/core/services/push_notification_service.dart`** (NO CHANGES) — the in-app overlay is a cook-mode-specific surface, not a generic notification handler. Other notifications still use `_onForegroundMessage`'s SnackBar.

## Backend changes

- **None.** Timers are 100% local — no backend state, no API, no push notifications from the server. The only backend touchpoint is the Epic A `_category_for_type` mapping, but timer notifications are *local*, not server-sent, so they don't go through `send_to_user` at all. That means the per-category prefs check happens client-side (in the cook timer service: read the user's local cached `prefs.categories.timers` value before showing the in-app overlay).

## Infrastructure changes

- **None.** No backend, no infra. iOS Live Activities + Android notification actions are all client-side capabilities already provisioned (Live Activities entitlement is already declared per the proof-of-life epic; the `live_activities` Flutter plugin is in pubspec).

## Initial Design Principles (pre-party-mode)

1. **Parity across iOS and Android for the lock-screen surface.** Same action IDs, same labels, same handler routing.
2. **Cook-mode-specific in-app overlay.** Don't generalize to a global rich notification UI — too much scope, no need.
3. **Live Activities are passive.** Flutter starts/updates/ends; iOS handles rendering. No bidirectional state sync.
4. **One Live Activity at a time visually.** Multiple timers exist in app state; Dynamic Island picks the next-to-expire.
5. **OS notification is the source of truth for expiration.** Even if the app is killed, the alarm fires. The in-app overlay and Live Activity are presentation layers on top.
6. **Inherit from prior epics.** Per-category prefs (Epic A) gate the in-app overlay; OS alarm always fires.
7. **No persistence in this epic.** Timer state is in-memory; killed app loses in-app representation. Document; defer.

## File structure (expected)

```
app/lib/core/services/
├── cook_timer_notification_service.dart                    # MODIFIED — Android actions wiring
└── live_activity_service.dart                              # MODIFIED — confirm + add periodic updater

app/lib/features/recipes/cook_mode/
├── cook_mode_screen.dart                                   # MODIFIED — Live Activity lifecycle, overlay render
└── widgets/
    └── timer_completion_overlay.dart                       # NEW — Cupertino modal sheet
```

No backend or infra files.

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| timer-1 | Android notification actions parity | 🔴 P0 | 0.25–0.5 d | None |
| timer-2 | Wire LiveActivityService into cook_mode_screen lifecycle | 🔴 P0 | 0.5–1 d | None |
| timer-3 | TimerCompletionOverlay (Cupertino modal) + cook-mode integration | 🔴 P0 | 0.5–1 d | timer-1 (action IDs), Epic A nfn-1 (prefs read) |

**Total estimated effort: 1.5–2.5 days**

---

## Story timer-1: Android notification actions parity

As Leo on a Pixel,
I want to tap "+ 2 min", "+ 5 min", "Reset", and "Stop" directly from the notification banner without opening the app,
so that Android matches iOS's already-shipped quick actions.

### Acceptance Criteria

1. `cook_timer_notification_service.dart`'s `_scheduleNotification` (or `scheduleTimerNotification`) constructs `AndroidNotificationDetails` with `actions: <List<AndroidNotificationAction>>`:
   - `AndroidNotificationAction(id: 'TIMER_ADD_2_MIN', title: '+ 2 min')`
   - `AndroidNotificationAction(id: 'TIMER_ADD_5_MIN', title: '+ 5 min')`
   - `AndroidNotificationAction(id: 'TIMER_RESET', title: 'Reset')`
   - `AndroidNotificationAction(id: 'TIMER_DISMISS', title: 'Stop')` (alias `TIMER_STOP` if we rename — see open question)
2. Each action has `cancelNotification: true` (the original notification dismisses on action tap; the action handler may schedule a new one for +X min).
3. The existing `_backgroundNotificationHandler` handles all four IDs identically across platforms (confirm during dev — the handler is already platform-agnostic per Phase 2 research).
4. Manual verification on Android emulator + Pixel device:
   - [ ] Schedule a 1-minute timer in cook mode, background the app.
   - [ ] After 1 min, notification banner shows with four action buttons inline.
   - [ ] Tap "+ 2 min" → original dismisses, new notification fires 2 min later.
   - [ ] Tap "Reset" on a fresh timer → original dismisses, new notification scheduled at original duration.
   - [ ] Tap "Stop" → notification dismisses, no new schedule.
   - [ ] **Killed-app path (Phase 2 flagged this as unverified):** schedule a 1-min timer, force-quit the app via OS task switcher, wait for the notification to fire, tap "+ 2 min" on the notification → action handler fires → new notification scheduled 2 min later. If this fails on Android, note the constraint in the epic and document the limitation (the alternative is "user must open app to extend"; iOS already handles killed-app actions correctly via the existing background handler).
5. iOS: no change. Confirm regression doesn't break the existing iOS actions (Phase 2 audit confirmed they work).
6. Flutter unit test: mock `flutter_local_notifications`, schedule a timer, assert the `AndroidNotificationDetails.actions` list is set with all four entries.

### Key Files
- Modify: `app/lib/core/services/cook_timer_notification_service.dart`
- Test: `app/test/services/cook_timer_notification_service_test.dart`

### Risks / notes
- `AndroidNotificationAction` may require additional native plugin setup for the action handler to fire when the app is killed. Confirm during dev — Phase 2 audit didn't deep-test the killed-app path on Android.
- Action labels must be short enough to fit in the notification banner across screen sizes. "+ 2 min" / "+ 5 min" / "Reset" / "Stop" are all under 8 chars.

---

## Story timer-2: Wire LiveActivityService into cook_mode_screen lifecycle

As Leo,
I want my active cooking timer to appear in the Dynamic Island and on my lock screen with a live countdown,
so that I can see the timer at a glance without unlocking my phone, and the dead Swift UI in PalatefulWidgets actually does something.

### Acceptance Criteria

1. `cook_mode_screen.dart`'s `_startTimer` calls `LiveActivityService.startTimerActivity(notifId, label, durationSeconds, recipeName, stepNumber)` immediately after scheduling the OS notification.
2. A `Timer.periodic(Duration(minutes: 1))` runs while ANY timer is active — on each tick, iterates `_activeTimers` and calls `LiveActivityService.updateTimerActivity(notifId, remainingSeconds)` for each. Cancels when `_activeTimers.isEmpty`.
3. On timer completion (either Dart timer hits 0 OR foreground-resume reconciliation finds remaining ≤ 0):
   - `LiveActivityService.completeTimerActivity(notifId)` is called (5-min auto-dismiss runs in the Swift side).
4. On timer cancel (via `_cancelTimer` or the new "Stop" action):
   - `LiveActivityService.endTimerActivity(notifId)` (immediate dismiss, no "Done!" state).
5. `LiveActivityService` exposes the helper methods (most are stubs already per Phase 2 — confirm + flesh out):
   - `startTimerActivity(notifId, label, durationSeconds, recipeName, stepNumber) → Future<void>`
   - `updateTimerActivity(notifId, remainingSeconds) → Future<void>`
   - `completeTimerActivity(notifId) → Future<void>`
   - `endTimerActivity(notifId) → Future<void>`
6. Multiple timers: Dynamic Island shows the *next-to-expire* (the OS picks per its prioritization; Apple supports multiple Live Activities but UI shows one). All timers' Live Activities exist in parallel.
7. iOS-only: this story is a no-op on Android. Guard with `Platform.isIOS`.
8. Manual verification (TestFlight build on Leo's iPhone):
   - [ ] Open cook mode for any recipe with timer steps.
   - [ ] Start a 30-min timer.
   - [ ] Lock the phone → Live Activity banner visible on lock screen with countdown.
   - [ ] Long-press notch → Dynamic Island expanded view shows timer label + countdown.
   - [ ] After 1 min, countdown updates correctly (within ~1 min precision).
   - [ ] Start a 2nd timer → Dynamic Island switches to next-to-expire.
   - [ ] Cancel one timer in cook mode → its Live Activity ends.
   - [ ] Wait for a timer to expire → Live Activity shows "Done!" with auto-dismiss.

### Key Files
- Modify: `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- Modify: `app/lib/core/services/live_activity_service.dart` (confirm methods, add periodic helper)
- Test: `app/test/features/recipes/cook_mode/cook_mode_screen_test.dart` (mock LiveActivityService)

### Risks / notes
- `live_activities` plugin v2.0.0 (per pubspec) — confirm it supports multiple concurrent activities. Apple's limit per app is one ACTIVE display in the Dynamic Island compact, but multiple can exist; the OS picks.
- Battery cost: minute-cadence updates are fine. Don't tighten to second-cadence.
- The Swift side (`CookingTimerLiveActivity.swift`) renders the countdown; Flutter just sends `remainingSeconds`. If the Swift side has a self-decrementing timer based on a `staleDate`, a single-shot `start` may suffice and updates only on completion. Confirm during dev which model the Swift implementation uses.

---

## Story timer-3: TimerCompletionOverlay — Cupertino modal in cook mode

As Leo,
I want a big Apple-style modal to appear in cook mode when a timer expires, with the same +2/+5/Reset/Stop actions,
so that I don't have to look at the OS banner from across the kitchen — the action is right there in the app I'm already in.

### Acceptance Criteria

1. New widget `timer_completion_overlay.dart`:
   - `showTimerCompletionOverlay({required BuildContext context, required _ActiveTimer timer, required void Function() onAdd2, required void Function() onAdd5, required void Function() onReset, required void Function() onStop})` — uses `showModalBottomSheet` with rounded top corners, ~40% screen height.
   - Layout: emoji ⏱️, "Time's up — {timer.label}" headline, "{recipe.name} · Step {n}" subtitle (when available), 2×2 button grid.
   - Buttons: "+ 2 min" / "+ 5 min" (primary), "Reset" (secondary), "Stop" (destructive). Each tap calls the corresponding callback then dismisses the sheet.
2. `cook_mode_screen.dart`'s `_onTimerComplete` (when foreground):
   - If `prefs.categories.timers != false` (read from cached prefs), call `showTimerCompletionOverlay(...)`.
   - Callbacks wire to existing `_addMinutes`, `_restartTimer`, `_cancelTimer` methods.
3. If the app is foregrounded mid-completion (not in cook mode), the overlay does NOT appear — the existing SnackBar/system notification handles it. Only when `cook_mode_screen` is the active route does the overlay show.
4. The OS notification still fires at the moment of expiration (the system schedules it). The overlay is in addition, not instead. The user gets both, like Apple's Clock app.
5. Per-category opt-out: if `prefs.categories.timers == false`, the overlay does NOT appear. The OS notification (alarm-class) still fires — explicitly NOT gated by the category, since alarms are an expected system-level signal when the user starts a timer.
6. Visual polish: matches the cook-mode dark theme (chocolate background, ivory text per Story 6.1) but overlay can use a slightly lighter surface so it stands out.
7. Flutter widget test: simulate timer completion → assert sheet appears, tap "+5 min" → assert callback fired.
8. Manual verification:
   - [ ] Open cook mode, start a 1-min timer.
   - [ ] Wait 1 min foreground → overlay appears with the four buttons.
   - [ ] Tap "+ 2 min" → sheet dismisses, new chip appears with 2:00 remaining, OS notification rescheduled for 2 min.
   - [ ] Repeat with "Reset" → restarts at original duration.
   - [ ] Repeat with "Stop" → timer removed from header strip, no further notifications.

### Key Files
- Create: `app/lib/features/recipes/cook_mode/widgets/timer_completion_overlay.dart`
- Modify: `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- Test: `app/test/features/recipes/cook_mode/timer_completion_overlay_test.dart`

### Risks / notes
- The overlay is cook-mode-specific. Resist extending to a generic foreground-notification banner system. Out of scope.
- Screen-wake: cook mode already has wake-lock per Story 6.1; the overlay rendering doesn't need additional wake handling.

## Dependencies

- timer-1 is independent.
- timer-2 is independent of timer-1; can ship in parallel.
- timer-3 depends on Epic A's nfn-1 for the per-category prefs read; depends conceptually on timer-1's action IDs being defined (so the callbacks have something to invoke).

## Open questions for the user

- **`TIMER_DISMISS` vs `TIMER_STOP` naming.** iOS today uses `TIMER_DISMISS` (per Phase 2 audit). The user's wording was "stop". Should we rename to `TIMER_STOP` for clarity (and update both platforms), or keep `TIMER_DISMISS` to avoid touching working iOS code? Default: rename to `TIMER_STOP` for consistency with the user's mental model and the button label "Stop". Migration is a string-replace.
- **Live Activity update cadence.** Once-per-minute is the default. Should the Dynamic Island show seconds-precision (which would require a second-cadence updater + battery cost)? Default: minute precision; user can re-evaluate if it feels stale.

## Definition of Done (Epic Level)

- An Android user with a backgrounded app gets a notification banner with four action buttons (+2/+5/Reset/Stop) when a timer expires; tapping each routes through the existing handler.
- An iOS user starting a cook-mode timer sees a Live Activity in Dynamic Island + lock screen with live countdown.
- An iOS user with cook mode in the foreground sees a Cupertino-style modal sheet on timer expiration with the four action buttons.
- The overlay respects `prefs.categories.timers` (does not appear when off); the OS notification always fires.
- No regression in existing iOS notification actions (per Phase 2 they work today).
- Manual smoke test: Leo runs a 1-min timer in cook mode, sees the modal; backgrounds, sees Dynamic Island; locks, sees lock-screen banner; expires, sees notification with action buttons that work.
