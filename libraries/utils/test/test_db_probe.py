"""Unit tests for the fresh-connection probe (rsh102, FR-2).

The endpoint-level expectations (E-2/E-3/E-4) are asserted in
`services/api/tests/test_health_credential_probe.py`, against the real
router. This module covers the probe module's own surface — the seams,
the verdict mapping, the single-flight cache, the sync twin and the CLI
— without needing a database or an API app.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.exc import OperationalError
from utils.services import db_probe
from utils.services.db_probe import ProbeVerdict


@pytest.fixture(autouse=True)
def reset_cache():
    """The verdict cache is process-global — see `_reset_verdict_cache`."""
    db_probe._reset_verdict_cache()
    yield
    db_probe._reset_verdict_cache()


class FakeConn:
    def __init__(self, engine):
        self._engine = engine

    async def execute(self, statement):
        self._engine.statements.append(str(statement))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeEngine:
    """Enough of an AsyncEngine for `_connect_once`."""

    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.statements: list[str] = []
        self.disposed = 0

    def connect(self):
        if self.fail_with is not None:
            raise self.fail_with
        return FakeConn(self)

    async def dispose(self):
        self.disposed += 1


@pytest.fixture
def fake_engine(monkeypatch):
    """Intercept engine construction; hand back the engine that was built."""
    built = {}

    def _install(fail_with=None):
        engine = FakeEngine(fail_with=fail_with)

        def fake_create_async_engine(url, **kwargs):
            built["url"] = url
            built["kwargs"] = kwargs
            built["engine"] = engine
            return engine

        monkeypatch.setattr(
            db_probe, "create_async_engine", fake_create_async_engine
        )
        return built

    return _install


def auth_error():
    orig = Exception('password authentication failed for user "palateful"')
    orig.pgcode = "28P01"
    return OperationalError("SELECT 1", {}, orig)


# ---------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------


def test_now_is_monotonic():
    """Monotonic, not wall-clock: an NTP step must not age the cache."""
    first = db_probe._now()
    assert db_probe._now() >= first


def test_probe_url_reads_constants_at_call_time(monkeypatch):
    from utils import constants

    monkeypatch.setattr(constants, "ASYNC_DATABASE_URL", "postgresql+asyncpg://x/y")
    assert db_probe._probe_url() == "postgresql+asyncpg://x/y"

    monkeypatch.setattr(constants, "ASYNC_DATABASE_URL", None)
    assert db_probe._probe_url() is None


def test_ttl_default_prefers_the_environment(monkeypatch):
    monkeypatch.setenv("DB_PROBE_TTL_S", "12.5")
    assert db_probe._ttl_default() == 12.5


def test_ttl_default_falls_back_to_the_constant_when_unset(monkeypatch):
    from utils import constants

    monkeypatch.delenv("DB_PROBE_TTL_S", raising=False)
    monkeypatch.setattr(constants, "DB_PROBE_TTL_S", 33.0)
    assert db_probe._ttl_default() == 33.0


def test_ttl_default_ignores_a_non_numeric_environment_value(monkeypatch):
    """A typo in an env var must not crash the health endpoint."""
    from utils import constants

    monkeypatch.setenv("DB_PROBE_TTL_S", "not-a-number")
    monkeypatch.setattr(constants, "DB_PROBE_TTL_S", 60.0)
    assert db_probe._ttl_default() == 60.0


# ---------------------------------------------------------------------------
# `_connect_once`
# ---------------------------------------------------------------------------


async def test_connect_once_is_a_noop_without_a_url(monkeypatch, fake_engine):
    built = fake_engine()
    monkeypatch.setattr(db_probe, "_probe_url", lambda: None)

    await db_probe._connect_once()

    assert built == {}, "no engine should be built when there is nothing to probe"


async def test_connect_once_uses_nullpool_and_runs_select_1(
    monkeypatch, fake_engine
):
    """NullPool is the point of the whole story.

    A pooled connection stays authenticated across a rotation, so a probe
    that reuses one structurally cannot observe the failure.
    """
    from sqlalchemy.pool import NullPool

    built = fake_engine()
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")

    await db_probe._connect_once()

    assert built["kwargs"]["poolclass"] is NullPool
    assert built["engine"].statements == ["SELECT 1"]


async def test_connect_once_applies_a_connect_timeout(monkeypatch, fake_engine):
    """A probe that hangs is as bad as one that lies."""
    built = fake_engine()
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")

    await db_probe._connect_once()

    assert built["kwargs"]["connect_args"]["timeout"] == (
        db_probe.PROBE_CONNECT_TIMEOUT_S
    )


async def test_connect_once_preserves_configured_ssl_connect_args(
    monkeypatch, fake_engine
):
    """TLS intent from `ASYNC_DB_CONNECT_ARGS` must survive.

    Prod reaches RDS over TLS; dropping the ssl connect-arg here would
    make the probe negotiate differently from the real pool and could
    classify a working credential as unreachable.
    """
    from utils import constants

    built = fake_engine()
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")
    monkeypatch.setattr(constants, "ASYNC_DB_CONNECT_ARGS", {"ssl": True})

    await db_probe._connect_once()

    assert built["kwargs"]["connect_args"]["ssl"] is True


def test_connect_once_does_not_mutate_the_shared_connect_args(monkeypatch):
    """`setdefault` on the module-level dict would leak into the real pool."""
    from utils import constants

    monkeypatch.setattr(constants, "ASYNC_DB_CONNECT_ARGS", {"ssl": True})
    shared = constants.ASYNC_DB_CONNECT_ARGS

    asyncio.run(_connect_with_fake(monkeypatch))

    assert "timeout" not in shared


async def _connect_with_fake(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(db_probe, "create_async_engine", lambda url, **kw: engine)
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")
    await db_probe._connect_once()


async def test_connect_once_disposes_the_engine_even_on_failure(
    monkeypatch, fake_engine
):
    """One engine per probe, every 60s, for the life of the task."""
    built = fake_engine(fail_with=auth_error())
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")

    with pytest.raises(OperationalError):
        await db_probe._connect_once()

    assert built["engine"].disposed == 1


# ---------------------------------------------------------------------------
# Verdict mapping
# ---------------------------------------------------------------------------


async def test_probe_async_returns_ok_on_success(monkeypatch):
    async def ok():
        return None

    monkeypatch.setattr(db_probe, "_connect_once", ok)
    assert await db_probe.probe_async() is ProbeVerdict.OK


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        pytest.param(auth_error(), ProbeVerdict.AUTH_FAILED, id="auth"),
        pytest.param(
            OperationalError("SELECT 1", {}, Exception("timed out")),
            ProbeVerdict.UNREACHABLE,
            id="operational",
        ),
        pytest.param(OSError("dns"), ProbeVerdict.UNREACHABLE, id="oserror"),
        pytest.param(
            TimeoutError(), ProbeVerdict.UNREACHABLE, id="timeout"
        ),
        pytest.param(RuntimeError("???"), ProbeVerdict.UNKNOWN, id="unknown"),
    ],
)
async def test_probe_async_classifies(monkeypatch, exc, expected):
    async def boom():
        raise exc

    monkeypatch.setattr(db_probe, "_connect_once", boom)
    assert await db_probe.probe_async() is expected


async def test_probe_async_never_raises(monkeypatch):
    """The health handler has no exception path — the probe owes it a value."""

    async def boom():
        raise ValueError("anything at all")

    monkeypatch.setattr(db_probe, "_connect_once", boom)
    assert await db_probe.probe_async() is ProbeVerdict.UNKNOWN


def test_only_auth_failed_is_actionable():
    """Guards the fail-open invariant against a careless enum addition."""
    actionable = {v for v in ProbeVerdict if v is ProbeVerdict.AUTH_FAILED}
    assert actionable == {ProbeVerdict.AUTH_FAILED}


# ---------------------------------------------------------------------------
# Single-flight TTL cache
# ---------------------------------------------------------------------------


async def test_cached_verdict_reuses_within_the_ttl(monkeypatch):
    calls = []

    async def counting():
        calls.append(1)

    monkeypatch.setattr(db_probe, "_connect_once", counting)

    for _ in range(5):
        assert await db_probe.cached_verdict_async(ttl_s=60) is ProbeVerdict.OK
    assert len(calls) == 1


async def test_cached_verdict_reprobes_after_the_ttl(monkeypatch):
    calls = []
    clock = {"t": 0.0}

    async def counting():
        calls.append(clock["t"])

    monkeypatch.setattr(db_probe, "_connect_once", counting)
    monkeypatch.setattr(db_probe, "_now", lambda: clock["t"])

    await db_probe.cached_verdict_async(ttl_s=60)
    clock["t"] = 59.9
    await db_probe.cached_verdict_async(ttl_s=60)
    assert len(calls) == 1, "still inside the window"

    clock["t"] = 60.0
    await db_probe.cached_verdict_async(ttl_s=60)
    assert len(calls) == 2, "TTL boundary is exclusive — 60s old is stale"


async def test_concurrent_misses_coalesce(monkeypatch):
    """Single-flight, not merely cached."""
    calls = []
    release = asyncio.Event()

    async def slow():
        calls.append(1)
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow)

    tasks = [asyncio.create_task(db_probe.cached_verdict_async()) for _ in range(8)]
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*tasks)

    assert len(calls) == 1
    assert results == [ProbeVerdict.OK] * 8


async def test_ttl_defaults_to_the_configured_value(monkeypatch):
    seen = {}

    async def ok():
        return None

    monkeypatch.setattr(db_probe, "_connect_once", ok)
    monkeypatch.setattr(db_probe, "_ttl_default", lambda: seen.setdefault("n", 60.0))

    await db_probe.cached_verdict_async()
    assert seen["n"] == 60.0


async def test_reset_clears_a_cached_verdict(monkeypatch):
    calls = []

    async def counting():
        calls.append(1)

    monkeypatch.setattr(db_probe, "_connect_once", counting)

    await db_probe.cached_verdict_async(ttl_s=60)
    db_probe._reset_verdict_cache()
    await db_probe.cached_verdict_async(ttl_s=60)

    assert len(calls) == 2


async def test_reset_cancels_an_in_flight_probe(monkeypatch):
    """A reset abandons the shared probe rather than letting it publish.

    Teardown resets run between tests; a probe still in flight must not
    survive to write a verdict into the next test's cache.
    """
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow():
        started.set()
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow)

    caller = asyncio.create_task(db_probe.cached_verdict_async())
    await started.wait()

    inflight = db_probe._inflight
    assert inflight is not None

    db_probe._reset_verdict_cache()
    assert db_probe._inflight is None

    # The caller awaits the shared task, so abandoning it surfaces as
    # cancellation rather than a verdict — the endpoint's fail-open guard
    # is what turns that into a 200 rather than a 500.
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert inflight.cancelled()
    assert db_probe._cached is None


async def test_reset_is_safe_with_nothing_in_flight():
    db_probe._reset_verdict_cache()
    db_probe._reset_verdict_cache()
    assert db_probe._inflight is None


async def test_a_waiter_survives_its_own_cancellation(monkeypatch):
    """`shield` — one cancelled request must not kill the shared probe."""
    calls = []
    release = asyncio.Event()

    async def slow():
        calls.append(1)
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow)

    first = asyncio.create_task(db_probe.cached_verdict_async())
    await asyncio.sleep(0)
    second = asyncio.create_task(db_probe.cached_verdict_async())
    await asyncio.sleep(0)

    second.cancel()
    release.set()

    assert await first is ProbeVerdict.OK
    assert len(calls) == 1


async def test_cancelling_the_first_caller_does_not_poison_the_others(
    monkeypatch,
):
    """The probe is a task, not work owned by whoever happened to start it.

    An ALB check timing out at 3s cancels its handler, so the caller that
    started the probe being torn down mid-flight is the COMMON case, not
    a corner one. If the shared work died with it, the container check
    coalesced behind it would fail on the same tick — both checkers
    failing, with no credential failure anywhere.
    """
    calls = []
    release = asyncio.Event()

    async def slow():
        calls.append(1)
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow)

    first = asyncio.create_task(db_probe.cached_verdict_async())
    await asyncio.sleep(0)
    followers = [
        asyncio.create_task(db_probe.cached_verdict_async()) for _ in range(3)
    ]
    await asyncio.sleep(0)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    release.set()
    assert await asyncio.gather(*followers) == [ProbeVerdict.OK] * 3
    assert len(calls) == 1, "the shared probe must not have been restarted"


async def test_a_probe_outlives_every_caller_and_still_caches(monkeypatch):
    """Nobody left waiting is not a reason to throw the work away."""
    release = asyncio.Event()

    async def slow():
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow)

    only = asyncio.create_task(db_probe.cached_verdict_async())
    await asyncio.sleep(0)
    task = db_probe._inflight

    only.cancel()
    with pytest.raises(asyncio.CancelledError):
        await only

    release.set()
    assert await task is ProbeVerdict.OK
    assert db_probe._cached is not None
    assert db_probe._cached[1] is ProbeVerdict.OK


def test_a_task_from_a_dead_loop_is_ignored(monkeypatch):
    """Cross-loop guard.

    `utils/tasks/task.py` runs `asyncio.run` per Celery task, so a leaked
    `_inflight` from a finished loop is reachable the moment rsh107's
    worker health check calls this. Awaiting it would raise "attached to
    a different loop" on every subsequent call, forever.
    """
    release = asyncio.Event()

    async def hangs():
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", hangs)

    async def strand():
        caller = asyncio.create_task(db_probe.cached_verdict_async())
        await asyncio.sleep(0)
        caller.cancel()
        return db_probe._inflight

    stranded = asyncio.run(strand())
    assert stranded is not None
    db_probe._inflight = stranded  # survived its loop

    async def ok():
        return None

    monkeypatch.setattr(db_probe, "_connect_once", ok)
    assert asyncio.run(db_probe.cached_verdict_async()) is ProbeVerdict.OK


def test_a_finishing_probe_does_not_retire_a_newer_one():
    """`_clear_inflight` ownership check.

    Without it, an older probe settling blanks the slot a newer probe has
    already claimed; the next caller then sees an empty slot and opens a
    second concurrent connection, silently breaking the single-flight
    guarantee this module exists to provide. Reachable whenever a reset
    lands mid-flight and a fresh probe starts before the old one settles.

    Driven directly rather than through the scheduler: the interleaving
    that matters is "stale task's done-callback fires while a newer task
    owns the slot", and reproducing that by timing alone is a coin-flip
    on loop-turn ordering — the kind of test that passes for the wrong
    reason and then flakes.
    """
    stale = object()
    fresh = object()

    db_probe._inflight = fresh
    try:
        db_probe._clear_inflight(stale)
        assert db_probe._inflight is fresh, (
            "a settling stale probe must not retire the current one"
        )

        db_probe._clear_inflight(fresh)
        assert db_probe._inflight is None, "its owner must still retire it"
    finally:
        db_probe._inflight = None


# ---------------------------------------------------------------------------
# Sync twin + CLI
# ---------------------------------------------------------------------------


class FakeSyncConn:
    def __init__(self, engine):
        self._engine = engine

    def execute(self, statement):
        self._engine.statements.append(str(statement))

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeSyncEngine:
    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.statements: list[str] = []
        self.disposed = 0

    def connect(self):
        if self.fail_with is not None:
            raise self.fail_with
        return FakeSyncConn(self)

    def dispose(self):
        self.disposed += 1


@pytest.fixture
def fake_sync_engine(monkeypatch):
    import sqlalchemy

    def _install(fail_with=None):
        engine = FakeSyncEngine(fail_with=fail_with)
        monkeypatch.setattr(sqlalchemy, "create_engine", lambda url, **kw: engine)
        return engine

    return _install


def test_probe_sync_is_ok_without_a_url(monkeypatch):
    from utils import constants

    monkeypatch.setattr(constants, "DATABASE_URL", None)
    assert db_probe.probe_sync() is ProbeVerdict.OK


def test_probe_sync_uses_nullpool(monkeypatch):
    import sqlalchemy
    from sqlalchemy.pool import NullPool
    from utils import constants

    seen = {}
    engine = FakeSyncEngine()

    def fake_create_engine(url, **kwargs):
        seen.update(kwargs)
        return engine

    monkeypatch.setattr(constants, "DATABASE_URL", "postgresql://x/y")
    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)

    assert db_probe.probe_sync() is ProbeVerdict.OK
    assert seen["poolclass"] is NullPool
    assert engine.statements == ["SELECT 1"]


def test_probe_sync_classifies_and_disposes(monkeypatch, fake_sync_engine):
    from utils import constants

    monkeypatch.setattr(constants, "DATABASE_URL", "postgresql://x/y")
    engine = fake_sync_engine(fail_with=auth_error())

    assert db_probe.probe_sync() is ProbeVerdict.AUTH_FAILED
    assert engine.disposed == 1


def test_probe_sync_fails_open_on_a_transient_error(monkeypatch, fake_sync_engine):
    from utils import constants

    monkeypatch.setattr(constants, "DATABASE_URL", "postgresql://x/y")
    fake_sync_engine(fail_with=OSError("dns"))

    assert db_probe.probe_sync() is ProbeVerdict.UNREACHABLE


def test_cli_prints_the_verdict_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(db_probe, "probe_sync", lambda: ProbeVerdict.OK)
    assert db_probe.main([]) == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_cli_exits_nonzero_only_on_auth_failure(monkeypatch, capsys):
    monkeypatch.setattr(db_probe, "probe_sync", lambda: ProbeVerdict.AUTH_FAILED)
    assert db_probe.main([]) == 1
    assert capsys.readouterr().out.strip() == "AUTH_FAILED"


def test_cli_fails_open_like_the_endpoint(monkeypatch):
    """UNREACHABLE is exit 0 — the CLI mirrors the 200, not a crash."""
    monkeypatch.setattr(db_probe, "probe_sync", lambda: ProbeVerdict.UNREACHABLE)
    assert db_probe.main([]) == 0


def test_cli_async_flag_uses_the_async_path(monkeypatch, capsys):
    async def fake_probe_async():
        return ProbeVerdict.UNKNOWN

    monkeypatch.setattr(db_probe, "probe_async", fake_probe_async)
    monkeypatch.setattr(
        db_probe, "probe_sync", lambda: pytest.fail("should not be used")
    )

    assert db_probe.main(["--async"]) == 0
    assert capsys.readouterr().out.strip() == "UNKNOWN"


# ---------------------------------------------------------------------------
# Hardening added after adversarial review — each of these is a path where
# a bug would have turned a non-credential problem into a task replacement.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["abc", "", "   ", "60s", None, object()],
    ids=["text", "empty", "blank", "unit-suffix", "none", "not-a-number"],
)
def test_coerce_ttl_rejects_unusable_values(raw):
    assert db_probe._coerce_ttl(raw) is None


@pytest.mark.parametrize(
    "raw", ["inf", "-inf", "nan", "-5"], ids=["inf", "-inf", "nan", "negative"]
)
def test_coerce_ttl_rejects_the_dangerous_numbers(raw):
    """`inf` never expires the cache; `nan` never hits it.

    `inf` means the verdict observed at boot is served for the life of
    the task and a rotation is never detected — the 2026-07-21 outage,
    reintroduced by a config value. `nan` makes every comparison False,
    so every request opens a fresh connection. Neither reads as a typo.
    """
    assert db_probe._coerce_ttl(raw) is None


def test_coerce_ttl_accepts_a_plain_number():
    assert db_probe._coerce_ttl("12.5") == 12.5
    assert db_probe._coerce_ttl(" 60 ") == 60.0
    assert db_probe._coerce_ttl("0") == 0.0


def test_ttl_default_survives_a_garbage_constant(monkeypatch):
    from utils import constants

    monkeypatch.delenv("DB_PROBE_TTL_S", raising=False)
    monkeypatch.setattr(constants, "DB_PROBE_TTL_S", float("inf"))
    assert db_probe._ttl_default() == db_probe.DEFAULT_PROBE_TTL_S


async def test_probe_times_out_rather_than_hanging(monkeypatch):
    """The budget is TOTAL, not just the connect.

    A half-open TCP after an RDS failover completes the handshake and
    then hangs in `SELECT 1`. Without a total bound the shared task never
    resolves and every later caller coalesces onto it forever — every
    health request hangs for the life of the task.
    """

    async def hangs():
        await asyncio.Event().wait()

    monkeypatch.setattr(db_probe, "_connect_once", hangs)
    monkeypatch.setattr(db_probe, "PROBE_TOTAL_TIMEOUT_S", 0.01)

    assert await db_probe.probe_async() is ProbeVerdict.UNREACHABLE


def test_probe_budget_fits_inside_the_tightest_health_check():
    """Pins the constant to the infrastructure it has to satisfy.

    The ALB target group uses `timeout = 3` (terraform/modules/alb/main.tf).
    A probe budget at or above that means the fail-open 200 is never
    delivered on exactly the scenario fail-open exists for: the checker
    gives up first, and a timed-out check scores like a failed one.
    """
    assert db_probe.PROBE_TOTAL_TIMEOUT_S < 3.0
    assert db_probe.PROBE_CONNECT_TIMEOUT_S <= db_probe.PROBE_TOTAL_TIMEOUT_S


async def test_a_failing_dispose_does_not_mask_an_auth_error(monkeypatch):
    """An exception raised in `finally` REPLACES the one propagating out.

    A noisy dispose would turn a genuine credential failure into an
    unclassified one — verdict UNKNOWN, 200, rotation missed, no
    self-heal.
    """

    class ExplodingEngine(FakeEngine):
        async def dispose(self):
            raise RuntimeError("dispose blew up")

    engine = ExplodingEngine(fail_with=auth_error())
    monkeypatch.setattr(db_probe, "create_async_engine", lambda url, **kw: engine)
    monkeypatch.setattr(db_probe, "_probe_url", lambda: "postgresql+asyncpg://x/y")

    assert await db_probe.probe_async() is ProbeVerdict.AUTH_FAILED


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(RuntimeError("__str__ raises"), id="str-raises"),
        pytest.param(ValueError("attribute raises"), id="attr-raises"),
    ],
)
async def test_a_classifier_exception_fails_open(monkeypatch, exc):
    """A classifier bug must not escape and become a 500.

    The container health check runs `urllib.request.urlopen`, which
    raises `HTTPError` on ANY non-2xx — so a 500 replaces the task
    exactly as hard as a 503, with no credential failure anywhere.
    """

    def exploding_is_auth_error(_exc):
        raise exc

    monkeypatch.setattr(db_probe, "is_auth_error", exploding_is_auth_error)

    async def boom():
        raise OSError("something ordinary")

    monkeypatch.setattr(db_probe, "_connect_once", boom)

    assert await db_probe.probe_async() is ProbeVerdict.UNKNOWN


def test_probe_sync_classifies_a_malformed_url(monkeypatch):
    """`create_engine` is inside the try, matching the async twin.

    Raising here would also give the CLI exit code 1, which it documents
    as AUTH_FAILED — during an incident an operator reads exit 1 and
    concludes the credentials rotated when the URL is merely malformed.
    """
    from utils import constants

    monkeypatch.setattr(constants, "DATABASE_URL", "not a url at all")
    assert db_probe.probe_sync() is ProbeVerdict.UNKNOWN


def test_probe_sync_survives_a_failing_dispose(monkeypatch):
    import sqlalchemy
    from utils import constants

    class ExplodingSyncEngine(FakeSyncEngine):
        def dispose(self):
            raise RuntimeError("dispose blew up")

    monkeypatch.setattr(constants, "DATABASE_URL", "postgresql://x/y")
    monkeypatch.setattr(
        sqlalchemy, "create_engine", lambda url, **kw: ExplodingSyncEngine()
    )
    assert db_probe.probe_sync() is ProbeVerdict.OK


def test_probe_sync_never_passes_libpq_a_zero_timeout(monkeypatch):
    """libpq reads `connect_timeout=0` as *wait indefinitely*.

    So a sub-second budget must round UP to 1, never truncate to 0 —
    the truncation is silent and turns the bound into its opposite.
    """
    import sqlalchemy
    from utils import constants

    seen = {}
    monkeypatch.setattr(constants, "DATABASE_URL", "postgresql://x/y")
    monkeypatch.setattr(db_probe, "PROBE_CONNECT_TIMEOUT_S", 0.5)

    def fake_create_engine(url, **kwargs):
        seen.update(kwargs)
        return FakeSyncEngine()

    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)

    db_probe.probe_sync()
    assert seen["connect_args"]["connect_timeout"] >= 1
