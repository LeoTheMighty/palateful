# QA walkthrough — Story timer-3 (TimerCompletionOverlay Cupertino modal)

**What shipped:** a Cupertino-style bottom-sheet overlay that replaces
the one-line "Timer done" SnackBar when a cook-mode timer expires with
the app in the foreground on the cook-mode route. Four big buttons in a
2×2 grid: `+ 2 min`, `+ 5 min`, `Reset`, `Stop`. Gated by the
`prefs.categories.timers` per-category notification pref — if the user
turned timer notifications off, the SnackBar fallback runs instead
(OS alarm continues to fire in both branches).

## Setup

Any recent build on iOS or Android. Open a recipe with timer steps,
enter **Cook mode**.

## Happy-path (foreground, cook-mode active)

- [ ] Start a 1-min timer from a step chip (or via the manual timer
  sheet).
- [ ] Wait 1 min in the foreground (don't lock, don't switch apps).
- [ ] The overlay appears with:
  - Title: `Time's up — {timer label}`
  - Subtitle: `{recipe name} · Step {n+1}` (1-indexed step)
  - Four buttons in a 2×2 grid: + 2 min / + 5 min / Reset / Stop
- [ ] Tap `+ 2 min`. Sheet dismisses. A fresh chip appears in the
  header strip labelled `{original} (+2m)` counting down from 2:00.
  OS notification rescheduled 2 min out.
- [ ] Reset flow: start a 1-min timer, let it fire, tap `Reset` on
  the overlay. New 1-min timer with the original label starts.
- [ ] Stop flow: start a 1-min timer, let it fire, tap `Stop`. Overlay
  dismisses, no chip appears, no new OS notification.
- [ ] Drag the sheet down without tapping a button. Overlay dismisses;
  the expired timer is already removed from the header strip (same
  "already fired" semantics as the legacy SnackBar).

## Per-category gating

- [ ] Go to Settings → Notifications. Toggle **Timers** OFF.
- [ ] Return to cook mode. Start a 1-min timer. Wait.
- [ ] The **SnackBar** (not the modal sheet) appears with the legacy
  "Timer done: {label}" copy.
- [ ] The OS notification still fires (alarm-class — expected).
- [ ] Turn Timers back ON. Start another timer. After 1 min, the
  overlay returns.

## Multi-timer coexistence

- [ ] Start three timers at 30s intervals. As each expires, a fresh
  overlay appears. Each must be dismissed (via action or drag-down)
  before the next shows — stacking behavior is whatever
  `showModalBottomSheet` does (typically: second one waits until the
  first dismisses). Confirm this is the observed behavior; if multiple
  sheets stack, note the UX surprise.

## Visual polish

- [ ] Dark theme: surface uses `cookSurface` (chocolate), buttons use
  `cookAccent` (terracotta) for `+2/+5`, a dimmer surface for `Reset`,
  and a warning red `#B33A3A` for `Stop`.
- [ ] Buttons are ≥ 56 dp tall and comfortable to tap mid-stir.
- [ ] On iPhone SE (narrowest common screen) the 2×2 grid does not
  clip; button labels read cleanly on one line.
- [ ] On a tablet in landscape, the sheet is anchored to the bottom of
  the screen and doesn't consume absurd height (clamped to 420 dp).

## Gotchas to watch for

- **Prefs read latency.** The prefs fetch is fire-and-forget in
  `initState`. If the network takes > 1 s and the user starts a very
  fast timer, the overlay defaults to showing (null = assume true).
  This is epic-sanctioned "acceptable lag" and matches what most users
  would expect.
- **Offline entry.** If `getNotificationPreferences()` fails (offline
  or server error), `_timerCategoryEnabled` stays null → overlay
  always shows. Safer default.
- **Navigation context.** The overlay uses the cook-mode screen
  context. If the user opened a nested route (AI chat sheet, manual
  timer sheet) at the moment of expiration, the overlay renders on
  top of that route. Intended — don't want to swallow the alert.
- **Android:** the overlay is cross-platform; it renders identically
  on Android. No extra work needed beyond what timer-1 already wired.
- **The `Stop` button has no-op callback.** That's by design — the
  expired timer is already removed from `_activeTimers` before the
  overlay opens, so there's nothing to cancel. The button exists
  purely to close the sheet as a "done with this alert" gesture.
