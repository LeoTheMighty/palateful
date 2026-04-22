# QA walkthrough — Story timer-2 (Wire LiveActivityService into cook mode)

**What shipped:** `LiveActivityService` is registered in DI, initialized
at app boot, and `cook_mode_screen.dart` now drives the Live Activity
lifecycle: start on timer-start, minute-cadence re-anchor of `endTime`,
complete on expiration, end on cancel/restart/exit. Android is a no-op.

## Setup

Install a TestFlight build on an iPhone with iOS 16.1+ (Dynamic Island
only on Pro models; lock-screen banner on all models). Ensure the app
has "Allow Live Activities" permission (Settings → Palateful). Open any
recipe with timer steps.

## Happy-path iPhone checks

- [ ] **Start a 30-min timer** from a step chip.
- [ ] **Lock the phone.** Lock-screen banner appears immediately with
  the timer label + recipe name + a native countdown + progress bar.
- [ ] **Long-press the notch / Dynamic Island (Pro only).** Expanded
  view shows timer label, recipe name, live countdown, and progress bar.
- [ ] **Compact Dynamic Island.** The notch edges show the timer icon
  (left) and live countdown (right) while any other app is foreground.
- [ ] **Wait ~1 minute.** Countdown stays accurate; no visual drift
  from the Dart-side `remaining` in the cook-mode chip.

## Multi-timer checks

- [ ] **Start two timers** (e.g. a 30-min bake and a 5-min cool).
  Dynamic Island shows whichever the OS prioritizes (usually the
  next-to-expire). Both lock-screen banners visible on the lock screen.
- [ ] **Cancel one timer** (tap its chip → Cancel). Its banner vanishes
  immediately. The other remains with its countdown intact.

## Completion checks

- [ ] **Let a 1-min timer expire in foreground.** SnackBar appears
  ("Timer done: {label}"). Lock-screen banner + Dynamic Island flip to
  "Done!" with a green checkmark.
- [ ] **Wait 5 minutes.** The "Done!" activity auto-dismisses (Swift
  side handles via `Future.delayed`). No lingering banner.

## Dispose / exit checks

- [ ] **Start a 10-min timer. Exit cook mode (back arrow).** Every
  lock-screen banner and Dynamic Island activity ends within 1–2
  seconds. No orphan banners.

## Restart / extend (sets up timer-3 context)

- [ ] **Tap a timer chip → Restart.** The banner flips: old activity
  ends, new activity starts with the full original duration.

## Android checks (no-op)

- [ ] Install same build on an Android device. Start a 1-min timer.
  Lock-screen and notification shade show the existing four-action
  notification (shipped in timer-1). No Live Activity attempts, no
  crashes in logcat from `LiveActivityService`.

## E2E / cold-launch checks

- [ ] **Cold launch the app.** Watch logcat / console for
  `LiveActivityService initialized` on iOS;
  `Failed to initialize LiveActivityService` should NOT appear unless
  the device has Live Activities disabled globally.

## Gotchas to watch for

- **"Done!" state persists too long.** The auto-dismiss is a 5-min
  `Future.delayed` in `LiveActivityService`; if the app is killed
  during that window, the activity stays on the lock screen until the
  Swift side times out (usually 8 hours). This is Apple's fallback
  behavior, not a bug we introduced.
- **App killed mid-timer.** Dart-side `_activeTimers` is lost; Live
  Activity freezes at its last `endTime`. The Swift `.timer` style
  continues counting, so the countdown still looks live until the OS
  evicts the activity. OS notification still fires. Documented as a
  known limitation; persistence is a future epic.
- **Simulator vs device.** Live Activities do NOT render in the iOS
  Simulator prior to Xcode 15. Verify on a real device or Xcode 15+
  simulator with the Live Activities checkbox flipped in the scheme.
