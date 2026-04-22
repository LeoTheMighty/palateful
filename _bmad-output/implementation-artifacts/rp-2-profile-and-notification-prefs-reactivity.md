# rp-2 — ProfileService + NotificationPrefsService + optimistic toggle

**Status**: done
**Epic**: epic-reactive-migration-books-profile-pantry-and-polish

## What shipped

Closes AC rp-2 #1–#7. Profile + notification-prefs mutations now emit
on the MutationBus from dedicated services. Two providers
(`profileProvider`, `notificationPrefsProvider`) subscribe and
invalidate on the expected event types. The notification-prefs
optimistic toggle is preserved: the switch flips synchronously in
`setState` before the server round-trip, and reverts in `setState` on
failure before routing to `showMutationFailureSnackbar` — same UX as
before, now with centralized copy.

## Files

### New

- `app/lib/features/profile/services/profile_service.dart` —
  `getMe`, `updateProfile`, `setUsername`, `checkUsername`,
  `submitFeedback`, `exportRecipes`. Emits `ProfileUpdated` /
  `UsernameUpdated` on mutations.
- `app/lib/features/profile/services/notification_prefs_service.dart`
  — `getNotificationPreferences`, `updateNotificationPreferences`
  (scalar-field update), `updateCategoryPref` (per-category toggle).
  Both mutations emit `NotificationPrefsUpdated` carrying the full
  server payload so subscribers patch in place.
- `app/lib/features/profile/providers/profile_provider.dart` —
  `profileProvider` subscribes to `ProfileUpdated` + `UsernameUpdated`.
- `app/lib/features/profile/providers/notification_prefs_provider.dart`
  — `notificationPrefsProvider` subscribes to
  `NotificationPrefsUpdated`.
- `app/test/features/profile/profile_and_prefs_reactivity_test.dart`
  — 12 tests: emit coverage per mutation, provider invalidation
  scoping, failed-mutation-emits-nothing, export-does-not-emit.

### Modified

- `app/lib/core/di/injection.dart` — registered `ProfileService` and
  `NotificationPrefsService`.
- `app/lib/features/profile/notification_preferences_screen.dart` —
  `_toggleCategory` routes through `NotificationPrefsService`;
  preserves optimistic `setState`; failure routes through
  `showMutationFailureSnackbar`. `_updatePreference` (scalar writes)
  same migration.
- `app/lib/features/profile/profile_screen.dart` — `updateProfile` /
  `setUsername` / `submitFeedback` / `exportRecipes` now delegate to
  `ProfileService`. Export failure routes through the central
  Snackbar.

## QA walkthrough

### Regression (CI-guarded)

- [x] `profile_and_prefs_reactivity_test.dart` — 12 tests green.
- [x] Optimistic toggle path: category toggle visually flips within
  one frame of tap; failure reverts via `setState` then shows
  central Snackbar with `"Couldn't update notifications"` copy.
- [x] No breaking change to the prefs screen's external UX —
  quiet-hours pickers, timezone, auto-approve toggle all still work.

### Manual dogfood (dogfood-proof step 2)

1. Profile → Notifications → toggle Meals off.
   - [ ] Switch flips immediately (within one frame).
   - [ ] Server call fires; switch stays off on success.
2. Force failure via airplane mode → toggle Timers.
   - [ ] Switch flips off, then reverts to on within ~1s.
   - [ ] Snackbar: "Couldn't update notifications" + Retry.
   - [ ] Tap Retry → toggle airplane off → reconciles.

### Follow-ups

- `profile_screen.dart` is still StatefulWidget with imperative
  `_fetchProfile()` — not converted to `ref.watch(profileProvider)`.
  The service + provider are in place; a future polish epic can do
  the widget-side migration when it's worth the churn. Provider-
  first consumers (future surfaces) already work today.
