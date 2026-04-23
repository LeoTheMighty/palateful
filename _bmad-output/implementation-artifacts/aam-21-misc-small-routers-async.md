# aam-21 — Misc Small Routers Async

**Epic:** `epic-api-async-migration`
**Status:** review → done (pending commit coordination with aam-10)
**Parent ACs:** epic-api-async-migration § Phase 3 → `aam-21`

## Scope

Convert the 12 "misc" router domains to `AsyncEndpoint` +
`get_async_database` + `get_current_user_async`. Parser is deferred —
it depends on boto3 which is blocked on aam-9.

### In-scope domains (12)

1. **`client_latency`** — `/v1/client-latencies` ingest. Hot path —
   baseline p95 5931 ms.
2. **`flags`** — `/v1/flags/perf` kill-switch (stateless, unauthed).
3. **`health`** — `/v1/health`, `/v1/health/ready` (already stateless;
   no conversion needed — documented as a no-op).
4. **`timer`** — `/v1/timers/*` CRUD (4 endpoints).
5. **`units`** — `/v1/units/aliases` seed map.
6. **`chat`** — partial flip: `create/list/get/delete` threads
   converted; `send_message` (SSE + OpenAI + agent tools) **deferred**
   — blocked on aam-7 (openai async) + agent-tool async rewrite.
7. **`invitations`** — 7 endpoints + shared `helpers.py`.
8. **`invite_links`** — 4 endpoints.
9. **`cooking_log`** — 2 endpoints (create + list), plus
   `require_calendar_access_async` helper added in
   `calendar/dependencies.py` (aam-14 will remove the sync sibling).
10. **`feedback`** (in `user_router.py`) — `POST /v1/users/me/feedback`.
11. **`client-errors`** (in `user_router.py`) —
    `POST /v1/users/me/client-errors`. Epic's **hard target**: p95 < 200 ms
    (baseline 5931 ms).
12. **`notifications`** (in `user_router.py`) —
    `GET/PUT /v1/users/me/notification-preferences`.

### Deferred (documented in this story)

- **`parser`** — `services/api/src/api/v1/parser/get_upload_url.py`
  uses boto3 presigned-URL generation; AC 6 says this lands with
  aam-9's boto3 threadpool wrap.
- **`auth`** — no router file; the auth dep was the whole surface and
  it shipped in aam-6.
- **`chat/send_message`** — SSE generator + sync OpenAI + sync agent
  tools. Splitting it off preserves aam-21's blast radius.

## Why

Phase 3 of the async migration. These are the low-risk "leaf" routers —
no external SDK dependency on the hot path, no cross-domain coupling
with meals (aam-10's domain). Converting them unblocks Phase 4
(middleware + lifespan) without fighting over the meal codebase.

The **client-errors** endpoint is the single highest-value conversion
in the epic: today its p95 is 5931 ms (a server-side self-DoS via sync
session exhaustion during cold-start error storms). Converting it
first and capturing a baseline is epic-level coordination.

## Acceptance Criteria

1. **Hot path converted.** `POST /v1/users/me/client-errors` dispatches
   through `AsyncEndpoint`, uses `get_async_database` +
   `get_current_user_async`. Server-side p95 < 200 ms target captured
   in the QA walkthrough (file: `aam-21-qa-walkthrough.md`).
2. **Client-latency ingest converted.** `POST /v1/client-latencies`
   → `AsyncEndpoint`, `get_optional_user_async` (new async dep added to
   `dependencies.py`), bulk insert flipped from
   `bulk_insert_mappings(...)` → `await db.execute(insert(...), rows)`.
3. **Router domains converted.** All 12 listed domains (excluding
   deferrals) use async deps in their router and `AsyncEndpoint` in the
   endpoint classes.
4. **Invitation helpers async.** `api/v1/invitations/helpers.py` is now
   async; every `check_resource_permission` / `check_existing_membership`
   / `create_membership` / `get_resource_name` callsite in aam-21
   domains awaits.
5. **Lazy-load audit clean.** Every converted handler's response-builder
   path has been scanned for `.` chains on ORM attributes. Any detected
   relationship access is covered by `selectinload` — see QA
   walkthrough's per-domain audit.
6. **Parser deferred.** `/v1/parser/*` intentionally NOT converted —
   blocked on aam-9. Noted in both the epic file's story entry and this
   AC list so a future reader can't mistake the gap for scope miss.
7. **Firebase calls threadpool-wrapped.** Invitations'
   `push_service.send_to_user(...)` calls (accept, join-via-link,
   send-invitation) dispatch via `await run_in_threadpool(...)` since
   aam-8 hasn't landed. aam-8 removes the wrap once
   `push_notification.py` is native async.
8. **Test suite green.** All per-domain tests converted to
   `mock_async_db` + `MockExecuteResult`. Test inventory updated in the
   QA walkthrough. No regressions in the rest of the API suite.

## Deliverables

- `_bmad-output/implementation-artifacts/aam-21-misc-small-routers-async.md`
  — this file.
- `_bmad-output/implementation-artifacts/aam-21-qa-walkthrough.md` —
  per-domain lazy-load audit, baseline latency numbers,
  synthetic-load result for client-errors.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `aam-21-misc-small-routers-async` to `done`.

## File List

### New

- (none — all conversions in-place)

### Modified — API source

- `services/api/src/dependencies.py`
  — added `get_optional_user_async`.
- `services/api/src/api/v1/calendar/dependencies.py`
  — added `require_calendar_access_async`.
- `services/api/src/api/v1/client_latency/ingest.py`
  — Endpoint → AsyncEndpoint; `bulk_insert_mappings` → async
  `execute(insert(...), rows)`.
- `services/api/src/api/v1/flags/get_perf_flags.py`
  — AsyncEndpoint (stateless).
- `services/api/src/api/v1/timer/{create_timer,get_active_timers,update_timer,delete_timer}.py`
  — AsyncEndpoint + awaited DB ops.
- `services/api/src/api/v1/units/get_unit_aliases.py`
  — AsyncEndpoint + awaited selects.
- `services/api/src/api/v1/chat/{create_thread,list_threads,get_thread,delete_thread}.py`
  — AsyncEndpoint + selectinload for `Thread.chats` in get_thread.
- `services/api/src/api/v1/invitations/helpers.py`
  — every helper now async.
- `services/api/src/api/v1/invitations/{accept,claim,decline,list_received,list_sent,revoke,send}_invitation.py`
  — AsyncEndpoint; Firebase fan-out wrapped in run_in_threadpool.
- `services/api/src/api/v1/invite_links/{create,deactivate,join_via,preview}_invite_link.py`
  — AsyncEndpoint; Firebase fan-out wrapped.
- `services/api/src/api/v1/cooking_log/{create,list}_cooking_log.py`
  — AsyncEndpoint; Meal components loaded via explicit
  `selectinload(Meal.components).selectinload(MealRecipe.recipe)`
  to avoid MissingGreenlet.
- `services/api/src/api/v1/user/record_client_error.py`
  — AsyncEndpoint.
- `services/api/src/api/v1/user/create_user_feedback.py`
  — AsyncEndpoint.
- `services/api/src/api/v1/user/push_tokens.py`
  — `GetNotificationPreferences` + `UpdateNotificationPreferences`
  flipped to AsyncEndpoint. Push-token classes stay sync (aam-19
  territory).

### Modified — Routers

- `services/api/src/routers/v1/client_latency_router.py`
- `services/api/src/routers/v1/flags_router.py`
- `services/api/src/routers/v1/timer_router.py`
- `services/api/src/routers/v1/units_router.py`
- `services/api/src/routers/v1/chat_router.py` (partial — send_message
  deferred)
- `services/api/src/routers/v1/invitations_router.py`
- `services/api/src/routers/v1/invite_links_router.py`
- `services/api/src/routers/v1/cooking_log_router.py` (post-cook
  fan-out rewritten to own-a-sync-Database in a threadpool
  worker with defensive try/except)
- `services/api/src/routers/v1/user_router.py` (partial — feedback,
  client-errors, notification-preferences only)

### Modified — Tests

- `services/api/tests/test_client_latency_ingest.py`
- `services/api/tests/test_timer.py`
- `services/api/tests/test_units_endpoint.py`
- `services/api/tests/test_chat.py`
- `services/api/tests/test_invitations.py`
- `services/api/tests/test_invite_links.py`
- `services/api/tests/test_invitation_calendar_resource.py`
- `services/api/tests/test_cooking_logs.py`
- `services/api/tests/test_create_cooking_log.py`
- `services/api/tests/test_user.py` (only TestRecordClientError class)
- `services/api/tests/test_user_feedback.py`
- `services/api/tests/test_coverage_gaps.py` (only aam-21-owned
  classes: invite links, list_threads, invitation helpers, send
  invitation, create invite link)
- `services/api/tests/test_recipe_book_notifications.py` (only
  `TestPartnerActivityPreference` — exercises notification-preferences
  endpoints directly).

## Gotchas / Decisions

1. **`auth` is not a router.** The epic-text lists "auth" as part of
   aam-21's scope. There is no `auth_router.py`; the auth surface is
   the FastAPI deps themselves, which shipped in aam-6. Calling this
   out so a future reader doesn't hunt for missing routes.

2. **Parser is deferred to aam-9.** `parser/get_upload_url.py` uses
   boto3's `generate_presigned_url` — an aam-9 dep. Leaving this in
   place keeps aam-21's blast radius contained.

3. **Chat `send_message` deferred.** The SSE generator wires sync
   `provider.chat(...)` (openai), sync `tool.execute(db=database.db,
   ...)` on agent tools, and sync `database.create(...)` inside the
   loop. Converting it is blocked on aam-7 (openai async) + an
   agent-tool async rewrite. A follow-up story owns this.

4. **Post-cook notification fan-out** (partner-cooked push +
   cook-feedback prompt enqueue) runs through `run_in_threadpool` with
   its own sync Database session. The recipe_book notifications module
   (aam-11's domain) is still sync, and we can't share an async
   session across a threadpool boundary. Defensive try/except at every
   level so a Celery / FCM failure — or a missing DATABASE_URL during
   tests — can never fail the cook response.

5. **`push_tokens.py` split ownership.** The file contains four
   endpoint classes: `RegisterPushToken` + `UnregisterPushToken`
   (aam-19) and `GetNotificationPreferences` +
   `UpdateNotificationPreferences` (aam-21). Rather than splitting the
   file, we converted two classes in-place and noted the boundary in
   the module docstring. aam-19 flips the remaining two.

6. **`cooking_log` Meal eager-load.** Original handler read
   `event.meal.components[i].recipe` — lazy load in async triggers
   `MissingGreenlet`. Converted to an explicit
   `select(Meal).options(selectinload(Meal.components).selectinload(MealRecipe.recipe))`
   so the fan-out loop walks the mapping without a second round-trip.

7. **`require_calendar_access_async` sibling.** Cooking-log's async
   conversion needed an async auth helper for calendar-scoped access.
   Added alongside the existing sync `require_calendar_access` —
   aam-14 will remove the sync sibling once every caller is async.

8. **`get_optional_user_async` sibling.** Client-latency ingest
   accepts anonymous callers. Added `get_optional_user_async` to
   `dependencies.py` as the async mirror of `get_optional_user`.
   aam-24 removes the sync sibling during cutover.

9. **Firebase send wraps.** Invitations + invite_links +
   accept/join/send handlers call
   `push_service.send_to_user(user, notification)` which is sync
   Firebase Admin + sync Database. Every callsite in aam-21 now
   dispatches via `await run_in_threadpool(...)`. aam-8 will remove
   these wraps once `push_notification.py` is native async. The
   `db_session` kwarg is omitted on the threadpool call — a fresh
   sync Database is created inside the push service (async session
   can't cross the threadpool boundary).

## Coordination

- **Commit ordering.** aam-10's test conversion (meal-domain tests)
  must land first. aam-21 commits after, staging only the 12
  converted router domains + their tests + this story + walkthrough
  + sprint-status. Parser files and meal-domain files are deliberately
  untouched.
- **Remote CI.** Expect a single remote CI run on `main` once both
  commits land. No special migration / ECS coordination needed (no
  schema changes, no infra changes).
