# aam-8 — QA Walkthrough

**Story:** `aam-8-firebase-threadpool-wrap` (devx spec `aam8`)
**Date:** 2026-07-28

## Summary

Guarantees no Firebase Admin `messaging.send*` call ever runs on the
event loop. Adds four async twins to `PushNotificationService`
(`send_to_token_async`, `send_to_tokens_async`, `send_to_user_async`,
`send_to_users_async`), each dispatching the full sync body — FCM send,
`error_logs` write, invalid-token cleanup commit — via
`await run_in_threadpool(...)`. Sync methods are unchanged (worker
contract frozen — epic design principle 13). Lands dark: existing API
callsites keep their equivalent `notify_via_threadpool` /
`run_in_threadpool` hops; the audit below proves that surface is
already complete.

## What changed

| File | Change |
|---|---|
| `libraries/utils/utils/services/push_notification.py` | +4 `*_async` methods wrapping each sync send path in `run_in_threadpool` |
| `libraries/utils/test/test_push_notification_async.py` | +6 tests: threadpool-dispatch per variant, off-loop-thread proof, log-only round-trip |
| `services/api/src/api/v1/{invite_links/join_via_link,invitations/accept_invitation,invitations/send_invitation}.py`, `services/api/src/routers/v1/invitations_router.py` | Comment-only: retired stale "aam-8 hasn't landed" notes |

## Event-loop audit (AC-2)

`messaging.send*` exists in exactly one module — the push service
itself (line 567 is a comment):

```
$ grep -rn 'messaging\.send' services/api/src/ libraries/utils/utils/
libraries/utils/utils/services/push_notification.py:317:            message_id = messaging.send(message)
libraries/utils/utils/services/push_notification.py:376:            response = messaging.send_each_for_multicast(message)
libraries/utils/utils/services/push_notification.py:567:    # The Firebase Admin SDK's `messaging.send*` calls are blocking HTTP,
```

Every path from an async handler in `services/api/src/` into that
module hops through a threadpool. Full callsite census
(`grep -rnE 'get_push_service|PushNotificationService\(' services/api/src/`)
buckets into four categories, each verified caller-by-caller:

- [x] **Sync domain notify helpers** — `api/v1/recipe_book/notifications.py`
      (5 sites), `api/v1/meal_event/utils/notifications.py` (4),
      `api/v1/friends/notifications.py` (2),
      `api/v1/shopping_list/utils/notifications.py` (2). Grep for every
      exported `notify_*` symbol shows each async caller dispatches via
      `await notify_via_threadpool(...)` (recipe_router:105/313/500,
      recipe_book_router:181, meal_event_router:202,
      friends/send_request:136, friends/accept_request:67,
      shopping_list/{add_item:80, update_item:173/188,
      invite_member:121, join_shopping_list:70}) or
      `await run_in_threadpool(...)`
      (meal_event/invite_participant:91, cooking_log_router:137 →
      `_run_post_cook_fanout`, which owns its own sync `Database()`).
- [x] **Direct endpoint sends** — each wraps `push_service.send_to_user`
      in `await run_in_threadpool(...)`:
      `admin/send_test_push.py:139` (via `_send_to_user_sync`),
      `invite_links/join_via_link.py:130`,
      `invitations/accept_invitation.py:114`,
      `invitations/send_invitation.py:174`.
- [x] **`utils.services.meal_event_notifications`** (sends at 181/265) —
      `notify_meal_event_updated` reached only via
      `run_in_threadpool` (`meal_event/update_meal_event.py:243`);
      `notify_meal_event_reminder` reached only from the Celery worker
      task (`utils/tasks/meal_event_tasks/send_meal_reminders.py` —
      sync process, no event loop).
- [x] **`user/push_tokens.py`** — imports `NOTIFICATION_CATEGORIES` /
      `categories_default` only; no send calls.

No direct sync `messaging.send` — and no unwrapped
`push_service.send_*` — is reachable from any async handler.

## Manual verification checklist

- [x] **Sync API unchanged.** The four sync methods keep their original
      signatures and bodies; async variants delegate through
      `run_in_threadpool` (AC-1).
- [x] **Async variants test-covered.** `test_push_notification_async.py`
      mirrors `test_notifications_bridge.py` patterns: per-variant
      threadpool-dispatch assertions plus a real-threadpool test proving
      `messaging.send` executes off the event-loop thread (AC-3).
- [x] **Push/bridge suites green.** All push_notification +
      notifications_bridge tests pass (40 tests); pre-existing
      unrelated red on `origin/main` (`test_db_credential_provider.py`,
      `test_rotation_redeploy_handler.py` — red-stage TDD from commit
      `5a6174de`) is baseline, not a regression.
- [x] **Worker contract frozen.** `npx nx run worker:test` green against
      the library diff (AC-4).
- [x] **Full api suite green at 100% coverage** — `npx nx run api:test`
      (coverage gate enforced) (AC-5).
- [x] **Lint clean.** `npx nx run utils:lint` and
      `npx nx run api:lint` pass.

## Production safety notes

- **No contract change.** Dark rollout — no callsite switched to the
  async variants yet; response shapes, error surfaces, and worker
  behavior are byte-identical. Full revert is `git revert` of the
  branch commits.
- **No migration, no new dependency, no env var.** The
  `fastapi.concurrency` import is already satisfied in
  `libraries/utils` via `utils/api/endpoint.py`.

## Observability

- No new log lines, metrics, or error types. Exceptions raised inside
  the sync bodies surface at the `await` site exactly as from the sync
  call; the `error_logs` write and token-cleanup commit run inside the
  threadpool hop, unchanged.
