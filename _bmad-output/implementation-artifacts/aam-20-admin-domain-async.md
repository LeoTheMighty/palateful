# Story aam-20 — Admin Domain Async

**Status:** done
**Epic:** epic-api-async-migration (Phase 1)
**Chunk:** D-10 in `_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`

## Summary

Convert the admin domain (`/v1/admin/*`) from the sync `Endpoint` base
class to `AsyncEndpoint`. Flip every router handler from `def` →
`async def` with `Depends(get_async_database)` + a new
`require_admin_async` dependency so the admin surface runs on the async
engine end-to-end. 16 endpoint classes, 16 router handlers, 2 push
paths wrapped through the threadpool.

## Scope

### Endpoints converted (services/api/src/api/v1/admin/)
1. `get_logs.py` — `GetLogs` (CloudWatch; `boto3.client.filter_log_events` wrapped in `run_in_threadpool`)
2. `get_errors.py` — `GetErrors`
3. `get_error_detail.py` — `GetErrorDetail`
4. `list_users.py` — `ListUsers`
5. `update_user_admin.py` — `UpdateUserAdmin`
6. `get_stats.py` — `GetStats`
7. `send_test_push.py` — `SendTestPush` (push service wrapped via `run_in_threadpool` + short-lived sync `Database(db=SessionLocal())`)
8. `get_push_health.py` — `GetAdminPushHealth` (+ `_resolve_target` helper)
9. `list_feedback.py` — `ListFeedback`
10. `update_feedback_status.py` — `UpdateFeedbackStatus`
11. `get_endpoint_metrics.py` — `GetEndpointMetrics`
12. `get_task_metrics.py` — `GetTaskMetrics`
13. `get_client_metrics.py` — `GetClientRouteMetrics`, `GetClientEndpointMetrics`, `GetClientJankMetrics`, `GetClientSparkline`

### Router
- `services/api/src/routers/v1/admin_router.py` — all 16 handlers flipped to `async def` with `Depends(require_admin_async)` + `Depends(get_async_database)`; every `X.call(...)` wrapped in `await`.

### Dependencies
- `services/api/src/dependencies.py` — added `require_admin_async` (sibling of `require_admin`) that routes through `get_current_user_async`.

### Tests (services/api/tests/)
- `test_admin.py` — added `TestRequireAdminAsync`; all admin test fixtures switched from `mock_db` → `mock_async_db`.
- `test_admin_feedback.py` — fixture switch.
- `test_admin_metrics.py` — fixture switch.
- `test_admin_client_metrics.py` — fixture switch.
- `test_admin_push_health.py` — fixture switch.
- `test_admin_send_test_push.py` — fixture switch.

No tests deleted. No new tests added beyond the `TestRequireAdminAsync` pair.

## Notable decisions

1. **New `require_admin_async` dep.** The sync `require_admin` depends on
   `get_current_user` which runs sync DB I/O on the event loop — flipping
   to an async sibling keeps the admin surface fully async without
   touching the existing sync callers of `require_admin`.

2. **`SendTestPush` threadpool wrap.** The push service
   (`push_service.send_to_user`) is sync — it uses Firebase Admin SDK +
   a sync `Database` for invalid-token cleanup. `run_in_threadpool`
   with a fresh `Database(db=SessionLocal())` keeps the FCM round-trip
   off the event loop and gives the cleanup path a usable sync handle.
   Matches the pattern in `services/api/src/api/v1/invite_links/join_via_link.py`.

3. **`GetLogs` boto3 wrap.** `boto3.client("logs").filter_log_events(...)`
   is sync network I/O. Wrapped via `run_in_threadpool`. The `boto3.client`
   constructor itself stays inline (very fast, in-memory).

4. **`_resolve_target` in `get_push_health.py` made async.** It performs
   two DB lookups (UUID then email), now awaited.

## Definition of Done checklist

- [x] Every `Endpoint` subclass in `api/v1/admin/` is `AsyncEndpoint`.
- [x] Every `admin_router` handler is `async def` with
      `Depends(require_admin_async)` + `Depends(get_async_database)` and
      `await X.call(...)`.
- [x] No MCP tool file for admin exists — nothing to convert there.
- [x] All admin test files use `mock_async_db` shape. No tests deleted.
- [x] `require_admin_async` unit-tested direct (admin-user-allowed +
      non-admin-forbidden).
- [x] `npx nx run api:lint` green.
- [x] `npx nx run api:test -- tests/test_admin.py tests/test_admin_feedback.py tests/test_admin_metrics.py tests/test_admin_client_metrics.py tests/test_admin_push_health.py tests/test_admin_send_test_push.py` → **74/74 passed**.
- [x] sprint-status `aam-20-admin-domain-async` flipped `backlog → done`.

## Files Changed

### Modified
- `services/api/src/dependencies.py`
- `services/api/src/routers/v1/admin_router.py`
- `services/api/src/api/v1/admin/get_client_metrics.py`
- `services/api/src/api/v1/admin/get_endpoint_metrics.py`
- `services/api/src/api/v1/admin/get_error_detail.py`
- `services/api/src/api/v1/admin/get_errors.py`
- `services/api/src/api/v1/admin/get_logs.py`
- `services/api/src/api/v1/admin/get_push_health.py`
- `services/api/src/api/v1/admin/get_stats.py`
- `services/api/src/api/v1/admin/get_task_metrics.py`
- `services/api/src/api/v1/admin/list_feedback.py`
- `services/api/src/api/v1/admin/list_users.py`
- `services/api/src/api/v1/admin/send_test_push.py`
- `services/api/src/api/v1/admin/update_feedback_status.py`
- `services/api/src/api/v1/admin/update_user_admin.py`
- `services/api/tests/test_admin.py`
- `services/api/tests/test_admin_feedback.py`
- `services/api/tests/test_admin_metrics.py`
- `services/api/tests/test_admin_client_metrics.py`
- `services/api/tests/test_admin_push_health.py`
- `services/api/tests/test_admin_send_test_push.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Added
- `_bmad-output/implementation-artifacts/aam-20-admin-domain-async.md` (this file)
- `_bmad-output/implementation-artifacts/aam-20-qa-walkthrough.md`
