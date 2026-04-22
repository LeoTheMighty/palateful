# Story nfn-3 — Fix RECIPE_ADDED arity bug + use copy library

**Status:** done
**Epic:** epic-notifications-foundation-prefs-copy
**Depends on:** nfn-2.

## Audit finding (recipe_router.py:91)

The "arity bug" called out in the epic was **NOT reproducible** at
implementation time. Current callsite `recipe_router.py:91-97` already
matches `notify_recipe_added`'s signature exactly: `recipe_book_id,
recipe_book_name, recipe_name, added_by_user, database`. Per the
epic's "If the bug isn't reproducible, the story collapses to 'swap
to notification_copy.py' only" clause, this story shipped only the
copy-library swap + image_url plumbing.

Plausible explanation: the bug existed when the epic was drafted, was
fixed in an unrelated commit, and the planning doc went stale. No
follow-up needed.

## Scope

- Swap inline title/body strings in `notify_recipe_added` for
  `notification_copy.recipe_added(...)`.
- Add `image_url: str | None = None` parameter to `notify_recipe_added`;
  pass through to `PushNotification(image_url=...)`.
- Wire `recipe_router.py` create-recipe handler to pass
  `params.image_url` through to `notify_recipe_added`.

## File list

- `services/api/src/api/v1/recipe_book/notifications.py` [MODIFY] — use copy library; new `image_url` param.
- `services/api/src/routers/v1/recipe_router.py` [MODIFY] — pass `params.image_url` through.
- `services/api/tests/test_recipe_book_notifications.py` [MODIFY] — new test for `image_url` attachment + central-copy assertions.

## Acceptance criteria

- AC1 — Callsite arity at `recipe_router.py:91-97` matches function signature. ✅ (was already correct; confirmed via test)
- AC2 — `notify_recipe_added` calls `notification_copy.recipe_added(actor_name=..., recipe_name=..., book_name=...)`. ✅
- AC3 — Recipe `image_url` passed through to `PushNotification(image_url=...)`. ✅
- AC4 — Recipient list excludes the actor. ✅ (existing behavior, verified by `test_sends_to_members_excluding_actor`)
- AC5 — Each recipient is checked against `categories.partner_activity` via the nfn-1 path. ✅ (`send_to_user` does this)
- AC6 — Integration test creates a shared book with two members + actor; member B receives the right copy + image; actor doesn't. ✅

## QA walkthrough

See `nfn-3-qa-walkthrough.md`.
