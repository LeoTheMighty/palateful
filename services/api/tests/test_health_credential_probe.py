"""Credential-aware health probe — RED artifact for rsh102.

E-2 (P0), E-3 (P0) and E-4 (P1) — RED artifact for the credential-aware
health probe. Workstream: rotation-self-heal (plan 462355), Phase 2 (FR-2).

**Registered in `tools/red-artifacts.txt` (rshred1).** This file is
excluded from default pytest collection until rsh102 lands; run it with
`PYTEST_RUN_RED=1` or by naming it explicitly. Originally authored in
place as `test_health.py`, which replaced that file's three passing
tests and so took the shared `test` gate red on `main` — `services/api`
pins `fail_under = 100`, so the green baseline could not simply be
dropped. rshred1 split the two apart.

**rsh102's GREEN commit must reconcile the two files**, not just delete
the registry entry: `test_health.py::test_health_check` still asserts
the *old* body `{"status": "ok"}` and `test_health_check_db_failure`
still asserts the old blanket-503 behaviour. Both become wrong the
moment FR-2 ships. Fold them into this file and delete the baseline
duplicates.

Expectations (`_devx/workstreams/rotation-self-heal/expectations.md`):
  E-2 (:21-32)  a fresh connection refused with SQLSTATE 28P01/28000 SHALL
                return 503, so ECS replaces the task; the body identifies
                the failure as credential-related.
  E-3 (:34-46)  any *other* connection failure SHALL return 200 —
                replacing a task cannot fix connectivity, and mass
                replacement escalates a transient blip into an outage.
  E-4 (:48-58)  at most 1 fresh connection per probe interval regardless
                of probe rate.

**The seam is the connection attempt, not the verdict** (plan.md:202-214).
The router never sees a SQLSTATE, so these tests patch
`db_probe._connect_once` to raise real `sqlalchemy.exc.OperationalError`
instances carrying those codes. `is_auth_error` therefore executes for
real inside the API test and the whole classify → verdict → status chain
is exercised end to end. Mocking `cached_verdict_async` directly would
assert an enum-to-int mapping and would not satisfy the threshold.

The `orig` attached to each `OperationalError` is a stub rather than a
genuine psycopg2 error: `pgcode` is read-only on the C type, and
connect-time libpq errors commonly carry `pgcode is None` anyway
(plan.md:332-340). Classifying a **live** driver failure is Phase 2's
T2.3, in `libraries/utils` against docker-compose Postgres — not this
artifact.

Authored RED, before `utils.services.db_probe` and
`utils.services.db_credentials` exist. Expected first failure:
`ModuleNotFoundError` for those modules — the missing feature.
"""

import asyncio

import pytest
from sqlalchemy.exc import OperationalError


# ---------------------------------------------------------------------------
# Error fixtures at the connect seam
# ---------------------------------------------------------------------------


class StubDbapiError(Exception):
    """Stands in for the raw DBAPI error a connect attempt raises."""

    def __init__(self, message, sqlstate=None):
        super().__init__(message)
        self.pgcode = sqlstate
        self.sqlstate = sqlstate


def operational_error(message, sqlstate=None):
    """A real `sqlalchemy.exc.OperationalError` wrapping a stub `orig`."""
    return OperationalError(
        "SELECT 1", {}, StubDbapiError(message, sqlstate=sqlstate)
    )


AUTH_FAILURES = [
    pytest.param(
        operational_error(
            'password authentication failed for user "palateful"', "28P01"
        ),
        id="28P01-password-authentication-failed",
    ),
    pytest.param(
        operational_error("no password supplied", "28000"),
        id="28000-invalid-authorization",
    ),
]

NON_AUTH_FAILURES = [
    pytest.param(
        operational_error("connection to server timed out", "57P03"),
        id="timeout",
    ),
    pytest.param(
        operational_error("could not connect to server: Connection refused"),
        id="operational-error-without-sqlstate",
    ),
    pytest.param(
        OSError("[Errno 8] nodename nor servname provided, or not known"),
        id="dns-resolution-failure",
    ),
    pytest.param(
        RuntimeError("something nobody anticipated"),
        id="unclassified-exception",
    ),
]


@pytest.fixture
def db_probe():
    """Import the probe module under test.

    A fixture rather than a module-level import so a missing module fails
    the probe-dependent tests individually instead of erroring collection
    for the whole file (`test_readiness_check` has no stake in FR-2).
    """
    from utils.services import db_probe as module

    return module


@pytest.fixture(autouse=True)
def reset_probe_cache():
    """The verdict cache is process-global.

    `conftest.py`'s example, `test_main.py:46` and
    `test_async_client_fixture.py:15` all hit `/v1/health`; a leaked
    `AUTH_FAILED` verdict would make them order-dependent. Module-local
    here so the RED artifact is self-contained — **T2.6 promotes this to
    `services/api/tests/conftest.py`**, which is where it has to live for
    the rest of the suite to be protected.
    """
    try:
        from utils.services import db_probe
    except ImportError:
        yield
        return
    db_probe._reset_verdict_cache()
    yield
    db_probe._reset_verdict_cache()


@pytest.fixture
def failing_connect(monkeypatch, db_probe):
    """Make the probe's fresh-connection attempt raise `exc`."""

    def _install(exc):
        calls = []

        async def fake_connect_once():
            calls.append(1)
            raise exc

        monkeypatch.setattr(db_probe, "_connect_once", fake_connect_once)
        return calls

    return _install


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def test_health_check(client):
    """Happy path. The body gains a `db` field carrying the verdict name.

    This updates the previous exact-body assertion (`{"status": "ok"}`) —
    called out in plan.md:357-361 as a deliberate contract change.
    """
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "OK"}


def test_readiness_check(client):
    """Readiness stays a pure liveness signal — no DB probe."""
    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


# ---------------------------------------------------------------------------
# E-2 — stale credentials fail the health check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exc", AUTH_FAILURES)
def test_auth_failure_returns_503(client, failing_connect, exc):
    """A positively-identified auth failure is the *only* 503 trigger.

    ECS turns this into a task replacement, which is the whole self-heal
    mechanism for a rotated credential resolved at task start.
    """
    failing_connect(exc)

    response = client.get("/v1/health")

    assert response.status_code == 503, (
        f"{exc!r} carries an auth SQLSTATE and must fail the health check; "
        f"got {response.status_code} {response.json()!r}"
    )


@pytest.mark.parametrize("exc", AUTH_FAILURES)
def test_503_body_identifies_the_failure_as_credential_related(
    client, failing_connect, exc
):
    """E-2's second threshold clause (expectations.md:30-31).

    Today's body is `{"detail": "db unavailable"}`, which does not
    distinguish a rotation from a network blip — the ambiguity that made
    the incident take six days to read.
    """
    failing_connect(exc)

    body = client.get("/v1/health").json()

    assert body == {"detail": "db credentials invalid", "db": "AUTH_FAILED"}


def test_auth_failure_uses_a_fresh_connection_not_a_pooled_one(
    client, failing_connect
):
    """The regression that makes E-2 possible at all.

    The pre-FR-2 router probed a *pooled* connection via
    `Depends(get_async_database)`; pooled connections stay authenticated
    across a rotation, so the probe could never observe the failure. The
    handler must therefore no longer declare that dependency.
    """
    import inspect

    from routers.v1.health_router import health_check

    params = inspect.signature(health_check).parameters
    assert "database" not in params, (
        f"health_check still takes a pooled-connection dependency "
        f"({list(params)!r}) — it structurally cannot observe a rotation"
    )

    calls = failing_connect(AUTH_FAILURES[0].values[0])
    client.get("/v1/health")
    assert calls, "the handler must actually drive the fresh-connection probe"


# ---------------------------------------------------------------------------
# E-3 — transient failures must NOT fail the health check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exc", NON_AUTH_FAILURES)
def test_non_auth_failure_returns_200(client, failing_connect, exc):
    """Fail-open floor.

    Both services run `deployment_minimum_healthy_percent = 0`
    (`ecs/main.tf:371`, `:473`), so a 503 from every task at once drains
    the service completely. Replacing tasks cannot fix a timeout, a
    refused connection or DNS — it only escalates the blip.

    The `RuntimeError` case inverts the previous
    `test_health_check_db_failure`, which asserted 503. Deliberate
    behaviour change (plan.md:352-356).
    """
    failing_connect(exc)

    response = client.get("/v1/health")

    assert response.status_code == 200, (
        f"{exc!r} is not an auth failure and must fail open; got "
        f"{response.status_code} {response.json()!r}"
    )


@pytest.mark.parametrize("exc", NON_AUTH_FAILURES)
def test_non_auth_200_body_does_not_claim_credentials_are_bad(
    client, failing_connect, exc
):
    """The 200 body still reports what the probe saw — a degraded verdict
    is useful signal — but it must never be `AUTH_FAILED`, which is the
    value that drives replacement."""
    failing_connect(exc)

    body = client.get("/v1/health").json()

    assert body.get("db") not in (None, "", "AUTH_FAILED"), (
        f"expected a non-auth verdict name in the body; got {body!r}"
    )


# ---------------------------------------------------------------------------
# E-4 — the probe is rate-limited
# ---------------------------------------------------------------------------


def test_burst_of_probes_opens_one_connection(client, monkeypatch, db_probe):
    """Container (30s) and ALB (60s) checks both land here.

    Without a TTL every probe is a new connection and TLS handshake — and
    post-FR-5, a `get_secret_value` too.
    """
    calls = []

    async def counting_connect_once():
        calls.append(1)

    monkeypatch.setattr(db_probe, "_connect_once", counting_connect_once)

    for _ in range(10):
        assert client.get("/v1/health").status_code == 200

    assert len(calls) == 1, (
        f"10 probes inside one TTL must cost exactly 1 fresh connection; "
        f"got {len(calls)}"
    )


async def test_concurrent_misses_coalesce_onto_one_connection(monkeypatch, db_probe):
    """Single-flight, not merely cached.

    Two in-process checkers at 30s and 60s can both miss on the same tick.
    A plain TTL cache lets both connect; the cache must coalesce them onto
    one in-flight attempt or E-4's budget is blown in exactly the sliding
    window that matters.
    """
    calls = []
    release = asyncio.Event()

    async def slow_connect_once():
        calls.append(1)
        await release.wait()

    monkeypatch.setattr(db_probe, "_connect_once", slow_connect_once)

    probes = [asyncio.create_task(db_probe.cached_verdict_async()) for _ in range(8)]
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*probes)

    assert len(calls) == 1, (
        f"8 concurrent misses must coalesce onto 1 in-flight connection; "
        f"got {len(calls)}"
    )


async def test_interleaved_30s_and_60s_schedule_holds_the_budget(
    monkeypatch, db_probe
):
    """The case that actually tests the design.

    Simulates the real arrival pattern — container probe every 30s, ALB
    probe every 60s, the two coinciding on every other tick — across five
    minutes of virtual time. E-4's threshold is at most 1 fresh connection
    per 60s window, so 300s admits at most 6.
    """
    calls = []
    clock = {"t": 0.0}

    async def counting_connect_once():
        calls.append(clock["t"])

    monkeypatch.setattr(db_probe, "_connect_once", counting_connect_once)
    monkeypatch.setattr(db_probe, "_now", lambda: clock["t"])

    for tick in range(0, 301, 30):
        clock["t"] = float(tick)
        await db_probe.cached_verdict_async(ttl_s=60)
        if tick % 60 == 0:
            # ALB probe lands on the same instant as the container probe.
            await db_probe.cached_verdict_async(ttl_s=60)

    assert len(calls) <= 6, (
        f"300s at 1-per-60s admits at most 6 fresh connections; got "
        f"{len(calls)} at {calls!r}"
    )
    for earlier, later in zip(calls, calls[1:]):
        assert later - earlier >= 60, (
            f"two fresh connections {later - earlier}s apart breaches the "
            f"1-per-60s budget: {calls!r}"
        )


async def test_unset_database_url_is_ok_not_a_failure(monkeypatch, db_probe):
    """Nothing to authenticate against is not an auth failure.

    `utils.constants.ASYNC_DATABASE_URL` is `None` wherever the DB env is
    absent, and `database.py:79-80` already returns `(None, None)` there.
    Getting this wrong breaks `test_main.py:46` and
    `test_async_client_fixture.py:15` (plan.md:341-347).
    """
    monkeypatch.setattr(db_probe, "_probe_url", lambda: None)

    verdict = await db_probe.probe_async()

    assert verdict is db_probe.ProbeVerdict.OK, (
        f"an absent URL must classify OK, not a failure; got {verdict!r}"
    )
