# Story nfn-5 — `/calendar/meals/:id` route + meal detail screen + push deep-link refinement

**Status:** done
**Epic:** epic-notifications-foundation-prefs-copy
**Depends on:** none.

## Scope

Adds a lightweight meal-event detail screen reachable via push deep-link
(`palateful://calendar/meals/:id`). Push handler in
`push_notification_service.dart` now routes `meal_event_invite` /
`meal_event_reminder` / `meal_event_updated` straight to the detail
screen when the payload includes `meal_event_id`; falls back to the
calendar root otherwise (defensive — old/missing payloads).

## Decisions / scope cuts

- Class name is `MealEventDetailScreen` (not `MealDetailScreen`) — the
  Meals feature already exports a screen of that name; renaming avoids
  a Dart import collision.
- Date formatting uses an in-house helper rather than pulling in `intl`
  (no existing `intl` dep; not worth adding for one format string).
- Edit button intentionally omitted — the screen is a notification
  target, not a full meal-management surface. The existing meal-edit
  sheet (`MealDetailSheet` in calendar/widgets/) covers that.
- "Open in Calendar" button surfaced at the bottom for users who arrived
  via the push deep-link and want to see the surrounding week.
- `getMealEvent` was added to `MealCalendarService` and `ApiClient` —
  the existing `listMealEvents` projection doesn't include the full
  participant list / recurrence rule id we need for the detail surface.

## File list

- `app/lib/core/router/app_router.dart` [MODIFY] — `/calendar/meals/:id` route under the calendar nav shell.
- `app/lib/features/calendar/meal_detail_screen.dart` [NEW] — `MealEventDetailScreen` widget.
- `app/lib/features/calendar/services/meal_calendar_service.dart` [MODIFY] — `getMealEvent(eventId)` method.
- `app/lib/core/services/api_client.dart` [MODIFY] — `getMealEvent` + `respondToMealInvite` methods.
- `app/lib/core/services/push_notification_service.dart` [MODIFY] — `_routeForNotification` deep-link refinement for meal-event types.
- `app/test/features/calendar/meal_event_detail_screen_test.dart` [NEW] — formatter + status-label + RSVP-chip-layout tests.
- `app/test/features/calendar/{meal_detail_sheet_recurring,calendar_screen,plan_meal_sheet,add_ingredients_from_calendar,per_meal_shopping_add}_test.dart` [MODIFY] — stub `getMealEvent` on each `_FakeMealCalendarService`.
- `app/test/features/profile/recurring_plans_screen_test.dart` [MODIFY] — same stub.

## Acceptance criteria

- AC1 — `/calendar/meals/:id` route mounted under the calendar `StatefulShellBranch` so the bottom nav persists. ✅
- AC2 — `MealEventDetailScreen` shows: title, scheduled-at (human-readable, local time), meal-type chip, optional Shared chip, recipe card with thumbnail (taps → `/recipes/:id`), participant list with status badges, RSVP filter chips, "Open in Calendar" footer link. ✅
- AC3 — RSVP filter chips dispatch `respondToMealInvite(status)`. Local state updates optimistically; failures surface a SnackBar. ✅
- AC4 — Loading state renders a spinner; error state renders "Couldn't load this meal — open Calendar instead" + a button. ✅
- AC5 — `_routeForNotification` for `meal_event_invite` / `meal_event_reminder` / `meal_event_updated` returns `/calendar/meals/$id` when `data.meal_event_id` is present; falls back to `/calendar`. ✅
- AC6 — Backend `MEAL_EVENT_*` already includes `meal_event_id` in the data payload — confirmed via grep of `meal_event_invitations.py` (no backend change needed). ✅
- AC7 — Widget tests cover the formatter (5 cases), status mapping (4 cases), and chip layout (1). ✅
- AC8 — Existing test fakes for `MealCalendarService` were updated to stub `getMealEvent` — no regression in the calendar/profile suites. ✅

## QA walkthrough

See `nfn-5-qa-walkthrough.md`.
