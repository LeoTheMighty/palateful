# cmp-5 — QA walkthrough

## Automated assertions (run locally)

- [x] `flutter test test/theme/` — all 12 pass
- [x] `flutter test test/cook_mode_gesture_test.dart` — 11 pass
  (tap-zone + touch-target + cmp-4 back-nav + cmp-5 surface colour)
- [x] `flutter test test/cook_mode_timer_test.dart` — 22 pass
- [x] `flutter test test/offline_cook_mode_test.dart` — pass
- [x] `flutter test test/post_cook_feedback_test.dart` — 5 pass

## Manual QA (Leo's phone)

- [ ] **Light home → cook mode**: open a recipe while app is in light
  theme, tap Cook. Scaffold is calm warm-neutral (cream), not
  orange-flooded. Next button + progress bar + current pill are
  deep-terracotta `cookAccent`.
- [ ] **Advance → back**: swipe forward steps 1 → 4, then swipe back
  to step 2. Step 2 renders as the in-progress current card (no line-
  through, no dim, no check icon). Step 2 pill in the strip shows
  "current" (no green check). Pills at 0, 1, 3 still show green
  checks.
- [ ] **Pill-tap back**: repeat step 4 above but use a direct pill
  tap on index 0 — step 0 uncompletes, pills 1/2/3 stay green.
- [ ] **Left-zone tap back**: repeat with left-25% tap — same result.
- [ ] **AI chat sheet**: open the chat sheet. Background matches
  `cookSurface`, no orange seam. Input row matches surface. Assistant
  bubbles use `cookAccent.withValues(alpha: 0.12)` — tinted, not raw
  orange.
- [ ] **Dark theme**: toggle system theme to dark, re-enter cook
  mode. Same spatial layout, cocoa surface, terracotta accent + sage
  completed, no flash of stale light palette.
- [ ] **Error fallback**: force a network error (offline before
  entering) — error scaffold paints cookSurface, banner tint derived
  from cookError.
- [ ] **Loading fallback**: throttle API (slow) — loading scaffold
  paints cookSurface with `cookAccent` spinner.
- [ ] **Offline mid-cook**: enable airplane mode while in cook mode
  — offline indicator icon + label adopt `cookOffline` (calm warm
  brown), not raw terracotta.
- [ ] **Post-cook feedback**: tap Done on last step — feedback sheet
  paints `cookSurface`, stars use `cookAccent`, Save button is
  `cookAccent` + `cookOnAccent`.

## Accessibility

- [ ] **TalkBack / VoiceOver**: swipe over pills — each reads "Step
  N, current|completed|upcoming". Step back and forward, and the
  pill's announcement changes accordingly.
- [ ] **Contrast** (automated): WCAG AA ≥4.5:1 on three text-on-
  surface pairs already enforced by
  `test/theme/cook_mode_theme_test.dart`.
