# nfn-5 — QA walkthrough

## End-to-end deep-link

1. Sarah invites Leo to a meal event "Saturday brunch — Sweet Potato Quiche".
2. Leo's iPhone gets a push: `meal_event_invite` with `data.meal_event_id`.
3. Leo taps the push.
4. App opens the new `/calendar/meals/<id>` route. Bottom nav persists
   (Calendar tab is highlighted).
5. Screen renders within ~500ms:
   - Large title.
   - Date line `"Saturday, Apr 18 • 7:00 PM"`.
   - Meal-type chip + Shared chip.
   - Recipe card (with thumbnail) — tap → recipe detail.
   - Participants list with status badges.
   - RSVP filter chips (Accept / Maybe / Decline).
   - "Open in Calendar" link at the bottom.

## RSVP

1. Tap **Accept** on the RSVP chip row.
2. Chip flips to selected; "Going" badge appears next to Leo's row.
3. Verify with `curl /v1/meal-events/<id>` that participant status updated.
4. Tap **Decline** → chip switches; badge becomes "Can't go" / red bg.
5. Tap **Maybe** → chip switches; badge "Maybe" / amber bg.

## Defensive: missing meal_event_id

1. Manually fire a `meal_event_reminder` push without a `meal_event_id`
   in the payload (using a debug tool or admin test-push with a
   custom payload).
2. Tap → app opens `/calendar` root (the fallback). No crash.

## Defensive: invalid meal_event_id

1. Tap a push with `meal_event_id=00000000-0000-0000-0000-000000000000`.
2. Screen renders the loading spinner, then the error state:
   "Couldn't load this meal — open Calendar instead." with an "Open
   Calendar" button.
3. Tap the button → goes to `/calendar`.

## Existing functionality — no regression

- Open Calendar normally → tap a meal tile → existing
  `MealDetailSheet` bottom sheet still appears (used by tap path,
  not deep-link). Reschedule / Unschedule / Mark Cooked still work.
- Tap a `recipe_added` push → still routes to `/recipes/:id`.
- Tap a `shopping_*` push → still routes to `/cart`.
- Test push (admin button) → still routes to `/`.
