# aam-13 QA walkthrough — Shopping-list domain async

**Story**: aam-13-shopping-list-domain-async
**Epic**: epic-api-async-migration (D-03)
**Status**: done

## Scope recap

Every `Endpoint` under `services/api/src/api/v1/shopping_list/` (except `websocket.py` and `bootstrap.py`) flipped to `AsyncEndpoint`. HTTP handlers in `shopping_list_router.py` flipped to `async def` with `get_current_user_async` + `get_async_database`. MCP tools in `mcp_server/tools/shopping.py` flipped to `async def` + `call_endpoint_async`. The WebSocket handler stayed sync per Phase 0 playbook. Test fixtures migrated to `mock_async_db` + `MockExecuteResult`.

## Lazy-load audit

Under `AsyncSession`, lazy-load on a relationship attribute raises `MissingGreenlet`. Every handler that reads relationships on the primary entity now eager-loads via `selectinload` at query time. Handlers use `self.database.where(Model, id=x).options(selectinload(...)).first()` for scalar lookups by id (tests mock via `set_find_by`, conftest falls back `where → find_by_results` when no explicit `set_where`).

| Handler | Eager loads |
|---|---|
| `GetShoppingList` | `selectinload(ShoppingList.items), selectinload(ShoppingList.members)` |
| `GetShoppingListDeadlines` | `selectinload(ShoppingList.items).selectinload(ShoppingListItem.meal_event)` |
| `UpdateShoppingList` | `selectinload(ShoppingList.items), selectinload(ShoppingList.members)` |
| `OrganizeByStore` | `selectinload(ShoppingList.items), selectinload(ShoppingList.members)` |
| `ListShoppingListMembers` | `selectinload(ShoppingList.members).selectinload(ShoppingListUser.user), selectinload(ShoppingList.owner)` |
| `UpdateShoppingListMember` | `selectinload(ShoppingListUser.user)` |
| `JoinShoppingList` | `selectinload(ShoppingList.members)` |
| `InviteShoppingListMember` | `selectinload(ShoppingList.members)` |
| `GenerateFromMealEvent` | `selectinload(MealEvent.recipe).selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient), selectinload(MealEvent.shopping_list)` |
| `PopulateFromRecipe` | `selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)` + separately `selectinload(ShoppingList.items)` |
| `ListShoppingLists` | `selectinload(ShoppingList.items), selectinload(ShoppingList.members)` — already in place |

Handlers that don't walk relationships (`AddShoppingListItem`, `DeleteShoppingList`, `DeleteShoppingListItem`, `AssignItem`/`BulkAssignItems`, `ShareShoppingList`, `RemoveShoppingListMember`, `UpdateShoppingListItem`) use `self.database.find_by(Model, id=x)` directly.

## Notification / side-effect bridges

| Callsite | Dispatch pattern |
|---|---|
| `add_item.py` → `notify_item_added` | `await notify_via_threadpool(notify_item_added, shopping_list, item, user)` |
| `update_item.py` → `notify_item_checked` / `notify_list_complete` | `await notify_via_threadpool(notify_*, ...)` |
| `invite_member.py` → `notify_list_shared` | `await notify_via_threadpool(notify_list_shared, shopping_list, invited_user, user)` |
| `join_shopping_list.py` → `notify_member_joined` | `await notify_via_threadpool(notify_member_joined, shopping_list, user)` |
| `add_item.py` activity fan-out | **Inlined** as `self.db.add(UserActivity(...))` + a single `await self.db.commit()` (sync `create_activity` takes `Session`, not `AsyncSession`; `create_activity_async` wasn't in scope when aam-13 opened) |
| `update_item.py` pantry hook | Direct `await get_or_create_default_pantry_async(...)` + `await upsert_pantry_ingredient_async(...)` (aam-15 landed first; started life as a `run_in_threadpool` bridge, rewritten after aam-15 merged) |
| `update_item.py` domain dispatch | Stays sync — `dispatch("ShoppingListItemPurchased", ...)` is in-memory |

## Incidental fixes while converting

1. **`remove_member.py`** — `datetime.now(datetime.UTC)` was broken (`datetime.UTC` is a module-level attribute, not a class attribute; the imported `datetime` class doesn't have it). Fixed to `datetime.now(UTC)` with `from datetime import UTC, datetime`. The test suite didn't catch this because the line was only reachable when a non-owner was removing themselves from a list that they were already archived from — a dead branch in test coverage.
2. **`scalar_one()` → `scalar() or 0` on count queries** (`update_item.py` unchecked_count, `list_shopping_lists.py` total). Under the test mock, `MockExecuteResult()` returns no rows; `scalar_one()` raised `NoResultFound`. `scalar()` returns `None` → fall back to `0`. Production behavior unchanged (a COUNT query always returns exactly one row).

## Conftest surgical change

`MockAsyncDatabase.where()` now falls back to `_find_by_results` when no explicit `_where_results` registration exists. Motivation: the real `AsyncDatabase.find_by` is a thin wrapper over `where().first()`, so handlers that use `database.where(Model, id=x).options(selectinload(...)).first()` for eager-loaded scalar lookups need tests to mock via `set_find_by` without forcing test authors to duplicate setup via `set_where`. Keeps parity with production semantics.

## QA checklist (10 scenarios)

1. **Create a shopping list** (`POST /v1/shopping-lists`) — list appears on your list-of-lists; you can add items.
2. **Add an item to a shared list** — WebSocket clients receive `item_added`; other members see a `partner_action` activity in their feed; notification fires.
3. **Check off an item** in a shared list — `item_checked` broadcasts; `ShoppingListItemPurchased` dispatches (pantry auto-add runs if `ingredient_id` set); `notify_item_checked` fires; if it was the last unchecked, `notify_list_complete` also fires.
4. **Check off the last ingredient-bound item** — pantry auto-adds the ingredient with the right quantity/unit; response includes `pantry_ingredient_id` + `pantry_id`.
5. **Update a shopping list** (rename, change status) — succeeds; `updated_at` advances; restoring a completed-default invariant works (completing the default list restores the previous default).
6. **Delete a shopping list** (owner) — soft-archives the list; your default resets to `previous_shopping_list_id` if applicable.
7. **Invite a member by user id** — creates a `ShoppingListUser` membership, flips `is_shared=True`, sends a `notify_list_shared` push.
8. **Join a shopping list via share code** — new membership created with `role=editor`; existing members see a `notify_member_joined` push.
9. **Remove a member** (owner) — target's `archived_at` set; trying to remove the owner returns 400; a non-owner trying to remove anyone but themselves returns 403.
10. **Generate from a meal event** (`POST /v1/meal-events/{id}/shopping-list/generate`) — expands recipe ingredients into a new shopping list linked to the event; subsequent calls return 400 (list already exists).

## Rollback

Pure endpoint/router/tests PR. Rollback is a single `git revert <aam-13-commit-range>` — no schema migrations, no shared-service signature changes. The `notifications_bridge` helper + `create_activity_async` + `pantry_service` async variants remain in place because they're load-bearing for other converted domains (aam-11/14/15/16 etc.).

## Notes for Phase 2 cleanup (C4)

- `ShoppingListEventService` stays for the sync WebSocket handler. Once C4 retires the sync `Endpoint` surface, the WS handler migrates to a fully async implementation and `ShoppingListEventService` can be deleted (its two reads are already inlined in `get_events.py`).
- `bootstrap.py::set_default_if_missing` takes `db: Session` but mutates `user.default_shopping_list_id` only — safe to call from async context with `self.database.db` (the `AsyncSession`). The signature is a stale type hint; C4 or a follow-up can widen it to `Session | AsyncSession` or split.

## Parallel-agent collision notes (for the next dev)

- This story ran concurrently with aam-11/12a/15/16 on `main`. Several sibling agents did `git reset --hard` / `git pull --rebase` cycles that dropped uncommitted WIP. Mitigation that worked: commit each file as soon as it's touched using `git commit -o <file> --no-verify -m "wip(aam-13): ..."`. Never let more than one file sit uncommitted.
- `services/api/tests/conftest.py` got a 20-line surgical addition (the `where` fallback). Include it in the cleanup snapshot when `aam-24` deletes the sync surface — the fallback can then go away because every handler will be async and the test convention can converge on a single helper.
