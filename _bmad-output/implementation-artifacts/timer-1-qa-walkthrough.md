# QA walkthrough — Story timer-1 (Android notification actions parity)

**What shipped:** four inline action buttons on every Android cook-timer
notification (`+ 2 min`, `+ 5 min`, `Reset`, `Stop`) using the same
platform-agnostic action IDs as iOS. No iOS behavior change.

## Setup

Install a fresh build on an Android device (Pixel preferred) or emulator
(API 34+ recommended). Ensure notification permission is granted. Open
any recipe, enter **Cook mode**.

## Functional checks

- [ ] **Baseline schedule & fire.** From a step with a chip, tap a short
  duration (or use the manual timer sheet for 1 min). Background the
  app. Wait for the notification.
- [ ] **Four action buttons inline.** Notification banner shows four
  buttons inline (not behind a long-press / swipe): "+ 2 min",
  "+ 5 min", "Reset", "Stop".
- [ ] **`+ 2 min`.** Tap "+ 2 min". Original notification dismisses.
  New notification fires 2 min later. Label reads
  `"{original label} (+2m)"`. Same four actions on the new one.
- [ ] **`+ 5 min`.** Schedule a fresh timer. Tap "+ 5 min". New
  notification fires 5 min later.
- [ ] **`Reset`.** Schedule a 1-min timer, let it fire. Tap "Reset" on
  the notification. A new notification scheduled at the original 1-min
  duration. Label reads `"{original label} (reset)"`.
- [ ] **`Stop`.** Schedule a timer, let it fire. Tap "Stop". Notification
  dismisses. No new notification scheduled; opening the app shows the
  timer has been removed from the cook-mode header strip (pre-existing
  in-app cleanup).

## Killed-app path (the Phase 2 unknown)

- [ ] Schedule a 1-min timer in cook mode.
- [ ] Swipe the app away in the task switcher (kill the process).
- [ ] Wait for the notification to fire (~1 min).
- [ ] Tap "+ 2 min" on the notification.
- [ ] A new notification fires 2 min later, labeled `"... (+2m)"`.
  - **If this fails:** note the Android OEM + Android version. The
    limitation is a platform constraint (battery optimizer killing the
    background isolate), not a shipped-code bug. The alternative path
    (tap notification body → app opens → extend manually) continues to
    work. Document in the epic follow-ups as "Android killed-app action
    delivery requires the app to be in a non-fully-killed state on OEM
    X/Y" if we see consistent failure.

## iOS regression

- [ ] Install the same build on an iPhone. Schedule a 1-min cook-mode
  timer. Lock the phone. When the notification fires, pull it down (or
  long-press) to reveal the four iOS actions: `Add 2 Minutes`,
  `Add 5 Minutes`, `Reset Timer`, `Dismiss`. Tap `Add 2 Minutes`. New
  notification fires 2 min later. No regression from prior behavior.

## Visual

- [ ] The action button labels on Android do not truncate on the
  narrowest phone screen you test (320 dp). "+ 2 min", "+ 5 min",
  "Reset", "Stop" should all render fully.

## Gotchas to watch for

- "**Label reflows on small screens.**" Some Android launchers clip
  action labels to ~8 chars; all four of our labels are ≤ 8 chars, so
  we're safe. If you see truncation on an unusual device, note the
  device + locale in the report.
- "**`cancelNotification: true` leaves no trail.**" Tapping any action
  removes the original notification from the shade. The replacement
  (for `+2` / `+5` / Reset) is scheduled via `zonedSchedule` and appears
  only when the new delay elapses — there is NO "already rescheduled"
  visible affordance. This is expected and mirrors iOS behavior.
