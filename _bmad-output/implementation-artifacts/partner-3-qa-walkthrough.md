# QA Walkthrough — partner-3

Two pushes to exercise. For the 2h-delay case, temporarily lower
`_COOK_FEEDBACK_DELAY_SECONDS` (`services/api/src/routers/v1/cooking_log_router.py`)
to ~60 during QA, or use `celery_app.send_task(..., countdown=60)`.

## Setup

- [ ] Shared book "Weeknight Dinners", Leo owns, Sarah is a member.
- [ ] Both have push tokens, `partner_activity` = true.
- [ ] Leo owns recipe "Sweet Potato Quiche" with a cover `image_url`.

## Flow C — Sarah cooks Leo's recipe

1. [ ] Sarah opens the recipe in Weeknight Dinners, enters cook mode,
       completes the cook.
2. [ ] Leo's phone buzzes:
       - title: `🍳 Sarah cooked your Sweet Potato Quiche!`
       - body:  `Tap to see how it went.`
       - image: recipe cover.

## Flow C-self — Leo cooks his own recipe

1. [ ] Leo completes a cook of his own recipe.
2. [ ] No RECIPE_COOKED_BY_PARTNER push fires (self-cook silent).
3. [ ] COOK_FEEDBACK_PROMPT is still enqueued for Leo (see Flow D).

## Flow C-solo — Sarah cooks a private recipe

1. [ ] Set up a recipe in a non-shared book Sarah has access to.
       Sarah completes a cook.
2. [ ] No partner push fires (book not shared).

## Flow D — 2h cook-feedback prompt

1. [ ] With a dev-tweaked countdown (~60s), Sarah completes a cook
       on any recipe.
2. [ ] After the countdown, Sarah's phone receives:
       - title: `How did your {recipe} turn out? 🍴`
       - body:  `Tap to add a quick rating + note.`
       - image: recipe cover when present.
3. [ ] If Sarah adds notes to the cook log *before* the countdown
       elapses, the prompt is a no-op (log shows
       `cook_feedback_prompt: user already rated ... skipping`).

## Flow D-restart — worker restart preserves the pending task

1. [ ] Complete a cook with a countdown of ~120s.
2. [ ] Restart the Celery worker within the window.
3. [ ] Task still fires ~120s after the enqueue (broker held it).

## Prefs / quiet hours

- [ ] Leo with `partner_activity=false`: Sarah cooks → no RECIPE_COOKED_BY_PARTNER push.
- [ ] Sarah with `partner_activity=false`: Sarah cooks → COOK_FEEDBACK_PROMPT is suppressed at the 2h mark.
- [ ] Quiet hours active when the 2h mark hits: push is suppressed
      (won't auto-retry after the window ends).

## Automated checklist

- [x] `npx nx run api:lint` passes.
- [x] `npx nx run utils:lint` passes.
- [x] `poetry run pytest libraries/utils/test/` — 436 passed.
- [x] `cd services/api && pytest tests/test_recipe_book_notifications.py`
      — 31 passed.
