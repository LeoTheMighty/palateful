# Story nfn-4 — Frontend per-category prefs UI

**Status:** done
**Epic:** epic-notifications-foundation-prefs-copy
**Depends on:** nfn-1.

## Scope

Adds the "Notifications by category" section to the existing
Notifications screen. 6 toggles, master switch disables but preserves
state, "Auto-save imports" relabeled to clarify it's a behavior, not a
notification opt-out.

## File list

- `app/lib/features/profile/notification_preferences_screen.dart` [MODIFY] — categories section, helpers, disabled-state visuals.
- `app/lib/core/services/api_client.dart` [MODIFY] — `categories` named param on `updateNotificationPreferences`.
- `app/test/features/profile/notification_preferences_screen_test.dart` [REWRITE] — 6 widget tests covering defaults, opt-out display, toggle dispatch, master-OFF disabled-state, master-OFF state preservation.

## Acceptance criteria

- AC1 — 6 toggles labeled "Meal reminders", "Timers", "Shopping", "Partner activity", "Imports", "Friends & invitations" with explanatory subtitles. ✅
- AC2 — Default to ON when missing from server response; reads `categories.{key}` from GET response. ✅
- AC3 — Master "Push Notifications" toggle stays at top; Quiet Hours stays at bottom. ✅
- AC4 — "Auto-save high-confidence imports" moved to its own "Import behavior" section with explicit "Not a notification setting" caption. ✅
- AC5 — Save flow PUTs `{categories: {<key>: <value>}}` per toggle; server merges into existing dict. ✅
- AC6 — Master OFF disables (greys + sets onChanged=null on) all category switches; their saved values are preserved. ✅
- AC7 — Widget tests A/B/C/D pass (default-ON, imports-off-display, toggle-dispatch, master-off-disabled). ✅
- AC8 — On API failure, local state reverts and a SnackBar surfaces the error. ✅

## QA walkthrough

See `nfn-4-qa-walkthrough.md`.
