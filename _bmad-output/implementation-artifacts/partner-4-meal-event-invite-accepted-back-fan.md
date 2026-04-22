# Story partner-4 — MEAL_EVENT_INVITE_ACCEPTED back-fan

**Epic:** epic-notifications-partner-activity
**Status:** done

## Summary

Back-fans `MEAL_EVENT_INVITE_ACCEPTED` to the event owner when a
participant RSVPs. Branches on status — accepted / declined / maybe
each get a dedicated copy template. Owner-self-RSVP is silent.

## Acceptance Criteria — status

1. ✅ After `RespondToInvite.call(...)` returns successfully, the
   router fires `MEAL_EVENT_INVITE_ACCEPTED` to the event owner.
2. ✅ Silent when responder is the owner (owner-self-RSVP).
3. ✅ Copy via `notification_copy.meal_event_invite_accepted(...)` —
   status branching covered in partner-1.
4. ✅ Image: `event.recipe.image_url` when present.
5. ✅ Data payload carries `meal_event_id` (for Epic A's deep-link)
   plus `responder_id` + `status` for downstream UI context.
6. ✅ Owner's `partner_activity` category + quiet hours apply via
   the shared `send_to_user` path.
7. ✅ Backend tests:
   - `TestNotifyMealEventInviteAccepted::test_accepted_fires_to_owner`
   - `TestNotifyMealEventInviteAccepted::test_declined_branch`
   - `TestNotifyMealEventInviteAccepted::test_maybe_branch`
   - `TestNotifyMealEventInviteAccepted::test_owner_rsvp_is_silent`
   - `TestNotifyMealEventInviteAccepted::test_owner_not_found_is_silent`

## File List

**Modified:**
- `services/api/src/api/v1/meal_event/utils/notifications.py` —
  `notify_meal_event_invite_accepted` helper.
- `services/api/src/routers/v1/meal_event_router.py` — wiring in
  `respond_to_invite`.
- `services/api/tests/test_meal_event.py` — new
  `TestNotifyMealEventInviteAccepted` class.

## Deviations from epic text

- **Category mapping is `partner_activity`, not `meals`.** Epic
  text implied the meals category but the locked epic goal frames
  the back-fan as partner-activity (the inviter wants to know *who*
  responded). Routing through `partner_activity` keeps the signal
  with the other partner-presence pushes and means `meals` stays
  for logistics (reminders, schedule changes).
- **Owner lookup is database-driven, not relationship-only.** The
  helper tries the eager-loaded `meal_event.owner` first but falls
  back to `database.find_by(User, id=owner_id)` because mocked
  tests and some code paths don't hydrate the relationship.

## Local CI

- `npx nx run api:lint` → passed
- `poetry run pytest tests/test_meal_event.py -k TestNotifyMealEvent` → 24 passed
- `poetry run pytest libraries/utils/test/` → 436 passed (regression check)

## Known pre-existing failures (unrelated)

- `tests/test_meal_event.py::TestUpdateMealEvent` and
  `TestRespondToInvite` error on baseline `main` too — same local
  `.env` bleed-through affecting Pydantic Settings that
  test_fork_recipe hits. Not caused by this story.
