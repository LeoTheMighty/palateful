"""aam-23: lifespan pool pre-warm.

The single-connection warm-up aam-1 landed only ever primed one asyncpg
connection — the pool hands the same one back to a sequential loop. These
tests pin the expanded behaviour:

* every pooled connection (up to `DB_ASYNC_POOL_SIZE`) gets a `SELECT 1`;
* the checkouts are concurrent, so distinct connections are primed and the
  added startup cost stays ~one connection's latency rather than N;
* the warm-up runs *before* the lifespan yields, so `/v1/health` cannot
  flip green until the pool is hot;
* sync-first / async-second startup ordering and the reversed dispose
  order (pre-landed in aam-1) still hold;
* a partial failure is best-effort — logged, never a crash-loop.

The engine is faked rather than mocked so concurrency is observable:
`FakeAsyncEngine` tracks how many checkouts are live at once, which a
`MagicMock` cannot show.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from utils.constants import DB_ASYNC_POOL_SIZE


class FakeAsyncConnection:
    """One checked-out connection. Records the statements it ran."""

    def __init__(self, engine: "FakeAsyncEngine", index: int):
        self._engine = engine
        self._index = index

    async def execute(self, statement):
        self._engine.statements.append(str(statement))
        if self._engine.delay:
            await asyncio.sleep(self._engine.delay)
        if self._engine.gate is not None:
            await self._engine.gate.wait()
        if self._index in self._engine.fail_indices:
            raise RuntimeError(f"connection {self._index} refused")


class FakeAsyncEngine:
    """Minimal stand-in for the SQLAlchemy async engine.

    `connect()` is sync and returns a fresh async context manager, matching
    `AsyncEngine.connect()`. Each checkout is tracked so a test can assert
    how many ran concurrently.
    """

    def __init__(self, *, delay: float = 0.0, fail_indices=(), gate=None,
                 on_dispose=None):
        self.delay = delay
        self.fail_indices = set(fail_indices)
        self.gate = gate
        self.statements: list[str] = []
        self.checkouts = 0
        self.live = 0
        self.max_concurrent = 0
        self.disposed = 0
        self._on_dispose = on_dispose

    def connect(self):
        index = self.checkouts
        self.checkouts += 1
        engine = self

        class _ConnectionContext:
            async def __aenter__(self_inner):
                engine.live += 1
                engine.max_concurrent = max(engine.max_concurrent, engine.live)
                return FakeAsyncConnection(engine, index)

            async def __aexit__(self_inner, exc_type, exc, tb):
                engine.live -= 1
                return False

        return _ConnectionContext()

    async def dispose(self):
        self.disposed += 1
        if self._on_dispose is not None:
            self._on_dispose()


class _NoOpMcpContext:
    """Stands in for the MCP streamable-http session manager context."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _NoOpMcpApp:
    class router:
        @staticmethod
        def lifespan_context(_app):
            return _NoOpMcpContext()


class TestPoolPreWarm:
    """Every pooled connection is primed, concurrently, before serving."""

    async def test_warms_every_pool_connection(self):
        from main import app, lifespan

        engine = FakeAsyncEngine()

        with patch("utils.services.database.async_db_engine", engine):
            async with lifespan(app):
                pass

        assert engine.checkouts == DB_ASYNC_POOL_SIZE, (
            f"expected one checkout per pool slot ({DB_ASYNC_POOL_SIZE}); "
            f"got {engine.checkouts} — a sequential loop only ever warms "
            f"the one connection the pool hands back"
        )
        assert engine.statements == ["SELECT 1"] * DB_ASYNC_POOL_SIZE
        assert engine.live == 0, "every warmed connection must be released"

    async def test_checkouts_are_concurrent_so_distinct_connections_warm(self):
        """Holding all `pool_size` checkouts at once is what forces the pool
        to open distinct connections instead of recycling one."""
        from main import app, lifespan

        engine = FakeAsyncEngine(delay=0.005)

        with patch("utils.services.database.async_db_engine", engine):
            async with lifespan(app):
                pass

        assert engine.max_concurrent == DB_ASYNC_POOL_SIZE, (
            f"expected all {DB_ASYNC_POOL_SIZE} checkouts live at once; peak "
            f"was {engine.max_concurrent}"
        )

    async def test_warmup_stays_within_the_startup_budget(self):
        """AC: < 500ms added for 20 connections; the test budget is 5s.

        With 50ms of simulated per-connection latency, a sequential warm-up
        of 20 connections costs ~1s; concurrent costs ~50ms. The tight bound
        (half of sequential) is the regression guard with ~10x headroom for
        a loaded CI runner; the 5s bound is the stated AC.
        """
        from main import app, lifespan

        per_connection = 0.05
        engine = FakeAsyncEngine(delay=per_connection)

        started = time.perf_counter()
        with patch("utils.services.database.async_db_engine", engine):
            async with lifespan(app):
                elapsed = time.perf_counter() - started

        assert elapsed < 5.0, f"startup took {elapsed:.3f}s, budget is 5s"
        sequential = per_connection * DB_ASYNC_POOL_SIZE
        assert elapsed < sequential / 2, (
            f"startup took {elapsed:.3f}s — at least half of a sequential "
            f"warm-up ({sequential:.3f}s); the checkouts are not concurrent"
        )


class TestHealthGate:
    """`/v1/health` flips green only after the pre-warm completes."""

    async def test_startup_does_not_yield_until_warmup_finishes(self):
        """The warm-up runs before `yield`, so nothing is served until it
        completes — held open here by a gate the fake connections await.

        The MCP session manager is swapped for a no-op context: its real
        one is an anyio cancel scope, which cannot be entered in the
        startup task and exited from the test's task.
        """
        import main

        gate = asyncio.Event()
        engine = FakeAsyncEngine(gate=gate)
        yielded = asyncio.Event()
        finish = asyncio.Event()

        async def run_lifespan():
            async with main.lifespan(main.app):
                yielded.set()
                await finish.wait()

        with (
            patch("utils.services.database.async_db_engine", engine),
            patch.object(main, "mcp_app", _NoOpMcpApp),
        ):
            startup = asyncio.create_task(run_lifespan())
            for _ in range(10):
                await asyncio.sleep(0)

            assert not yielded.is_set(), (
                "the lifespan yielded while the pre-warm was still blocked — "
                "the app would serve requests against a cold pool"
            )
            assert engine.checkouts == DB_ASYNC_POOL_SIZE, (
                "all pool checkouts must be in flight before the yield"
            )

            gate.set()
            await asyncio.wait_for(yielded.wait(), timeout=5)
            assert engine.statements == ["SELECT 1"] * DB_ASYNC_POOL_SIZE

            finish.set()
            await asyncio.wait_for(startup, timeout=5)

    def test_health_shape_unchanged_and_pool_hot_before_first_request(self):
        """`/v1/health` keeps its shape, and by the time a request can reach
        it the whole pool is already warm."""
        from dependencies import get_async_database
        from main import app

        engine = FakeAsyncEngine()
        probe_db = MagicMock()
        probe_db.db = AsyncMock()

        app.dependency_overrides[get_async_database] = lambda: probe_db
        try:
            with (
                patch("utils.services.database.async_db_engine", engine),
                TestClient(app) as client,
            ):
                # TestClient.__enter__ completes startup — including the
                # pre-warm — before any request is dispatched.
                assert engine.statements == (
                    ["SELECT 1"] * DB_ASYNC_POOL_SIZE
                ), "the pool must be hot before /v1/health can be reached"
                response = client.get("/v1/health")
        finally:
            app.dependency_overrides.pop(get_async_database, None)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestStartupOrdering:
    """aam-1 pre-landed ordering — verified, not rewritten."""

    async def test_sync_unit_alias_prewarm_runs_before_async_warmup(self):
        from main import app, lifespan

        order: list[str] = []
        engine = FakeAsyncEngine()
        fake_db = MagicMock()
        fake_db.db = MagicMock()

        def record_sync(_session):
            order.append("sync")

        original_connect = engine.connect

        def recording_connect():
            order.append("async")
            return original_connect()

        engine.connect = recording_connect

        with (
            patch("utils.services.database.Database", return_value=fake_db),
            patch(
                "utils.services.units.reload_unit_alias_cache",
                side_effect=record_sync,
            ),
            patch("utils.services.database.async_db_engine", engine),
        ):
            async with lifespan(app):
                pass

        assert order[0] == "sync", (
            f"the sync unit-alias pre-warm must precede the async pool "
            f"warm-up; saw {order[:3]!r}"
        )
        assert order.count("async") == DB_ASYNC_POOL_SIZE

    async def test_shutdown_disposes_async_engine_before_sync_engine(self):
        from main import app, lifespan

        order: list[str] = []
        engine = FakeAsyncEngine(on_dispose=lambda: order.append("async"))
        sync_engine = MagicMock()
        sync_engine.dispose = MagicMock(
            side_effect=lambda: order.append("sync")
        )

        with (
            patch("utils.services.database.async_db_engine", engine),
            patch("utils.services.database.db_engine", sync_engine),
        ):
            async with lifespan(app):
                pass

        assert order == ["async", "sync"], (
            f"dispose must reverse startup order (async first, sync "
            f"second); got {order!r}"
        )


class TestWarmupIsBestEffort:
    """A DB blip at boot logs and continues — never a crash-loop."""

    async def test_partial_failure_is_logged_and_startup_continues(self, caplog):
        from main import app, lifespan

        engine = FakeAsyncEngine(fail_indices=(0, 3))
        served = False

        with (
            patch("utils.services.database.async_db_engine", engine),
            caplog.at_level(logging.ERROR, logger="main"),
        ):
            async with lifespan(app):
                served = True

        assert served, "a failed warm-up must not prevent the app starting"
        assert engine.checkouts == DB_ASYNC_POOL_SIZE, (
            "one refused connection must not abandon the other in-flight "
            "checkouts"
        )
        assert any(
            "Async engine warm-up failed" in rec.message
            for rec in caplog.records
        )
        # The traceback carries how many slots failed, plus the original
        # driver error as the chained cause — both needed to triage a boot
        # blip from CloudWatch.
        assert f"2/{DB_ASYNC_POOL_SIZE} pool connections" in caplog.text
        assert "connection 0 refused" in caplog.text

    async def test_missing_async_engine_is_a_no_op(self):
        """Worker-style deployments run without an async engine configured."""
        from main import app, lifespan

        with patch("utils.services.database.async_db_engine", None):
            async with lifespan(app):
                pass
        # Reaching here without raising is the assertion.

    async def test_engine_import_failure_is_swallowed(self, caplog):
        from main import app, lifespan

        failing_engine = MagicMock()
        failing_engine.connect = MagicMock(side_effect=RuntimeError("no pg"))
        failing_engine.dispose = AsyncMock(return_value=None)

        with (
            patch("utils.services.database.async_db_engine", failing_engine),
            caplog.at_level(logging.ERROR, logger="main"),
        ):
            async with lifespan(app):
                pass

        assert any(
            "Async engine warm-up failed" in rec.message
            for rec in caplog.records
        )


@pytest.mark.parametrize("pool_size", [1, 5])
async def test_pre_warm_follows_the_configured_pool_size(pool_size):
    """The loop bound is `DB_ASYNC_POOL_SIZE`, not a hard-coded 20."""
    import main

    engine = FakeAsyncEngine()

    with (
        patch("utils.constants.DB_ASYNC_POOL_SIZE", pool_size),
        patch("utils.services.database.async_db_engine", engine),
    ):
        async with main.lifespan(main.app):
            pass

    assert engine.checkouts == pool_size
