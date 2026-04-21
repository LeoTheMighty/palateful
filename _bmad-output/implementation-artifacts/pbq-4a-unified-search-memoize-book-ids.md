# Story pbq-4a — `unified_search` memoize `_get_my_book_ids`

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Memoize `UnifiedSearch._get_my_book_ids` on the request-scoped
endpoint instance so the exact + fuzzy + semantic + meal tiers all
reuse the same `recipe_book_users` SELECT result. The instance is
created fresh per request (FastAPI dep injection of `database` +
`user`), so there's no cross-request bleed.

## Implementation notes

- **Per-instance cache, not a module cache.** `self._my_book_ids`
  is set on first call and returned on subsequent calls. Explicitly
  not a TTL cache or Redis-backed cache — the lifetime is one HTTP
  request. Disposed at request end when the `UnifiedSearch`
  instance goes out of scope.
- **No API signature change.** `_get_my_book_ids(self, user: User)`
  still returns `list[UUID]`. Callers don't know the cache exists.
- **Fallback path protected too.** `_search_my_recipes`'s
  `book_ids if book_ids is not None else self._get_my_book_ids(user)`
  fallback stays — when fired alongside the `execute()` prime, the
  second invocation is free.

## File list

- `services/api/src/api/v1/search/unified_search.py` [MODIFY] — memo
  in `_get_my_book_ids`.
- `services/api/tests/test_search.py` [MODIFY] — adds
  `test_get_my_book_ids_memoized_across_tiers`.

## Acceptance criteria — coverage

- AC1 — `_get_my_book_ids()` sets `self._my_book_ids` on first call;
  subsequent calls return the cached attr. ✅
- AC2 — Integration test: three sequential `_get_my_book_ids` calls
  on the same request-scoped instance trigger **one**
  `recipe_book_users`-shaped `db.execute` SELECT. Asserted via
  `count_queries` + `qc.select == 1`. ✅
- AC3 — p50/p95 before/after for `GET /v1/search` pasted into
  QA walkthrough. ✅

## QA walkthrough

See `pbq-4a-qa-walkthrough.md`.

## Rollback

Single commit revert. Removes the cache attr, restores the plain
`select().scalars().all()` body.
