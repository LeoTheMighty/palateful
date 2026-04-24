# Story aam-28 — Friends Domain Async

**Status:** in-progress
**Epic:** epic-api-async-migration
**Created:** 2026-04-24
**Source:** `_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md` table row `D-11`. Net-new chunk added to sprint-status by the original snippet author; this story file fills it in for execution.

## Context

Friends domain is one of the per-domain async-conversion chunks. Phase 0 (commit `2243928`) already flipped friends router handlers from blocking-`async def` back to threadpooled-`def`, so the user-facing event-loop starvation is gone today. This story does the right-thing migration: every Endpoint subclass becomes an `AsyncEndpoint`, the router goes back to `async def` with async deps + awaited dispatch, and the test file converts to `mock_async_db` mock shape.

8 endpoints in scope. 2 fan out a push notification (`SendFriendRequest`, `AcceptFriendRequest`). No MCP tool file for friends — none to convert. No WebSocket. No domain-event subscriber.

## Acceptance Criteria

1. Every Endpoint subclass under `services/api/src/api/v1/friends/` inherits `AsyncEndpoint`, has `async def execute`, and uses `await self.db.execute(select(...))` / `await self.database.{find_by,create,delete,...}` instead of sync queries.
2. `services/api/src/routers/v1/friends_router.py`: every handler is `async def`, uses `Depends(get_current_user_async)` + `Depends(get_async_database)`, and returns `await Foo.call(...)`.
3. Push-notification fan-out for `SendFriendRequest` + `AcceptFriendRequest` uses `notify_via_threadpool` (aam-foundations) with a sync helper module (`api/v1/friends/notifications.py`) that takes `database: Database` and dispatches to `push_service.send_to_user`. No async session is ever passed to `send_to_user`.
4. `services/api/tests/test_friends.py` converts every `mock_db.db.execute.{return_value,side_effect}` to `mock_async_db.db.execute.{return_value,side_effect}`. All test names + assertions preserved; no test deletions. Tests for the 2 push endpoints patch `api.v1.friends.notifications.get_push_service` (where the helper now lives).
5. `npx nx run api:lint` green. `npx nx run api:test` green. 100% coverage gate stays green.
6. `sprint-status.yaml` `aam-28-friends-domain-async` flips `backlog` → `review` (then `done` after review).

## File List

**Modified:**
- `services/api/src/routers/v1/friends_router.py` — async deps, awaited dispatch
- `services/api/src/api/v1/friends/list_friends.py` — AsyncEndpoint
- `services/api/src/api/v1/friends/get_friend.py` — AsyncEndpoint
- `services/api/src/api/v1/friends/list_requests.py` — AsyncEndpoint
- `services/api/src/api/v1/friends/send_request.py` — AsyncEndpoint + notify_via_threadpool
- `services/api/src/api/v1/friends/accept_request.py` — AsyncEndpoint + notify_via_threadpool
- `services/api/src/api/v1/friends/decline_request.py` — AsyncEndpoint
- `services/api/src/api/v1/friends/cancel_request.py` — AsyncEndpoint
- `services/api/src/api/v1/friends/remove_friend.py` — AsyncEndpoint
- `services/api/tests/test_friends.py` — mock_async_db rewrite
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — backlog → review → done

**New:**
- `services/api/src/api/v1/friends/notifications.py` — sync push helpers
- `_bmad-output/implementation-artifacts/aam-28-qa-walkthrough.md`

## QA Walkthrough Plan

See `aam-28-qa-walkthrough.md`.

## Notes

- No backwards-compat shim. Every route flips in one commit; Phase 0's threadpooled path is not preserved separately because the `async def` + `AsyncEndpoint` path is byte-identical for response shapes.
- `notify_via_threadpool` is the canonical bridge (aam-foundations) — do NOT introduce a friends-local equivalent.
- `_cleanup_invalid_tokens` inside `send_to_user` calls `db_session.commit()`; passing an `AsyncSession` would deadlock or error. The sync helper module gets a sync `Database` from the bridge, so this stays sync end-to-end.
