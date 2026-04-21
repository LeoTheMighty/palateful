# QA walkthrough — pbq-0 query-count test helper

## What shipped

`count_queries(mock_db)` context manager in
`services/api/tests/conftest.py`. Yields a `QueryCounter` with four
monotonic counters (`.select`, `.insert`, `.update`, `.delete`), a
`.total` sum, and a `.query_count_for(Model)` helper that walks the
captured `db.query(...)` args and matches either the model class or
any of its column attributes.

## Before/after numbers

**N/A — pbq-0 is the hard gate.** It ships the regression primitive
used by pbq-1 onward. No endpoint changed.

## How to verify

### 1. Helper smoke test is green

```bash
npx nx run api:test -- tests/test_shopping_list.py::TestListShoppingLists \
    -x
# 3 passed
```

The new test
`TestListShoppingLists::test_count_queries_helper_tracks_mock_invocations`
runs the `/v1/shopping-lists` handler inside `count_queries(mock_db)`,
asserts `qc.select > 0`, `qc.total >= qc.select`, and
`qc.query_count_for(ShoppingList) >= 1`.

### 2. Helper usage pattern (for pbq-1 onward)

```python
from conftest import count_queries
from utils.models.recipe_book_user import RecipeBookUser

def test_list_meals_hoists_readable_book_ids(client, mock_db, mock_user):
    # seed 30 meals ...
    with count_queries(mock_db) as qc:
        response = client.get("/v1/meals?scope=home")
    assert response.status_code == 200
    assert qc.query_count_for(RecipeBookUser) == 1
```

### 3. What the helper does and doesn't catch

| Pattern | Caught? |
| --- | --- |
| Handler calls `db.query(Model)` N times (per-item loop) | ✅ via `qc.query_count_for(Model)` |
| Handler calls `db.execute(select(...))` N times | ✅ via `qc.select` |
| Handler calls `self.db.find_by(Model, ...)` N times | ✅ via `qc.select` |
| Relationship lazy-load (`sl.items`, `event.participants`) | ❌ pair with `selectinload` spy |

Documented in the `QueryCounter` class docstring so the boundary is
visible in IDE hovers.

## Checklist

- [x] `count_queries` context manager ships in
      `services/api/tests/conftest.py`.
- [x] `QueryCounter` exposes `.select` / `.insert` / `.update` /
      `.delete` / `.total` / `.query_count_for`.
- [x] Representative end-to-end test in `test_shopping_list.py`
      proves the helper captures handler-level DB calls.
- [x] Docstring shows typical usage example.
- [x] Coverage boundary documented inline — relationship lazy loads
      are explicitly out of scope; `selectinload` spy is the
      complement.

## Rollback

```bash
git revert <pbq-0-commit>
```

One commit; no data migration; no response-shape change.
