# QA walkthrough — pbq-1 `list_shopping_lists` eager-load

## What shipped

`services/api/src/api/v1/shopping_list/list_shopping_lists.py` gained
two `selectinload` options on the main `ShoppingList` query:
`selectinload(ShoppingList.items)` and
`selectinload(ShoppingList.members)`. The response loop already walks
those relationships to build `member_count` / `item_count` /
`checked_count` / `role` — pre-this-change every list row fired 2
lazy-load queries; now a single `IN`-batched `selectinload` covers the
whole page.

## Before/after numbers

**Single-operator prod (solo user, test bench).** Replay the capture
after the fix clears staging and compare:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep list_shopping_lists
```

Method for the walkthrough reader: pin this row as baseline, redeploy
pbq-1, then rerun the same command 30 minutes post-deploy. Under this
repo's single-operator prod traffic shape, the p95 delta is driven by
the relationship count per list — currently 1 list × ~0 items × 0
members, so the measurable win is bounded by the synthetic upper-bound
we set during development (below). The change carries no regression
risk and unlocks the fan-out collapse as lists accumulate items.

### Synthetic repro (20 lists × 50 items × 5 members)

Seed locally via the test_helper factories or a psql script; hit the
endpoint with warm cache + cold cache and record p50/p95 across 10
samples. Before pbq-1 this path fires 1 + 2×20 = 41 DB round-trips;
after pbq-1 it fires exactly 3 (main + items IN + members IN).

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_shopping_list.py::TestListShoppingLists --no-cov
# 4 passed
```

### 2. Query-count test locks in the fix

`test_list_shopping_lists_eager_loads_items_and_members`:

- Spies on `api.v1.shopping_list.list_shopping_lists.selectinload` and
  asserts its call args include relationships keyed `"items"` and
  `"members"`. That proves the handler's `.options(...)` wiring is
  present and will continue to use `selectinload` (not `joinedload`).
- Asserts `qc.query_count_for(ShoppingList) == 1` and `qc.select
  <= 6` so any future regression that pulls items/members via per-row
  follow-up queries (or re-queries `ShoppingList`) breaks the test.

### 3. Hit the endpoint manually

```bash
curl -H "Authorization: Bearer <token>" \
     https://api.palateful.app/v1/shopping-lists
```

Response shape byte-compatible with pre-change — same `items[]`
structure, same `total` / `limit` / `offset` fields, same `role` /
`member_count` / `is_default` per row.

### 4. analyze_latency baseline check

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format table | grep shopping-lists
```

Pin the row; confirm `list_shopping_lists` drops out of any upcoming
`--regression-hunt` run (the targeted normalized_path should no
longer be in the regression list post-deploy).

## Checklist

- [x] Main query `.options(selectinload(ShoppingList.items),
      selectinload(ShoppingList.members))`.
- [x] Response shape byte-identical — `member_count` + `item_count`
      + `checked_count` + `role` still computed in-Python.
- [x] `count_queries` integration test bounds round-trips.
- [x] `selectinload` spy verifies the eager-load wiring.
- [x] No new migrations.
- [x] No Flutter client change.

## Rollback

```bash
git revert <pbq-1-commit>
```

Single commit; removes the two `.options()` args + the `selectinload`
import. No data migration; response shape unchanged either way.
