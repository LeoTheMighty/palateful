# Story meal-4: Wire MEAL_EVENT_UPDATED on shared-meal edits

**Epic:** epic-notifications-meal-reminders
**Status:** done
**Date:** 2026-04-22

## Summary

Wires the previously dormant `MEAL_EVENT_UPDATED` notification type.
When a shared meal's title / scheduled_at / recipe_id / meal_id /
meal_reminder_time changes, accepted participants (other than the
actor) get a push.

## Changes

**`services/api/src/api/v1/meal_event/update_meal_event.py`:**
- Imports `notify_meal_event_updated` from
  `utils.services.meal_event_notifications` (the shared module
  introduced in meal-3).
- Captures pre-commit `before` snapshot of the trigger fields
  (`_NOTIFY_TRIGGER_FIELDS`).
- `_compute_changed_fields(before, row)` diffs them against the
  refreshed row to decide which variants the copy function gets.
- `_format_new_time(scheduled_at)` — 12h time string for the
  "moved to X" title when only `scheduled_at` changed.
- After commit, if the event **was shared OR is still shared** AND any
  trigger field changed, calls `notify_meal_event_updated(meal_event,
  user, changed_fields, new_time, db_session)`. A raise from fan-out
  is caught + logged — never 500s the PATCH (the edit already
  committed).

**Trigger field set** (narrower than the full PATCH surface):
`{title, scheduled_at, recipe_id, meal_id, meal_reminder_time}`.
Description, notification offsets, recurrence rule tweaks — none of
these wake co-cooks.

**Actor exclusion** — handled inside `notify_meal_event_updated`
(meal-3 code), filtering the actor out of the recipient list before
the push fan-out.

## Tests

Five new cases in `services/api/tests/test_meal_event.py::TestUpdateMealEvent`:

- `test_update_title_on_shared_event_fires_meal_event_updated` —
  title change + shared event → `notify_meal_event_updated` called
  with the actor and `"title"` in `changed_fields`.
- `test_update_scheduled_at_only_passes_new_time_to_copy` — only
  `scheduled_at` changed → `new_time` formatted + passed through
  (time-specific copy variant).
- `test_update_description_only_does_not_fire_notification` —
  description change → no fan-out.
- `test_update_title_on_nonshared_event_does_not_fire` — non-shared
  event → no fan-out.
- `test_update_fanout_exception_does_not_500` — raise from the fan-out
  helper is caught; PATCH still returns 200 with the edited row.

## QA walkthrough

See `meal-4-wire-meal-event-updated-on-shared-edits-qa-walkthrough.md`.
