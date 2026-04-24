# Story aam-13: Shopping-list domain async

**Status**: in-progress
**Epic**: epic-api-async-migration
**Phase**: 3 — Per-domain conversions (D-03)

## Context

Phase 0 flipped 150 router handlers from `async def` (blocking) to `def` (threadpool) to unblock the event loop — shopping-list handlers currently run in the FastAPI threadpool on sync `Database`. This chunk rewrites the domain to `AsyncEndpoint` + `AsyncDatabase` + async HTTP handlers so reads and writes run natively on the event loop, freeing threadpool slots for the sync helpers (notifications, pantry_service, boto3) that stay sync for now.

A prior /dev session landed the same conversion locally, hit lint green, had 131/201 tests passing on `test_shopping_list.py`, and then was wiped by a parallel-agent checkout collision. This run redoes the work — gotchas from the prior session are pre-encoded in this story so the agent doesn't rediscover them.

## Acceptance Criteria

1. **Endpoints** — every `class X(Endpoint)` under `services/api/src/api/v1/shopping_list/` (excluding `websocket.py` and `bootstrap.py`) becomes `class X(AsyncEndpoint)` with `async def execute`. Every `self.database.find_by(...)`, `self.database.create(...)`, `self.database.update(...)`, `self.database.delete(...)`, `self.database.db.commit()` / `flush()` / `refresh()` is `await`ed. Every `self.db.query(...)` → `await self.db.execute(select(...))`.
2. **Router** — every HTTP handler in `services/api/src/routers/v1/shopping_list_router.py` becomes `async def`, uses `Depends(get_current_user_async)` + `Depends(get_async_database)`, and `return await X.call(...)`. The WebSocket handler (`@router.websocket("/{list_id}/ws")`) stays on `get_database` + sync body per Phase 0 — do not touch.
3. **MCP tool** — `services/api/src/mcp_server/tools/shopping.py` flips every `call_endpoint(...)` to `await call_endpoint_async(...)` and tool functions become `async def`.
4. **Notifications** — every `notify_*` call in `add_item.py`, `update_item.py`, `join_shopping_list.py`, `invite_member.py` dispatches through `await notify_via_threadpool(notify_fn, ...)` (from `utils.services.notifications_bridge`). Commit async state before the notify fan-out. Sync helper signatures unchanged.
5. **Activity creation** — `add_item.py`'s sync `create_activity(db, ...)` loop is inlined as `self.db.add(UserActivity(...))` with a single `await self.db.commit()` after the loop (sync `create_activity` takes `Session`, not `AsyncSession`).
6. **Pantry side-effect (update_item.py)** — `get_or_create_default_pantry` + `upsert_pantry_ingredient` from `utils.services.pantry_service` stay sync (aam-15 is landing the async conversion in parallel; if it merges first, this story rebases). Call them via `run_in_threadpool` with a fresh `Database(db=SessionLocal())` inside the threadpool body. Domain event dispatcher (`dispatch`) stays sync — it's in-memory only.
7. **Event replay (get_events.py)** — do NOT create a parallel `AsyncShoppingListEventService`. Inline the two reads (`get_events_since` + `get_current_sequence`) directly into the async handler: `select(ShoppingListEvent).options(selectinload(.user)).where(...).order_by(sequence).limit(...)` and `select(func.max(sequence)).where(...)`. `ShoppingListEventService` itself stays intact — it's still used by the sync WebSocket handler.
8. **Lazy-load audit** — every handler that reads `sl.items`, `sl.members`, `sl.owner`, `target_membership.user`, `item.meal_event`, `recipe.ingredients`, or `recipe_ing.ingredient` uses `selectinload` at query time. Under `AsyncSession`, lazy-load = `MissingGreenlet` at attribute access. Specific eager-load table pasted in QA walkthrough.
9. **Incidental bug fix** — `remove_member.py` currently uses `datetime.now(datetime.UTC)` which doesn't exist on the imported `datetime` class (the attribute lives on the `datetime` module). Change import to `from datetime import UTC, datetime` and callsite to `datetime.now(UTC)`. Existing `datetime.utcnow()` callsites in `get_shopping_list.py` and `get_events.py` stay — they preserve naive-datetime behavior tests rely on.
10. **Tests** — `test_shopping_list.py` (201 tests), `test_check_off_items.py` (13 tests), `test_shopping_list_router_broadcasts.py` (7 tests) convert to `mock_async_db` / `MockExecuteResult` pattern. No test deletions. Every test name + assertion preserved. 100% coverage on converted files.
11. `npx nx run api:lint` passes. `npx nx run api:test` passes (full suite, 100% coverage gate).
12. **Sprint-status** — flip `aam-13-shopping-list-domain-async: backlog` → `review` → `done` via per-story commit.

## File List

### Modified (Endpoints)
- `services/api/src/api/v1/shopping_list/add_item.py`
- `services/api/src/api/v1/shopping_list/assign_item.py`
- `services/api/src/api/v1/shopping_list/create_shopping_list.py`
- `services/api/src/api/v1/shopping_list/delete_item.py`
- `services/api/src/api/v1/shopping_list/delete_shopping_list.py`
- `services/api/src/api/v1/shopping_list/generate_from_meal_event.py`
- `services/api/src/api/v1/shopping_list/get_deadlines.py`
- `services/api/src/api/v1/shopping_list/get_events.py`
- `services/api/src/api/v1/shopping_list/get_shopping_list.py`
- `services/api/src/api/v1/shopping_list/invite_member.py`
- `services/api/src/api/v1/shopping_list/join_shopping_list.py`
- `services/api/src/api/v1/shopping_list/list_members.py`
- `services/api/src/api/v1/shopping_list/list_shopping_lists.py`
- `services/api/src/api/v1/shopping_list/organize_by_store.py`
- `services/api/src/api/v1/shopping_list/populate_from_recipe.py`
- `services/api/src/api/v1/shopping_list/remove_member.py`
- `services/api/src/api/v1/shopping_list/share_shopping_list.py`
- `services/api/src/api/v1/shopping_list/update_item.py`
- `services/api/src/api/v1/shopping_list/update_member.py`
- `services/api/src/api/v1/shopping_list/update_shopping_list.py`

### Modified (Router + MCP + tests)
- `services/api/src/routers/v1/shopping_list_router.py` — HTTP handlers async; WebSocket handler untouched.
- `services/api/src/mcp_server/tools/shopping.py` — `async def` + `call_endpoint_async`.
- `services/api/tests/test_shopping_list.py` — `mock_async_db` pattern.
- `services/api/tests/test_check_off_items.py` — `mock_async_db` pattern.
- `services/api/tests/test_shopping_list_router_broadcasts.py` — `mock_async_db` pattern (only where the endpoints touched flip; WS-side assertions stay on `mock_db`).

### Modified (sprint-status + QA walkthrough)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — aam-13 flips to `done`.

### New
- `_bmad-output/implementation-artifacts/aam-13-qa-walkthrough.md` — lazy-load audit table, 10-scenario QA checklist, rollback notes.

## Do Not Touch

- `services/api/src/api/v1/shopping_list/websocket.py` — Phase 0 has it on threadpool; stays sync.
- `services/api/src/api/v1/shopping_list/bootstrap.py` — not an endpoint; called from auth onboarding on sync `Database`. Changing it would ripple into auth flow which is out of scope.
- `libraries/utils/utils/services/shopping_list_event_service.py` — still used by the sync WS handler.
- `libraries/utils/utils/services/pantry_service.py` — aam-15 owns it.
- Endpoints / routers outside `shopping_list/`. aam-12a / aam-15 / aam-16 are running in parallel.

## Notes

- **Commit cadence** — commit endpoint conversions in batches of ~5 files (plus 1 for router + MCP, 1 for tests) with `--no-verify` WIP commits to survive parallel-agent collision. After all-green, `git reset --soft origin/main` and rebuild one clean commit.
- **`AsyncDatabase.create(x)` already commits + refreshes.** Do NOT call `self.database.db.refresh(x)` after. Same for `.update(x, ...)` and `.save(x)`.
- **Test side_effect sizing:** count `await self.db.execute(...)` + `await self.database.find_by(...)` + `await self.database.where(...).all()` in each endpoint's happy path; that's the list length. Reference: `services/api/tests/test_meal_router.py::TestGetMeal`.
- **Staging strategy:** `git add <specific files>` only — never `git add -A` (other agents will collide on `sprint-status.yaml` and the other uncommitted files visible in `git status`).
