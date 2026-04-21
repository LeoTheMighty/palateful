# QA walkthrough — pbq-4a unified_search memoize book_ids

## What shipped

`UnifiedSearch._get_my_book_ids(user)` caches its result on the
request-scoped endpoint instance as `self._my_book_ids`. The first
call fires the SELECT and stores the result; subsequent calls within
the same request return the cached list without hitting the DB.

## Before/after numbers

### Query count (hard AC)

| Flow | Pre-pbq-4a | Post-pbq-4a |
| --- | --- | --- |
| 3× `_get_my_book_ids` calls in a single request | 3 SELECTs | **1** |

Enforced by `test_get_my_book_ids_memoized_across_tiers`:

```python
with count_queries(mock_db) as qc:
    ep._get_my_book_ids(user); ep._get_my_book_ids(user); ep._get_my_book_ids(user)
assert qc.select == 1
```

### Latency (single-operator prod)

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep unified_search
```

Method: pin baseline → redeploy → 30-min follow-up. `recipe_book_users`
membership SELECTs are indexed, so the pre-fix redundant calls are
milliseconds each. The win scales with how many tiers fire per
request: a query that falls through to the semantic tier hits the
method twice (exact + fallback), so the saving is ~1 SELECT per
request at the worst-case path.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_search.py --no-cov
# existing tests still pass + new memoization test passes
```

### 2. Hit the endpoint

```bash
curl -H "Authorization: Bearer <token>" \
     "https://api.palateful.app/v1/search?q=pasta"
```

Response shape byte-identical.

### 3. Confirm no regression on `book_id` filter path

`execute()` passes `effective_book_ids` (a subset of `my_book_ids`)
into `_search_my_recipes`. That path bypasses the memoized accessor
entirely — no change, same result.

## Checklist

- [x] `self._my_book_ids` cache attr set on first call, read on
      subsequent calls.
- [x] `count_queries`-backed test locks in single-SELECT behavior.
- [x] Per-instance cache (request-scoped), not a module-level or
      time-bounded cache.
- [x] No response-shape change.

## Rollback

```bash
git revert <pbq-4a-commit>
```

Removes the cache attr + memoization; restores the plain
`select().scalars().all()` body. Single commit.
