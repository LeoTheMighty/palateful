# QA Walkthrough — aam-28 Friends Domain Async

**Story:** `aam-28-friends-domain-async`
**Branch:** `main` (parallel /dev push)
**Date:** 2026-04-24

## Scope

8 friends endpoints flipped from `Endpoint` (sync) to `AsyncEndpoint` (async). Router goes back to `async def` with `get_async_database` + `get_current_user_async`. 2 push-notification fan-outs (`SendFriendRequest`, `AcceptFriendRequest`) routed through `notify_via_threadpool` (aam-foundations) with a new `services/api/src/api/v1/friends/notifications.py` sync helper module.

## Conversion checklist (per epic AC)

- [x] Every Endpoint subclass → AsyncEndpoint
- [x] `def execute` → `async def execute`
- [x] `self.db.execute(...).scalars()...` → `result = await self.db.execute(...); result.scalars()...`
- [x] `self.db.commit() / .delete() / .refresh()` → awaited
- [x] Router handlers `def` → `async def`, deps swapped, `await Foo.call(...)`
- [x] Push fan-out via `notify_via_threadpool` (no async session crosses into `send_to_user`)
- [x] Tests rewritten to `mock_async_db.db.execute.{return_value,side_effect}` pattern
- [x] No test deletions; every original test preserved

## Lazy-load audit

- `ListFriends`: `selectinload`/`joinedload(Friendship.friend)` — every `f.friend.username/name/picture` is covered.
- `GetFriend`: `joinedload(Friendship.friend)` — `friendship.friend.{...}` covered.
- `ListFriendRequests`: `joinedload(FriendRequest.from_user)` for received, `joinedload(FriendRequest.to_user)` for sent — every `r.from_user.{...}` / `r.to_user.{...}` covered.
- `AcceptFriendRequest`: `joinedload(FriendRequest.from_user)` — `friend_request.from_user.{...}` covered before the threadpool fan-out, snapshots taken.
- `SendFriendRequest`: re-fetches target via `select(User).where(...)` — no relationship traversal in the response builder. Snapshots captured before threadpool fan-out.
- `DeclineFriendRequest`, `CancelFriendRequest`, `RemoveFriend`: no relationship access in response builders.

No `MissingGreenlet` risk surfaces: every attribute touched after the session call site is either a column on the loaded entity or part of an explicit eager load.

## Walkthrough scenarios

### List + Get
1. `GET /v1/friends` (empty) → `200`, `count=0`, `friends=[]`.
2. `GET /v1/friends` (one friend) → `200`, `count=1`, `friends[0].username=friend1`.
3. `GET /v1/friends/{id}` (existing) → `200`, friend profile body.
4. `GET /v1/friends/nonexistent` → `404` with `code=NOT_FOUND`.

### Friend requests
5. `GET /v1/friends/requests` (none) → `200`, `received=[]`, `sent=[]`, both counts zero.

### Send request
6. `POST /v1/friends/requests {}` → `400` (missing username/user_id).
7. `POST /v1/friends/requests {"username":"target"}` → `200`, `success=true`, push fired (notify_via_threadpool invoked once).
8. `POST /v1/friends/requests {"username":"@target"}` → `200` (strip `@`).
9. `POST /v1/friends/requests {"user_id":"<uuid>"}` → `200`.
10. Username not found → `404`.
11. user_id not found → `404`.
12. Self-request → `400` (`yourself`).
13. Already friends → `400` (`already friends`).
14. Pending outgoing exists → `400` (`already have a pending`).
15. Pending incoming exists → `400` (`accept it instead`).
16. Rate limit hit (≥20/day) → `429`.
17. With message `"Let's cook together!"` → `200`.

### Accept request
18. Happy path → `200`, `friend_request.status="accepted"`, two `Friendship` rows added (bidirectional), push fired.
19. Not found → `404`.
20. Wrong recipient → `403` (`sent to you`).
21. Already accepted → `400`.
22. Already declined → `400`.

### Decline request
23. Happy path → `200`, `status="declined"`.
24. Not found → `404`.
25. Wrong recipient → `403`.
26. Already accepted → `400`.
27. Already declined → `400`.

### Cancel request
28. Happy path → `200`, `db.delete` awaited once with the request, `db.commit` awaited.
29. Not found → `404`.
30. Wrong sender → `403` (`you sent`).
31. Already accepted → `400`.
32. Already declined → `400`.

### Remove friend
33. Happy path → `200` (deletes both bidirectional rows).
34. Not found → `404`.

### Notification copy (helper unit tests)
35. `notify_friend_request_sent` — sender with username → body contains `@<username>`.
36. `notify_friend_request_sent` — no username, has name → body contains the name.
37. `notify_friend_request_sent` — neither → body contains `Someone`.
38. `notify_friend_request_accepted` — same three branches.

## Acceptance evidence

**Tests:** `npx nx run api:test -- tests/test_friends.py` → **40 passed**.
**Lint:** `npx nx run api:lint` → green.
**Coverage:** verified across friends domain via the full-suite run; helper module has 100% line coverage from the dedicated `TestNotifyFriendRequest{Sent,Accepted}` classes.

## Performance baseline

This domain is low-traffic (single-user app). Per the epic's traffic-conditional rule, no 24h post-merge p95 capture is required. Synthetic-load reuse covered by the broader `analyze_latency.py --window 7d` snapshot in `aam-26`. No regression expected — the friends endpoints are tiny, sync DB work was already quick (~10-30ms), the wins are in not-blocking-the-loop, not in raw latency.

## Rollback

One-line revert of `friends_router.py` re-enables the sync handlers (since `Endpoint` and the sync deps are still in the codebase until aam-24). No database schema changes; no terraform changes.
