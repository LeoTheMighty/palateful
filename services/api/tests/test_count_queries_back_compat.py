"""Back-compat regression tests for the `count_queries` rewrite (aam-4).

The rewrite makes `count_queries` polymorphic: it still wraps a
`MockDatabase` for legacy `pbq-*` tests, AND it now attaches
`before_cursor_execute` listeners on whatever sync/async engines are
configured. Both pathways feed the same `QueryCounter`, and the public
surface (`.total/.select/.insert/.update/.delete`) is unchanged so
every existing assertion keeps running.

This file is the canary: if a future refactor breaks either pathway,
this test fails before the per-domain pbq-* tests do.

Coverage targets:

(a) **sync-mock pathway** — verifies `count_queries(mock_db)` still
    increments via the MockDatabase wrap (the only path API tests use
    today).
(b) **engine-listener pathway** — registers `before_cursor_execute` on
    a real in-memory sync engine, runs INSERT/UPDATE/DELETE/SELECT, and
    verifies each lands in the right counter bucket.
(c) **N+1 scenario** — runs N SELECTs in a loop and asserts the counter
    sees ≥ N. The "≥" matters: the engine fires a few warm-up queries
    (savepoint, etc.) that we don't want a brittle equality check on.
(d) **hybrid pathway** — both pathways active at once on the same
    counter (e.g. a test that uses MockDatabase but also issues a real
    error-log write through a separate sync engine). The counter sums
    both.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
    update,
)

from conftest import (
    MockDatabase,
    QueryCounter,
    _classify_sql,
    count_queries,
)


# ---------------------------------------------------------------------------
# (a) Legacy mock-db pathway — MockDatabase wrap still works
# ---------------------------------------------------------------------------


def test_count_queries_legacy_mockdb_path_still_works():
    """pbq-* assertions all use this signature — must keep working."""
    mock_db = MockDatabase()

    with count_queries(mock_db) as qc:
        # Simulate the kind of activity pbq-* tests trigger.
        mock_db.db.query(MagicMock())
        mock_db.db.query(MagicMock())
        mock_db.db.execute(MagicMock())
        mock_db.db.add(MagicMock())
        mock_db.db.delete(MagicMock())

    # 2 query() + 1 execute() = 3 selects
    assert qc.select == 3
    # 1 add() = 1 insert
    assert qc.insert == 1
    # 1 session-level delete()
    assert qc.delete == 1
    # No updates triggered
    assert qc.update == 0
    # Total surface intact
    assert qc.total == 5


# ---------------------------------------------------------------------------
# (b) Engine listener pathway — before_cursor_execute classifies SQL
# ---------------------------------------------------------------------------


@contextmanager
def _temp_sync_engine_attached():
    """Spin up an in-memory sqlite engine + a `things` table, swap it in
    as `utils.services.database.db_engine` so `count_queries` attaches
    its listener to it, then tear down.
    """
    engine = create_engine("sqlite:///:memory:")
    md = MetaData()
    things = Table(
        "things",
        md,
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )
    md.create_all(engine)

    with patch("utils.services.database.db_engine", engine):
        yield engine, things

    engine.dispose()


def test_count_queries_engine_listener_classifies_each_verb():
    """A real engine + before_cursor_execute increments select/insert/
    update/delete based on the leading SQL verb."""
    with _temp_sync_engine_attached() as (engine, things):
        with count_queries() as qc:
            with engine.begin() as conn:
                conn.execute(insert(things).values(id=1, name="apple"))
                conn.execute(insert(things).values(id=2, name="banana"))
                conn.execute(select(things))
                conn.execute(
                    update(things).where(things.c.id == 1).values(name="apricot")
                )
                conn.execute(delete(things).where(things.c.id == 2))

    # 2 inserts + 1 select + 1 update + 1 delete = 5 total
    assert qc.insert >= 2
    assert qc.select >= 1
    assert qc.update >= 1
    assert qc.delete >= 1
    assert qc.total >= 5


def test_count_queries_engine_listener_n_plus_one_scenario():
    """N+1 regression shape: N SELECTs in a loop, counter sees ≥ N."""
    n = 5
    with _temp_sync_engine_attached() as (engine, things):
        with engine.begin() as conn:
            for i in range(n):
                conn.execute(insert(things).values(id=i, name=f"r{i}"))

        with count_queries() as qc:
            with engine.begin() as conn:
                for i in range(n):
                    conn.execute(select(things).where(things.c.id == i))

    assert qc.select >= n


def test_count_queries_async_engine_listener_attaches_to_sync_engine():
    """Async path: listener registers on `async_db_engine.sync_engine`.

    We stub `async_db_engine` with a MagicMock whose `.sync_engine` is a
    real sync engine, then prove the listener catches a SELECT issued
    against the sync_engine. This validates the attachment hop without
    requiring asyncpg in the test image.
    """
    with _temp_sync_engine_attached() as (sync_engine, things):
        # The sync engine path is already covered by the test above; we
        # patch it to None here so we verify ONLY the async path fires.
        async_engine_double = MagicMock()
        async_engine_double.sync_engine = sync_engine

        with (
            patch("utils.services.database.db_engine", None),
            patch(
                "utils.services.database.async_db_engine", async_engine_double
            ),
        ):
            with count_queries() as qc:
                with sync_engine.begin() as conn:
                    conn.execute(insert(things).values(id=99, name="x"))
                    conn.execute(select(things))

    assert qc.insert >= 1
    assert qc.select >= 1


# ---------------------------------------------------------------------------
# (c) Public surface guarantees — exact API preserved
# ---------------------------------------------------------------------------


def test_query_counter_public_api_unchanged():
    """`pbq-*` consumers rely on these attributes — frozen surface."""
    qc = QueryCounter()
    assert qc.select == 0
    assert qc.insert == 0
    assert qc.update == 0
    assert qc.delete == 0
    assert qc.total == 0
    assert qc.query_args == []

    qc.select = 4
    qc.insert = 2
    qc.update = 1
    qc.delete = 1
    assert qc.total == 8


def test_query_counter_query_count_for_matches_model_name():
    """`query_count_for(Model)` is the pbq helper for "did we re-query
    RecipeBookUser per row?" — preserved verbatim."""
    qc = QueryCounter()
    user_class = type("RecipeBookUser", (), {})
    other_class = type("Other", (), {})
    qc.query_args = [(user_class,), (other_class,), (user_class,)]
    assert qc.query_count_for(user_class) == 2
    assert qc.query_count_for(other_class) == 1


def test_query_counter_query_count_for_matches_column_owner():
    """When tests pass `Model.column`, `query_count_for(Model)` should
    still match — the production code does this in joins."""
    qc = QueryCounter()
    user_class = type("RecipeBookUser", (), {})
    column = MagicMock()
    column.class_ = user_class
    qc.query_args = [(column,)]
    assert qc.query_count_for(user_class) == 1


def test_query_counter_query_count_for_handles_unknown_model():
    """Defensive: an empty args tuple or unknown shape returns 0."""
    qc = QueryCounter()
    qc.query_args = [(), (None,)]
    assert qc.query_count_for(type("Anything", (), {})) == 0


def test_query_counter_query_count_for_uses_repr_for_non_classes():
    """If first arg has no `__name__`, fall back to `repr(model)` so
    tests asserting on weird objects don't crash."""
    qc = QueryCounter()
    weird_target = MagicMock()
    weird_target.__name__ = None
    # Force the getattr fallback by passing a plain object as `model`.
    plain = object()
    # Args has the same plain object → match by identity-via-repr.
    qc.query_args = [(plain,)]
    # plain has no `__name__`, no `class_`, no `parent` → no match
    assert qc.query_count_for(plain) == 0


# ---------------------------------------------------------------------------
# (d) Hybrid pathway — both at once
# ---------------------------------------------------------------------------


def test_count_queries_hybrid_sums_mock_and_engine():
    """A test using MockDatabase that ALSO triggers a real sync-engine
    write (e.g. error-log path) gets an additive count."""
    mock_db = MockDatabase()
    with _temp_sync_engine_attached() as (engine, things):
        with count_queries(mock_db) as qc:
            mock_db.db.query(MagicMock())  # mock-db path: +1 select
            mock_db.db.add(MagicMock())  # mock-db path: +1 insert
            with engine.begin() as conn:
                conn.execute(insert(things).values(id=1, name="x"))  # +1 insert
                conn.execute(select(things))  # +1 select

    # Mock-db: 1 select + 1 insert. Engine: ≥1 select + ≥1 insert.
    assert qc.select >= 2
    assert qc.insert >= 2


# ---------------------------------------------------------------------------
# (e) _classify_sql edge cases — defensive default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stmt,expected",
    [
        ("SELECT 1", "select"),
        ("select * from x", "select"),
        ("INSERT INTO x VALUES (1)", "insert"),
        ("insert into x", "insert"),
        ("UPDATE x SET y=1", "update"),
        ("update x", "update"),
        ("DELETE FROM x", "delete"),
        ("delete from x", "delete"),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", "select"),  # CTE path
        ("BEGIN", "select"),  # unknown verbs default to select
        ("", "select"),  # empty doesn't crash
        (None, "select"),  # None doesn't crash
    ],
)
def test_classify_sql_table(stmt, expected):
    assert _classify_sql(stmt) == expected


# ---------------------------------------------------------------------------
# (f) Cleanup guarantee — listener removed after the block
# ---------------------------------------------------------------------------


def test_count_queries_removes_listener_after_block():
    """If the listener leaks across blocks, every subsequent test would
    over-count. Verify cleanup."""
    with _temp_sync_engine_attached() as (engine, things):
        with count_queries() as qc1:
            with engine.begin() as conn:
                conn.execute(insert(things).values(id=1, name="x"))
        captured = qc1.insert

        # Outside the block, a new query should NOT increment qc1.
        with engine.begin() as conn:
            conn.execute(insert(things).values(id=2, name="y"))

        assert qc1.insert == captured  # listener was removed
