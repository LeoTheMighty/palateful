# Story partner-2 — RECIPE_FORKED + RECIPE_NOTE_ADDED callsites

**Epic:** epic-notifications-partner-activity
**Status:** done

## Summary

Wires the foundation types from partner-1 to their callsites. When a
partner forks one of your recipes, you get a push. When a partner
adds a note to your recipe in a shared book, you get a push with the
(truncated) note snippet. Self-actions, solo-book notes, and books
without an active owner are all silent.

## Acceptance Criteria — status

1. ✅ After `ForkRecipe.call(...)` returns successfully, the router
   fires `RECIPE_FORKED` to the owner of the source recipe's book.
   Self-forks are silent (`notify_recipe_forked` short-circuits when
   `owner.id == actor.id`). Data payload carries `forked_recipe_id` +
   `source_recipe_id`. Image sourced from `recipe.image_url`.
2. ✅ After `AddRecipeNote.call(...)` returns successfully, the router
   fires `RECIPE_NOTE_ADDED` to the owner of the recipe's book — only
   when the book `is_shared` AND the actor is not the owner. Data
   payload carries `recipe_id` + `note_id`. Image sourced from
   `recipe.image_url`.
3. ✅ Each recipient's per-user / per-category / quiet-hours checks
   apply (inherited from the shared `send_to_user` path).
4. ✅ Unit tests:
   - `TestNotifyRecipeForked::test_fires_push_to_book_owner` — happy
     path asserts title/body/image/data shape.
   - `TestNotifyRecipeForked::test_self_fork_is_silent` — actor owns
     the book ⇒ no send.
   - `TestNotifyRecipeForked::test_no_owner_is_silent` — book has no
     owner row ⇒ no send.
   - `TestNotifyRecipeNoteAdded::test_fires_in_shared_book` — happy
     path.
   - `TestNotifyRecipeNoteAdded::test_silent_on_solo_book` —
     `is_shared=false` ⇒ no send.
   - `TestNotifyRecipeNoteAdded::test_long_note_gets_truncated_in_body`
     — 200-char note → 120-char ellipsis-suffixed body.
   - `TestNotifyRecipeNoteAdded::test_self_note_is_silent` — actor
     owns the book ⇒ no send.

## File List

Modified:
- `services/api/src/api/v1/recipe_book/notifications.py` —
  `notify_recipe_forked`, `notify_recipe_note_added`, `_find_book_owner`
  helper.
- `services/api/src/routers/v1/recipe_router.py` — wiring for both
  callsites.
- `services/api/tests/test_recipe_book_notifications.py` — new tests.

## Deviations from epic text

- Notifications are fired from the **router**, not inside
  `ForkRecipe.execute` / `AddRecipeNote.execute`. This matches the
  existing pattern for `notify_recipe_added` (fired from `recipe_router`
  after `CreateRecipe.call` returns) — consistency with the sibling
  notification keeps the endpoint classes pure.
- Recipe "owner" is resolved via `RecipeBookUser.role == "owner"` on
  the recipe's book, because neither `Recipe` nor `RecipeBook` has an
  `owner_id` column directly.

## Local CI

- `npx nx run api:lint` → passed
- `cd services/api && poetry run pytest tests/test_recipe_book_notifications.py`
  → 28 passed

## Known pre-existing failures (unrelated)

- `services/api/tests/test_fork_recipe.py` — 7 errors on baseline `main`
  before my changes too; caused by a local `.env` file leaking extra
  keys into the Pydantic Settings load. Not a regression from this
  story; needs a separate fix.
