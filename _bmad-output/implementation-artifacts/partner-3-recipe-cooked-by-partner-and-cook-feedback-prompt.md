# Story partner-3 — RECIPE_COOKED_BY_PARTNER + 2h cook-feedback prompt

**Epic:** epic-notifications-partner-activity
**Status:** done

## Summary

Wires two cook-log notifications:

1. **RECIPE_COOKED_BY_PARTNER** — when a cook lands against a recipe
   that lives in a shared book the cooker doesn't own, ping the
   recipe owner immediately.
2. **COOK_FEEDBACK_PROMPT** — enqueue a 2h-delayed push to the
   cooker via a new Celery task. Idempotent: if `cooking_log.notes`
   is already set by the time the task fires, it skips.

## Acceptance Criteria — status

1. ✅ After `CreateCookingLog.call(...)` returns, the router fires
   `RECIPE_COOKED_BY_PARTNER` to the book owner (via
   `notify_recipe_cooked_by_partner`) and enqueues
   `cook_feedback_prompt_task.apply_async(
     args=[cooking_log_id, user_id], countdown=7200)` for the cooker.
   Meal-level parent rows (where `data.recipe_id is None`) are
   skipped for both — see "Deviations" below.
2. ✅ `CookFeedbackPromptTask.execute(cook_log_id, user_id)`:
   - Loads `CookingLog` + `Recipe` + `User`.
   - Skips with log-line if any of those are missing, or if
     `cook_log.notes` is non-null (already-rated idempotency), or
     if `recipe_id is None` (meal-level parent).
   - Calls `notify_cook_feedback_prompt(database, user, recipe)`.
   - Catches push-send exceptions so the Celery retry doesn't fire
     again (logged, but not surfaced as a task failure).
3. ✅ `notify_cook_feedback_prompt` constructs the push from
   `notification_copy.cook_feedback_prompt(recipe_name=...)`, sets
   `data={"recipe_id", "source": "cook_feedback_prompt"}`, and
   attaches the recipe's `image_url`.
4. ✅ Title is `"🍳 {actor} cooked your {recipe}!"`; body is
   `"Tap to see how it went."`
5. ✅ Backend tests:
   - `TestNotifyRecipeCookedByPartner::test_fires_in_shared_book` —
     happy path with image URL + data shape.
   - `TestNotifyRecipeCookedByPartner::test_silent_on_solo_book` —
     `is_shared=False` ⇒ no send.
   - `TestNotifyRecipeCookedByPartner::test_self_cook_is_silent` —
     cooker owns the book ⇒ no send.
   - `TestCookFeedbackPromptTask::{log_missing, already_rated,
     meal_level_parent, recipe_missing, user_missing,
     fires_push_when_ready, send_failure_is_swallowed}` — every skip
     reason + happy path + exception guard.
   - `TestNotifyCookFeedbackPrompt::test_payload_shape` — asserts
     title/body/data/image on the constructed `PushNotification`.

## File List

**New:**
- `libraries/utils/utils/tasks/cook_feedback_tasks/__init__.py`
- `libraries/utils/utils/tasks/cook_feedback_tasks/cook_feedback_prompt.py`
- `libraries/utils/utils/services/cook_feedback_notifications.py`
- `libraries/utils/test/test_cook_feedback_prompt.py`

**Modified:**
- `services/api/src/api/v1/recipe_book/notifications.py` —
  `notify_recipe_cooked_by_partner` helper.
- `services/api/src/routers/v1/cooking_log_router.py` — fires the
  partner-cooked push + enqueues the 2h prompt.
- `services/api/tests/test_recipe_book_notifications.py` — new
  `TestNotifyRecipeCookedByPartner` class.

## Deviations from epic text

- **Meal-level parent rows skip both the partner-cooked notification
  and the feedback-prompt enqueue.** The epic's AC-1.A/B language
  reads "enqueue ... for the cooker" unconditionally, but meal-
  level parent rows have `recipe_id=None` (recipe lives on the
  child rows) and our copy library needs a recipe name — the
  skip keeps that contract clean. Every child recipe row is its
  own cook log, so if the user cooks a 3-recipe meal they get
  3 separate partner-cooked pings + 3 prompts; each child row is
  its own cook anyway.

- **Idempotency key is `notes`, not `rating`.** `CookingLog` has no
  `rating` column today; `notes` is the only signal the cook log
  carries. If/when a rating column ships, extend the check.

- **Notification fired from the router, not the endpoint class.**
  Matches the existing pattern for `notify_recipe_added` and
  `notify_recipe_forked`.

## Local CI

- `npx nx run api:lint` → passed
- `npx nx run utils:lint` → passed
- `poetry run pytest libraries/utils/test/` → 436 passed
- `cd services/api && pytest tests/test_recipe_book_notifications.py` → 31 passed
- `npx nx run migrator:check-models` → skipped locally (requires DB
  with `schema` option not present in local `DATABASE_URL`); no
  model changes in this story, CI will catch any regression.
