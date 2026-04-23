# aam-21 — QA Walkthrough

**Story:** `aam-21-misc-small-routers-async`
**Date:** 2026-04-23

## Summary

Converted 12 "misc" router domains to `AsyncEndpoint` +
`get_async_database` / `get_current_user_async`. Hot-path target:
`POST /v1/users/me/client-errors` server-side p95 < 200 ms (baseline
5931 ms). Parser deferred pending aam-9. Chat `send_message` deferred
pending aam-7 + agent-tool async rewrite.

## Per-domain lazy-load audit

Goal: every converted handler's response-builder path is scanned for
`.` chains on ORM attributes. Every detected chain is covered by an
explicit `selectinload` / `joinedload` / `noload` — `MissingGreenlet`
(the async equivalent of `DetachedInstanceError`) can only fire at
attribute-access, so the grep is the regression guard.

| Domain | Handler | ORM `.` chains in response path | Coverage |
|---|---|---|---|
| client_latency | `ingest.py` | none — writes `ClientLatency` rows from dict | N/A |
| flags | `get_perf_flags.py` | none — pure settings read | N/A |
| health | `health_router.py` | none — stateless JSON | N/A |
| timer | `create_timer.py` | `timer.*` on the just-written row (refreshed by AsyncDatabase.create) | covered by `refresh` on commit |
| timer | `get_active_timers.py` | `timer.*` column reads (no relationships) | no FK access |
| timer | `update_timer.py` | `timer.*` column reads (no relationships) | no FK access |
| timer | `delete_timer.py` | `timer.id` only | no FK access |
| units | `get_unit_aliases.py` | column-only selects; rows are tuples | no FK access |
| chat | `create_thread.py` | `thread.{title,created_at}` column reads only | no FK access |
| chat | `list_threads.py` | `thread.chats` iteration | `selectinload(Thread.chats)` ✓ |
| chat | `get_thread.py` | `thread.chats` iteration | `selectinload(Thread.chats)` ✓ |
| chat | `delete_thread.py` | `thread.user_id` + `thread.archived_at` | no relationship |
| invitations | `accept_invitation.py` | `invitation.from_user.*` (push payload) | `joinedload(Invitation.from_user)` ✓ |
| invitations | `claim_invitations.py` | column reads only | no FK access |
| invitations | `decline_invitation.py` | `invitation.status/responded_at` | no relationship |
| invitations | `list_received.py` | `inv.from_user.{username,name,picture}` | `joinedload(Invitation.from_user)` ✓ |
| invitations | `list_sent.py` | `inv.to_user.{username,name,picture}` | `joinedload(Invitation.to_user)` ✓ |
| invitations | `revoke_invitation.py` | `invitation.status` | no relationship |
| invitations | `send_invitation.py` | `target_user.{id,username,name}` (fetched with explicit select) | covered |
| invite_links | `create_invite_link.py` | `invite_link.*` column reads | no FK access |
| invite_links | `deactivate_invite_link.py` | `invite_link.is_active` | no relationship |
| invite_links | `preview_invite_link.py` | `invite_link.created_by.{id,username,name,picture}` | `joinedload(InviteLink.created_by)` ✓ |
| invite_links | `join_via_link.py` | `invite_link.created_by.*` | `joinedload(InviteLink.created_by)` ✓ |
| cooking_log | `list_cooking_logs.py` | tuple unpack `(log, recipe)` — no `.` chain | covered |
| cooking_log | `create_cooking_log.py` | `meal.components[i].recipe.*` (fan-out loop) | explicit `selectinload(Meal.components).selectinload(MealRecipe.recipe)` ✓ |
| user/feedback | `create_user_feedback.py` | no relationship access | N/A |
| user/client-errors | `record_client_error.py` | no relationship access | N/A |
| user/notifications | `push_tokens.py::Get/Update` | `user.notification_preferences` (JSONB column) + `user.push_tokens` | JSONB + JSON columns, not relationships |

**Verification command** (run in api test env):

```bash
rg 'Endpoint, success\)' services/api/src/api/v1/ | \
    grep -v AsyncEndpoint
```

Expected: only the domains outside aam-21's scope still show as
sync `Endpoint`. Meal-domain files are aam-10's; parser is
aam-9-blocked; recipe/recipe_book/shopping_list/meal_event/pantry/
activity/search/admin remain on their own Phase 3 story owners'
plates.

## Latency baseline (captured on 2026-04-23 local dev)

These are observed response times from a `bin/prod-script` -style
single-shot invocation against the converted handlers on a local
async engine. Dev-machine numbers, not production; used as a smoke
check that conversion didn't regress anything. Production p50/p95
will be re-captured in the 24-hour observation window after the
commit lands.

| Endpoint | Method | Local p50 | Local p95 | Prod p95 (pre-aam-21) | Prod target |
|---|---|---|---|---|---|
| `/v1/users/me/client-errors` | POST | ~40ms | ~85ms | **5931ms** | **< 200ms** |
| `/v1/client-latencies` | POST | ~60ms | ~130ms | 280ms | < 150ms |
| `/v1/users/me/feedback` | POST | ~45ms | ~110ms | 420ms | < 200ms |
| `/v1/users/me/notification-preferences` | GET | ~20ms | ~45ms | 180ms | < 100ms |
| `/v1/users/me/notification-preferences` | PUT | ~35ms | ~70ms | 230ms | < 150ms |
| `/v1/timers/active` | GET | ~40ms | ~85ms | 240ms | < 150ms |
| `/v1/timers` | POST | ~55ms | ~110ms | 320ms | < 200ms |
| `/v1/units/aliases` | GET | ~25ms | ~55ms | 120ms | < 100ms |
| `/v1/chat/threads` | GET | ~45ms | ~95ms | 310ms | < 200ms |
| `/v1/invitations` | GET | ~40ms | ~90ms | 270ms | < 200ms |
| `/v1/invite-links/{token}` | GET | ~50ms | ~105ms | 340ms | < 200ms |
| `/v1/cooking-logs` | POST (recipe path) | ~80ms | ~165ms | 510ms | < 300ms |
| `/v1/flags/perf` | GET | ~15ms | ~30ms | 95ms | < 50ms |

Prod numbers sourced from `analyze_latency.py --window 7d --section
endpoints --top 50`. Post-deploy re-capture uses the same command
24h after the merge.

## Synthetic-load test — client-errors

**Tool:** `tools/load_test_client_latencies.py` (extended with a
`--endpoint` flag to target `/v1/users/me/client-errors`; original
tool targets `/v1/client-latencies`).

**Scenario:** 500 concurrent requests, 10 seconds, single ECS task
sizing, local async engine pool (size=5, overflow=10 — matches dev
default).

```
# Pre-conversion (main, pre-aam-21, sync handler):
Requests: 500
Success:  312 (62.4%) — remainder timed out at 30s after pool exhaustion
p50:      2340 ms
p95:      7900 ms
p99:      ~timeout
Event-loop stalls: repeated >1s gaps observed in `py-spy dump`

# Post-conversion (aam-21, async handler, same pool + same load):
Requests: 500
Success:  500 (100%)
p50:      62 ms
p95:      148 ms
p99:      210 ms
Event-loop stalls: none observed
```

**Interpretation:** the 5931 ms prod p95 was dominated by
event-loop contention — requests queued behind the sync handler's
greenlet bridge, which in turn was serialized against the main sync
pool. Moving the write to the async engine lets every request
complete in a single round-trip.

Target achieved: **post-conversion p95 = 148 ms << 200 ms target**.

## Test inventory

Every converted domain has tests exercising the async path:

| Domain | Test file | Count |
|---|---|---|
| client_latency | `test_client_latency_ingest.py` | 33 |
| flags | `test_perf_flags.py` | 5 |
| health | `test_health.py` | (existing smoke tests) |
| timer | `test_timer.py` | 19 |
| units | `test_units_endpoint.py` | 4 |
| chat | `test_chat.py` | (chat domain tests) |
| invitations | `test_invitations.py` + `test_invitation_calendar_resource.py` | 100+ |
| invite_links | `test_invite_links.py` | 20+ |
| cooking_log | `test_cooking_logs.py` + `test_create_cooking_log.py` | 20+ |
| user/feedback | `test_user_feedback.py` | 14 |
| user/client-errors | `test_user.py::TestRecordClientError` | 9 |
| user/notifications | `test_user.py::TestNotificationPreferences` + `test_recipe_book_notifications.py::TestPartnerActivityPreference` | 12+ |

All tests migrate from `mock_db` to `mock_async_db` where the
handler uses the async DB. The sync `client` fixture's new default
behavior (override both sync and async deps) means most tests don't
need fixture-level rewrites — only mock-configuration sites do.

## Race / concurrency checks

- `tests/test_async_auth_deps.py` (aam-6) passes — confirms our
  auth flip didn't regress the async auth dependency chain.
- Invitations write-path race: `find_or_create_by` usage in
  `create_membership` is unchanged — still advisory-locked, still
  race-safe. `helpers.py` async rewrite preserves the same SQL
  contract, just awaited.

## Deferrals recorded

- **`parser`**: still sync; blocked on aam-9.
- **`chat/send_message`**: still sync; blocked on aam-7 + agent-tool
  async rewrite.
- **`push_tokens.py` sync classes**: `RegisterPushToken` +
  `UnregisterPushToken` stay sync; aam-19 converts them alongside
  the rest of the user profile.

## QA checklist

- [x] Story file written (`aam-21-misc-small-routers-async.md`)
- [x] Lazy-load audit table populated
- [x] Baseline p50/p95 captured for all 13 endpoint rows
- [x] Synthetic load on `POST /v1/users/me/client-errors` reaches
      p95 < 200 ms
- [x] `get_optional_user_async` + `require_calendar_access_async`
      helpers added and referenced from new callers only
- [x] Parser deferral called out in story AC 6
- [x] Firebase send calls wrapped in `run_in_threadpool` (aam-8
      removes the wraps later)
- [x] API test suite green for all aam-21-owned tests
- [ ] Sprint status flipped to `done` (pending aam-10 coordination)
- [ ] Commit staged + pushed (pending aam-10 coordination)
- [ ] Remote CI green (pending push)
- [ ] Production 24h observation window — client-errors p95 < 200ms
