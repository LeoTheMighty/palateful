# QA Walkthrough — partner-5

Exercises the new deep-link routes end-to-end. Requires a build
with partner-2/3/4 shipped so the pushes arrive.

## Setup

- [ ] Two test accounts (Leo + Sarah) with iOS devices.
- [ ] Shared book "Weeknight Dinners" with Leo as owner.

## Tap-through matrix

- [ ] **recipe_forked** (Sarah forks Leo's Sweet Potato Quiche).
      Tap on Leo's notification → lands on the *forked* recipe
      (Sarah's copy), not Leo's original.
- [ ] **recipe_note_added** (Sarah notes Leo's recipe). Tap →
      lands on `/recipes/{recipe_id}`.
- [ ] **recipe_cooked_by_partner** (Sarah cooks Leo's recipe). Tap
      → lands on `/recipes/{recipe_id}`.
- [ ] **cook_feedback_prompt** (Sarah's 2h post-cook push to herself).
      Tap → lands on `/recipes/{recipe_id}`.
- [ ] **meal_event_invite_accepted** (Sarah RSVPs to Leo's meal).
      Tap → lands on `/calendar/meals/{meal_event_id}` (the existing
      meal-detail screen from nfn-5).

## Cold-start vs background

- [ ] Force-kill the app, tap a `recipe_forked` push from the
      notification center. App launches and lands on the forked
      recipe route.
- [ ] Tap a push while the app is backgrounded (not killed). Same
      route lands.

## Defensive fallback

- [ ] Send a dev `recipe_note_added` push with no `recipe_id`
      in the `data` map. Tap → navigates to `/` (home) instead of
      crashing.

## Automated checklist

- [x] `flutter test test/core/services/push_notification_service_test.dart`
      — 24 passed (9 new for this story).
- [x] `dart analyze app/lib/core/services/push_notification_service.dart`
      — clean.
