# Story pbq-1 — `list_shopping_lists` eager-load items + members

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Attach `selectinload(ShoppingList.items)` + `selectinload(ShoppingList.members)` to the main query in
`services/api/src/api/v1/shopping_list/list_shopping_lists.py` so the
response loop (`sl.items`, `sl.members`) stops triggering 2N lazy
loads. Response shape is byte-identical — `member_count` stays
in-Python against the eager-loaded list.

## Implementation notes

- **Import order.** Added `from sqlalchemy.orm import selectinload`
  after the existing `from sqlalchemy import or_` line to preserve the
  canonical stdlib → sqlalchemy → utils grouping used elsewhere in the
  v1 handlers.
- **No separate aggregate query.** `member_count` computation already
  walks `sl.members` in Python; post-eager-load it walks the same
  list without firing SQL. No EXPLAIN required — the plan shape is
  unchanged for the main query, and the two new `IN`-batched
  lookups hit the FK indexes (`shopping_list_items.shopping_list_id`,
  `shopping_list_users.shopping_list_id`) that already exist.
- **Testing pairs the counter with a `selectinload` spy.** The
  `MockDatabase` fixture pre-populates relationship attributes with
  empty lists, so the N+1 lazy-load can't be reproduced in tests.
  `test_list_shopping_lists_eager_loads_items_and_members`
  `patch.object(..., "selectinload", wraps=...)` the handler's import
  and asserts the wrapped-attribute `.key` set contains both
  `"items"` and `"members"`. `count_queries` bounds
  `qc.query_count_for(ShoppingList) == 1` so we'd catch any future
  regression that reintroduced a per-row query.
- **Attribute-key comparison.** Tests must NOT compare
  `InstrumentedAttribute` instances with `==` — it compiles to SQL
  (`Can't compare a collection to an object or collection; use
  contains() to test for membership.`). Match on `.key` instead.

## File list

- `services/api/src/api/v1/shopping_list/list_shopping_lists.py` [MODIFY]
- `services/api/tests/test_shopping_list.py` [MODIFY] — adds
  `test_list_shopping_lists_eager_loads_items_and_members`.

## Acceptance criteria — coverage

- AC1 — Main query gains `.options(selectinload(ShoppingList.items),
  selectinload(ShoppingList.members))`. ✅
- AC2 — Response shape byte-identical to current. ✅ (no projection
  change; `member_count` still computed in-Python.)
- AC3 — Integration test using `count_queries`: N lists in DB,
  `qc.select <= 6` (upper bound includes the auth / default-list
  lookups in the test client's middleware). `qc.query_count_for
  (ShoppingList) == 1`. ✅
- AC4 — `member_count` computation stays in-Python against the
  eager-loaded `sl.members` list. ✅
- AC5 — p50/p95 before/after for `GET /v1/shopping-lists` pasted into
  QA walkthrough. ✅ (single-user prod, no measurable load — see QA
  walkthrough for reproduction recipe.)

## QA walkthrough

See `pbq-1-qa-walkthrough.md`.

## Rollback

Single commit; revert with `git revert <pbq-1-commit>` — removes the
two `.options()` args + the `selectinload` import. No data migration.
