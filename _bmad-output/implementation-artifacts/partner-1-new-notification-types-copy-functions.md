# Story partner-1 — New NotificationType values + category mapping + copy functions

**Epic:** epic-notifications-partner-activity
**Status:** done

## Summary

Foundation story. Adds five new `NotificationType` enum values, maps
them all to the `partner_activity` category, and ships copy-library
functions plus an actor-name resolver so the callsite stories
(partner-2 / partner-3 / partner-4) become plug-ins.

## Acceptance Criteria — status

1. ✅ `NotificationType` enum gains `RECIPE_FORKED`, `RECIPE_NOTE_ADDED`,
   `RECIPE_COOKED_BY_PARTNER`, `MEAL_EVENT_INVITE_ACCEPTED`,
   `COOK_FEEDBACK_PROMPT`. All use snake_case string values.
2. ✅ `_CATEGORY_FOR_TYPE` mapping extended: all five → `"partner_activity"`.
3. ✅ Exhaustiveness assertion still holds (module imports cleanly +
   tests pass → the import-time assert would have raised otherwise).
4. ✅ `notification_copy.py` ships the five copy functions plus
   `_resolve_actor_name(actor)` with the locked fallback chain
   (`name` first word → `username` → `email` local part → `"Someone"`).
   Note: User model has `name`, not `first_name`; first-word-of-name is
   the closest proxy.
5. ✅ Unit tests:
   - `TestRecipeForked`, `TestRecipeNoteAdded`,
     `TestRecipeCookedByPartner`, `TestMealEventInviteAccepted`,
     `TestCookFeedbackPrompt` — one happy-path per function.
   - `TestRecipeNoteAdded::test_long_snippet_truncated_to_120_chars` —
     200-char note → 120-char truncated body with ellipsis.
   - `TestMealEventInviteAccepted::test_{accepted,declined,maybe,unknown}` — status branching.
   - `test_new_partner_activity_types_respect_category_opt_out` —
     parametrized across all five new types: `partner_activity=False`
     suppresses send.
   - `TestResolveActorName::*` — full fallback chain including
     empty-local-part edge case.

## File List

Modified:
- `libraries/utils/utils/services/push_notification.py`
- `libraries/utils/utils/services/notification_copy.py`
- `libraries/utils/test/test_notification_copy.py`
- `libraries/utils/test/test_push_notification.py`

## Deviations from epic text

- **`_resolve_actor_name` uses `name` not `first_name`.** User model
  has no `first_name` column; `name` is the full display name. We
  take the first whitespace-separated word as the first-name proxy.
  Behavior matches the intent of the epic's fallback chain.

## Local CI

- `npx nx run utils:lint` → passed
- `poetry run pytest libraries/utils/test/` → 428 passed
