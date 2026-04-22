# Story timer-3 — TimerCompletionOverlay (Cupertino modal in cook mode)

**Status:** ready-for-dev
**Epic:** epic-notifications-timer-actions-live-activities
**Depends on:** timer-1 (action handler IDs), nfn-1 (per-category prefs)

## Scope

When a cook-mode timer expires while the app is foregrounded on the
cook-mode route, replace the existing one-line SnackBar with a
Cupertino-style bottom-sheet overlay that shows the four timer
actions (+ 2 min / + 5 min / Reset / Stop) as big tappable buttons in
a 2×2 grid. Gated by the user's per-category notification pref
(`prefs.categories.timers`): if the user has explicitly turned timer
notifications off we keep the SnackBar behavior. The OS notification
continues to fire in both cases — the overlay is an in-app addition
on top of the system-level alarm.

## Decisions / scope cuts

- **No global "rich foreground banner" framework.** The overlay is
  cook-mode-specific; other foreground pushes (partner activity, meal
  reminders, import events) keep the existing SnackBar in
  `push_notification_service.dart`. Out of scope.
- **Prefs read on cook-mode entry (fire-and-forget).** There is no
  shared-preferences cache of notification prefs today
  (`notification_preferences_screen.dart` fetches on-demand). We add a
  one-shot async fetch in `cook_mode_screen.initState` and store the
  `categories.timers` value in local state. Default is `true` until the
  fetch resolves; this matches the "acceptable lag" note in the epic
  refinements — a user who toggles timers off and starts a cook within
  ~500ms hits the default-true path once, then it respects their choice
  for the rest of the cook. Building a dedicated prefs cache service is
  out of scope and a good target for a future polish epic.
- **`recipeName` / step number shown on the overlay.** The overlay
  shows `{recipe.name} · Step {n+1}` as a subtitle when available.
  `_currentStep` is 0-indexed in state; UI displays 1-indexed.
- **Color palette matches cook-mode theme.** Primary buttons use
  `cook.cookAccent` (terracotta); destructive "Stop" uses a warning
  red. Surface uses `cook.cookSurface` with a slight lift. Consistent
  with Story 6.1 dark-chocolate/ivory palette.
- **Dismissing the sheet.** Tapping any action runs its callback +
  closes the sheet. Drag-down dismiss is allowed and is treated as a
  soft "ignore" — the underlying `_ActiveTimer` is removed from
  `_activeTimers` (same behavior as the SnackBar today — the timer has
  already fired). No dedicated "Dismiss" button is rendered; Stop
  covers the destructive path.
- **SnackBar fallback.** When `categories.timers == false` OR the sheet
  cannot be shown (edge: cook-mode scaffold transitioning), we fall
  back to the existing SnackBar so the user still gets *some* signal.
- **Foreground-only.** If the timer expires while the app is
  backgrounded, the OS notification + (on iOS) Live Activity "Done!"
  state handle it. The overlay is only relevant when cook-mode is the
  active route.

## File list

- `app/lib/features/recipes/cook_mode/widgets/timer_completion_overlay.dart`
  [NEW] — `showTimerCompletionOverlay({context, label, recipeName,
  stepNumber, onAdd2, onAdd5, onReset, onStop})` entry point + widget.
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` [MODIFY]
  — fetch prefs on `initState`, route `_onTimerComplete` through the
  overlay when `prefs.categories.timers` isn't explicitly false; wire
  `+ 2 min` / `+ 5 min` callbacks to a new
  `_extendActiveTimer(timer, minutes)` helper; `Reset` calls
  `_restartTimer`; `Stop` removes the timer (no reschedule).
- `app/test/features/recipes/cook_mode/timer_completion_overlay_test.dart`
  [NEW] — widget tests: overlay renders with all four buttons; label
  and subtitle display correctly; each button invokes its callback and
  dismisses the sheet.

## Acceptance criteria

- **AC1** — `showTimerCompletionOverlay(...)` renders a
  `showModalBottomSheet` with rounded top corners (radius 20), surface
  color from the cook-mode theme, ~40% screen height (target:
  `MediaQuery.size.height * 0.4`, clamped to [280, 420]), and four
  tappable buttons laid out in a 2×2 grid.
- **AC2** — Button layout: row 1 = `+ 2 min` (primary) / `+ 5 min`
  (primary). Row 2 = `Reset` (secondary) / `Stop` (destructive red).
  All four buttons are `FilledButton` with at least 56 logical-pixel
  minimum height (comfortable for a kitchen tap).
- **AC3** — Header shows emoji ⏱️, title `Time's up — {label}`, and
  subtitle `{recipeName} · Step {n+1}` when recipeName is non-null /
  non-empty; subtitle is omitted otherwise.
- **AC4** — Each button tap: invokes the callback provided by the
  caller, then closes the sheet via `Navigator.pop`.
- **AC5** — In `cook_mode_screen.dart`:
  - `initState` fires `_apiClient.getNotificationPreferences()`
    fire-and-forget; stores `categories.timers` into a local `bool?
    _timerCategoryEnabled` (null = not yet fetched, assume true).
  - `_onTimerComplete` branches: if
    `(_timerCategoryEnabled ?? true)` and cook-mode is still the
    active route (mounted), show the overlay. Otherwise fall back to
    the existing SnackBar.
- **AC6** — `+ 2 min` / `+ 5 min` buttons:
  - Schedule a new `_ActiveTimer` with `Duration(minutes: N)` + label
    `'{original label} (+Nm)'` via `_extendActiveTimer(timer,
    N)`. The helper removes the expired timer from `_activeTimers`,
    calls `_startTimer(new duration, new label)` to re-schedule OS
    notification + Live Activity in a single path, keeping parity
    with the existing `_addMinutes` flow but bound to the expired
    timer's label lineage.
- **AC7** — `Reset` button calls `_restartTimer(timer)` (existing
  behavior — cancels current, starts fresh at original duration).
- **AC8** — `Stop` button removes the timer (no reschedule). Visual
  effect = same as the existing SnackBar / header-strip no-op path.
- **AC9** — Widget tests cover:
  - Overlay renders the four expected button labels.
  - Subtitle appears when `recipeName` is non-empty; absent otherwise.
  - Tapping each button invokes its callback and dismisses the sheet
    (Navigator pop).
- **AC10** — The OS notification still fires at expiration (the
  system scheduled it). The overlay is in addition, not instead.
- **AC11** — When `_timerCategoryEnabled` is explicitly `false`, the
  overlay does NOT appear; the SnackBar fallback fires. Confirmed by
  a widget test.

## Manual verification

- [ ] Open cook mode for any recipe, start a 1-min timer.
- [ ] Wait 1 minute with the app in foreground. Overlay appears with
  `Time's up — {label}` title, subtitle shows the recipe + step, and
  four buttons in a 2×2 grid.
- [ ] Tap `+ 2 min`. Sheet dismisses; new chip appears in the header
  strip with a fresh 2:00 countdown. OS notification rescheduled.
- [ ] Repeat with `+ 5 min`. Same outcome at 5:00.
- [ ] Start a 1-min timer again. Let it fire. Tap `Reset`. Fresh 1-min
  timer scheduled.
- [ ] Start a 1-min timer. Let it fire. Tap `Stop`. Timer removed
  from header strip; no further notification fires.
- [ ] Drag the sheet down to dismiss without tapping any button. The
  expired timer is still removed from the header strip (same
  "already fired" semantics).
- [ ] In Settings → Notifications, toggle Timers OFF. Return to cook
  mode, start a 1-min timer. Wait. SnackBar (not the modal sheet)
  appears. OS notification still fires (alarm-class).

## Risks / notes

- **Prefs fetch timing.** On very fast expirations (start a 1-second
  timer, never possible in UI, but theoretically), the prefs fetch
  may not have resolved yet. Default-true means the overlay appears.
  Acceptable per epic.
- **Offline-mode cook.** If `getNotificationPreferences()` fails
  (offline / server error), `_timerCategoryEnabled` stays null → we
  default to true → overlay shows. Correct behavior (you'd rather
  have the overlay than swallow the timer).
- **Navigator context.** The overlay is shown from
  `_onTimerComplete` with `context` from the screen. If the user
  navigated mid-timer to a nested route (e.g. chat sheet), the
  overlay will be shown over the current route. Acceptable — the
  timer is expiring now, the user should see it.
