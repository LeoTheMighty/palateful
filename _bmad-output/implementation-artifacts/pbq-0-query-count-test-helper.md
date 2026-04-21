# Story pbq-0 — query-count test helper (hard gate)

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** none. Unblocks pbq-1 / pbq-2 / pbq-4a / pbq-4b / pbq-6 / pbq-7 / pbq-8 — every subsequent story's query-count AC uses it.

## Scope

Ship a `count_queries()` context manager in
`services/api/tests/conftest.py` plus a backing `QueryCounter`
dataclass. Subsequent pbq-* stories assert round-trip counts on list
endpoints (`qc.select <= N`, `qc.query_count_for(Model) == 1`) to
regression-proof against N+1 / redundant-query patterns.

## Implementation notes

- **Mock-layer accounting, not SQL cursor events.** The epic draft
  called out SQLAlchemy's `before_cursor_execute` event. The api test
  suite does NOT use a live engine — every test runs against the
  `MockDatabase` fixture (`MagicMock`-backed session + helper methods).
  A cursor event listener would fire zero times. `count_queries`
  instruments the mock instead: snapshots `mock_db.db.query` /
  `mock_db.db.execute` / `mock_db.db.add` / `mock_db.db.delete`
  call counts at entry and computes deltas at exit; wraps
  `MockDatabase.find_by` / `.where` / `.create` / `.create_all` /
  `.update` / `.delete` / `.save` to track invocation counts.
- **Coverage boundary.** The helper catches every N+1 whose extra hits
  manifest as explicit `db.query(...)` / `db.execute(...)` /
  `find_by` / `where` repetitions in the handler code path
  (`_readable_book_ids` per meal, `_get_my_book_ids` twice per
  request, `ensure_default_calendar` repeats, etc.). It does NOT catch
  relationship-attribute lazy loads (`sl.items`, `event.participants`)
  because mocks pre-populate those attributes — no lazy fetch ever
  fires. Stories whose fix is a `selectinload(Model.relationship)`
  pair the counter with a `selectinload` spy to verify the eager-load
  is wired.
- **`query_count_for(model)` helper.** Walks `qc.query_args` and
  matches either a direct class reference (`db.query(Meal)`) or a
  column attribute whose owning class matches
  (`db.query(RecipeBookUser.recipe_book_id)` counts as 1 query on
  `RecipeBookUser`). Makes the pbq-2 "hoist" assertion one-liner.
- **No framework.** Scope is locked by the epic — context manager +
  `QueryCounter` dataclass + docstring + one usage example. No
  per-story extensions.

## File list

- `services/api/tests/conftest.py` [MODIFY] — add `QueryCounter`
  dataclass, `count_queries` context manager, and imports
  (`contextlib.contextmanager`, `dataclasses.dataclass|field`,
  `typing.Any|Iterator`).
- `services/api/tests/test_shopping_list.py` [MODIFY] — import
  `count_queries`; add `test_count_queries_helper_tracks_mock_invocations`
  as the representative end-to-end usage example per the epic AC.

## Acceptance criteria — coverage

- AC1 — `services/api/tests/conftest.py` ships `count_queries()` as a
  context manager. ✅
- AC2 — Yields `QueryCounter` with `.total` / `.select` / `.insert` /
  `.update` / `.delete` attributes. ✅
- AC3 — One representative test in `test_shopping_list.py` exercises
  the helper end-to-end against the `/v1/shopping-lists` handler. ✅
- AC4 — Docstring shows typical usage (`with count_queries(mock_db)
  as qc: ...; assert qc.select <= 4`). ✅

## QA walkthrough

See `pbq-0-qa-walkthrough.md`.

## Rollback

Delete the `QueryCounter` + `count_queries` block from
`conftest.py`, drop the import + smoke test in `test_shopping_list.py`.
Single revert, no data migration.
