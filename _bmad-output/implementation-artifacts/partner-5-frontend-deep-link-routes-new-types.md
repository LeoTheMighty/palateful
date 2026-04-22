# Story partner-5 — Frontend deep-link routes for new types

**Epic:** epic-notifications-partner-activity
**Status:** done

## Summary

Extends `_routeForNotification` in the Flutter push service to handle
the five new partner-activity notification types. Taps now land on
the correct screen for each type, with defensive fallbacks when the
expected payload ids are missing.

## Acceptance Criteria — status

1. ✅ `recipe_forked` → `/recipes/{forked_recipe_id}` (Sarah's copy).
   Falls back to `source_recipe_id`, then `/` if both are absent.
2. ✅ `recipe_note_added` → `/recipes/{recipe_id}`. Falls back to `/`.
3. ✅ `recipe_cooked_by_partner` → `/recipes/{recipe_id}`. Falls back to `/`.
4. ✅ `cook_feedback_prompt` → `/recipes/{recipe_id}`. Falls back to `/`.
5. ✅ `meal_event_invite_accepted` → `/calendar/meals/{meal_event_id}`
   (reuses Epic A's existing meal-detail deep-link switch-case branch).
6. ✅ Defensive fallback to `/` (or `/calendar` for the meal event
   case) when ids are missing.
7. ✅ Flutter unit tests: 9 new cases in
   `PushNotificationService — partner-5 deep-link routes` group.
   Happy path + missing-id fallbacks for every type. Expose
   `_routeForNotification` via a `@visibleForTesting` wrapper.

## File List

**Modified:**
- `app/lib/core/services/push_notification_service.dart` — new cases
  in `_routeForNotification` plus `routeForNotificationForTest`
  visible-for-testing wrapper.
- `app/test/core/services/push_notification_service_test.dart` —
  new `partner-5 deep-link routes` group.

## Deviations from epic text

- **Exposed a test wrapper instead of refactoring the method.**
  `_routeForNotification` is private; a `@visibleForTesting` public
  wrapper keeps prod call sites unchanged while allowing a focused
  unit test. Alternative would have been to make the method public,
  which felt like a wider blast radius than the story warrants.

## Local CI

- `flutter test test/core/services/push_notification_service_test.dart`
  → 24 passed (9 new for this story, 15 pre-existing).
- `dart analyze app/lib/core/services/push_notification_service.dart`
  → clean (the pre-existing `unused_element_parameter` warning on
  the test file's `channel` param is unchanged).
