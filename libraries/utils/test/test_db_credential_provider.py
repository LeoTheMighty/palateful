"""E-6 (P0) — RED artifact for connect-time credential resolution.

Workstream: rotation-self-heal (plan 462355), Phase 5 (FR-5a) and the
second-clause extension in Phase 6 (T6.3b).

Expectation (`_devx/workstreams/rotation-self-heal/expectations.md:74-87`):
    When a connection attempt fails authentication and a secret ARN is
    configured, the system SHALL invalidate its cached credential,
    re-resolve from Secrets Manager, and retry exactly once before
    surfacing the error.

Threshold, both clauses:
    Exactly 1 re-resolution and 1 retry per auth failure; the retried
    connection succeeds; with `DB_PASSWORD_SECRET_ARN` unset, 0 Secrets
    Manager calls occur and engine construction is unchanged.

Authored RED, before `SecretPasswordProvider` /
`resolve_password_provider` / `register_rotating_credentials` exist in
`utils/services/db_credentials.py`. The expected first failure is
`ModuleNotFoundError` / `AttributeError` for those names — the missing
feature, not a wiring error.

Two seams are pinned here, deliberately, because the implementation has
no other testable surface:

1. `db_credentials` imports `boto3` at module scope and constructs the
   Secrets Manager client *lazily* (plan.md:585-591 — putting it in
   `aws.py` would build it unconditionally and blow the zero-client
   clause). Tests spy on `db_credentials.boto3.client`, which is what
   makes "0 clients constructed" observable at all.
2. The `do_connect` listener is driven through `engine.pool._creator()`
   rather than `engine.connect()`. That closure is exactly the
   do_connect chain plus `dialect.connect` and nothing else;
   `engine.connect()` additionally fires `first_connect` →
   `dialect.initialize()`, which would run real SQL against the stubbed
   connection. A SQLite engine stands in for Postgres because neither
   psycopg2 nor asyncpg is pinned in `libraries/utils`
   (`pyproject.toml`) — the listener is dialect-agnostic, and the
   *classification* of a live psycopg2 auth failure is Phase 2's T2.3,
   not this artifact's job.
"""

from __future__ import annotations

import ast
import importlib
import logging
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:rds!db-abc123-AbCdEf"
)
OLD_PASSWORD = "old-password-that-just-got-rotated"
NEW_PASSWORD = "new-password-from-secrets-manager"

AGENT_ENGINE_SITES = (
    Path(__file__).resolve().parents[2] / "agent" / "agent" / "runner.py",
    Path(__file__).resolve().parents[2] / "agent" / "agent" / "tasks.py",
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubSecretsManager:
    """Records `get_secret_value` calls and serves a queue of passwords."""

    def __init__(self, passwords: list[str] | None = None, raises: Exception | None = None):
        self.calls: list[dict] = []
        self._passwords = list(passwords or [NEW_PASSWORD])
        self.raises = raises

    def get_secret_value(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        password = (
            self._passwords.pop(0) if len(self._passwords) > 1 else self._passwords[0]
        )
        return {"SecretString": '{"username": "palateful", "password": "%s"}' % password}


class FakeAuthError(Exception):
    """Stands in for a psycopg2 connect-time OperationalError.

    Carries *both* signals `is_auth_error` is contracted to match
    (plan.md:332-340): a SQLSTATE and the libpq message. Real
    connect-time errors often have `pgcode is None`, so a correct
    implementation must accept either — this fixture is deliberately
    generous so the test measures retry semantics, not classification.
    Classification against a live driver is Phase 2's T2.3.
    """

    def __init__(self, message='password authentication failed for user "palateful"'):
        super().__init__(message)
        self.pgcode = "28P01"
        self.sqlstate = "28P01"


class FakeTransientError(Exception):
    """A non-auth connect failure. Must propagate untouched."""

    def __init__(self, message="connection to server timed out"):
        super().__init__(message)
        self.pgcode = None
        self.sqlstate = None


@pytest.fixture
def db_credentials():
    """Import the module under test (fresh, so env reads are honoured)."""
    import utils.services.db_credentials as module

    return importlib.reload(module)


@pytest.fixture
def arn_set(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD_SECRET_ARN", SECRET_ARN)
    monkeypatch.setenv("DB_PASSWORD", OLD_PASSWORD)


@pytest.fixture
def arn_unset(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD_SECRET_ARN", raising=False)
    monkeypatch.setenv("DB_PASSWORD", OLD_PASSWORD)


@pytest.fixture
def boto_spy(monkeypatch, db_credentials):
    """Count Secrets Manager client constructions.

    Returns the list of `(service_name, kwargs)` tuples so a test can
    assert on both "how many" and "which service".
    """
    constructed: list[tuple] = []

    def fake_client(service_name, *args, **kwargs):
        constructed.append((service_name, kwargs))
        return StubSecretsManager()

    monkeypatch.setattr(db_credentials.boto3, "client", fake_client)
    return constructed


@pytest.fixture
def engine():
    """A driver-free engine to hang the `do_connect` listener on."""
    eng = create_engine("sqlite://", poolclass=NullPool)
    yield eng
    eng.dispose()


def drive_connect(engine):
    """Invoke exactly the pool creator closure.

    That closure is the do_connect chain followed by `dialect.connect`.
    Deliberately not `engine.connect()` / `engine.raw_connection()`,
    which also fire `first_connect` → `dialect.initialize()` and would
    execute PRAGMA statements against the stubbed connection.
    """
    return engine.pool._creator()


class RecordingConnect:
    """Stands in for `dialect.connect`, recording the password each call.

    `failures` is a queue consumed one entry per call: an exception
    instance is raised, `None` yields a successful connection.
    """

    def __init__(self, failures: list[Exception | None]):
        self.passwords: list[str | None] = []
        self._failures = list(failures)

    def __call__(self, *args, **kwargs):
        self.passwords.append(kwargs.get("password"))
        outcome = self._failures.pop(0) if self._failures else None
        if outcome is not None:
            raise outcome
        return object()


# ---------------------------------------------------------------------------
# Provider — TTL cache semantics (T5.2, T5.5)
# ---------------------------------------------------------------------------


def test_current_resolves_the_password_from_the_secret_json(db_credentials):
    client = StubSecretsManager(passwords=[NEW_PASSWORD])
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, client=client)

    assert provider.current() == NEW_PASSWORD
    assert len(client.calls) == 1
    assert client.calls[0].get("SecretId") == SECRET_ARN


def test_repeated_current_within_ttl_makes_no_additional_calls(db_credentials):
    client = StubSecretsManager()
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, ttl_s=300, client=client)

    for _ in range(5):
        provider.current()

    assert len(client.calls) == 1, (
        f"the credential is fetched on the connect path — 5 calls inside one "
        f"TTL must cost 1 get_secret_value, got {len(client.calls)}"
    )


def test_current_past_ttl_reresolves_exactly_once(db_credentials):
    client = StubSecretsManager()
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, ttl_s=0.01, client=client)

    provider.current()
    time.sleep(0.02)
    provider.current()
    provider.current()

    assert len(client.calls) == 2, (
        f"crossing the TTL once should cost exactly 1 extra fetch, then cache "
        f"again; got {len(client.calls)} calls"
    )


def test_invalidate_forces_exactly_one_reresolution(db_credentials):
    client = StubSecretsManager(passwords=[OLD_PASSWORD, NEW_PASSWORD])
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, ttl_s=300, client=client)

    assert provider.current() == OLD_PASSWORD
    provider.invalidate()
    assert provider.current() == NEW_PASSWORD
    assert len(client.calls) == 2


def test_first_resolution_may_fall_back_to_db_password_env(db_credentials, monkeypatch):
    """The fallback is legal on the *first* resolution only.

    It is what keeps a Secrets Manager outage at boot from being worse
    than today's behaviour. The retry path is covered separately by
    `test_secrets_manager_outage_on_retry_does_not_represent_stale_password`.
    """
    monkeypatch.setenv("DB_PASSWORD", OLD_PASSWORD)
    client = StubSecretsManager(raises=RuntimeError("secretsmanager unavailable"))
    provider = db_credentials.SecretPasswordProvider(SECRET_ARN, client=client)

    assert provider.current() == OLD_PASSWORD


# ---------------------------------------------------------------------------
# Registration — the unset-ARN no-op path (CAP-6, E-6 clause 2)
# ---------------------------------------------------------------------------


def test_resolve_password_provider_returns_none_when_arn_unset(
    db_credentials, arn_unset
):
    assert db_credentials.resolve_password_provider() is None


def test_register_is_a_total_noop_when_arn_unset(
    db_credentials, arn_unset, boto_spy, engine
):
    before = len(engine.dialect.dispatch.do_connect)

    result = db_credentials.register_rotating_credentials(engine)

    assert result is False, (
        "register_rotating_credentials must report that it did nothing, so "
        "the enumeration guard in Phase 6 can tell wired-but-inert from unwired"
    )
    assert boto_spy == [], (
        f"0 boto3 clients may be constructed when the ARN is unset — local, "
        f"docker-compose and CI must be byte-identical to today; got {boto_spy!r}"
    )
    assert len(engine.dialect.dispatch.do_connect) == before, (
        "0 do_connect listeners may be registered when the ARN is unset"
    )


def test_register_attaches_exactly_one_listener_when_arn_set(
    db_credentials, arn_set, boto_spy, engine
):
    before = len(engine.dialect.dispatch.do_connect)

    result = db_credentials.register_rotating_credentials(engine)

    assert result is True
    assert len(engine.dialect.dispatch.do_connect) == before + 1, (
        "exactly one listener — a second registration on the same engine "
        "would double the retry budget"
    )


# ---------------------------------------------------------------------------
# do_connect — the retry contract (E-6 clause 1)
# ---------------------------------------------------------------------------


def test_auth_failure_triggers_exactly_one_reresolution_and_one_retry(
    db_credentials, arn_set, monkeypatch, engine
):
    client = StubSecretsManager(passwords=[OLD_PASSWORD, NEW_PASSWORD])
    monkeypatch.setattr(
        db_credentials.boto3, "client", lambda *a, **kw: client
    )
    connect = RecordingConnect(failures=[FakeAuthError(), None])
    monkeypatch.setattr(engine.dialect, "connect", connect)

    assert db_credentials.register_rotating_credentials(engine) is True
    conn = drive_connect(engine)

    assert conn is not None, "the retried connection must succeed"
    assert connect.passwords == [OLD_PASSWORD, NEW_PASSWORD], (
        f"expected 1 attempt with the cached password then exactly 1 retry "
        f"with the re-resolved one; got {connect.passwords!r}"
    )
    assert len(client.calls) == 2, (
        f"exactly 1 re-resolution per auth failure (1 initial + 1 after "
        f"invalidate); got {len(client.calls)}"
    )


def test_second_consecutive_auth_failure_propagates(
    db_credentials, arn_set, monkeypatch, engine
):
    """One retry, not a loop.

    If Secrets Manager is serving a password the database also rejects,
    retrying forever turns a bad credential into a hung connect pool.
    """
    client = StubSecretsManager(passwords=[OLD_PASSWORD, NEW_PASSWORD])
    monkeypatch.setattr(db_credentials.boto3, "client", lambda *a, **kw: client)
    connect = RecordingConnect(failures=[FakeAuthError(), FakeAuthError()])
    monkeypatch.setattr(engine.dialect, "connect", connect)

    db_credentials.register_rotating_credentials(engine)

    with pytest.raises(FakeAuthError):
        drive_connect(engine)

    assert len(connect.passwords) == 2, (
        f"exactly 2 connect attempts — the second failure must surface, not "
        f"trigger a third; got {len(connect.passwords)}"
    )


def test_non_auth_exception_propagates_with_zero_reresolutions(
    db_credentials, arn_set, monkeypatch, engine
):
    client = StubSecretsManager(passwords=[OLD_PASSWORD])
    monkeypatch.setattr(db_credentials.boto3, "client", lambda *a, **kw: client)
    connect = RecordingConnect(failures=[FakeTransientError()])
    monkeypatch.setattr(engine.dialect, "connect", connect)

    db_credentials.register_rotating_credentials(engine)

    with pytest.raises(FakeTransientError):
        drive_connect(engine)

    assert len(connect.passwords) == 1, "a timeout must not be retried here"
    assert len(client.calls) == 1, (
        f"a non-auth failure must cause 0 re-resolutions (only the initial "
        f"resolve); got {len(client.calls)} get_secret_value calls"
    )


def test_secrets_manager_outage_on_retry_does_not_represent_stale_password(
    db_credentials, arn_set, monkeypatch, engine, caplog
):
    """The composed failure (plan.md:614-621).

    `.current()` falls back to `DB_PASSWORD` when resolution raises. On
    the *retry* path that hands back the very password the database just
    rejected — which makes a Secrets Manager outage indistinguishable
    from "no rotation occurred", the exact ambiguity that produced the
    six-day outage. The retry must surface distinguishably instead.
    """
    calls = {"n": 0}

    class OutageAfterFirstResolve:
        def __init__(self):
            self.calls: list[dict] = []

        def get_secret_value(self, **kwargs):
            self.calls.append(kwargs)
            calls["n"] += 1
            if calls["n"] == 1:
                return {"SecretString": '{"password": "%s"}' % OLD_PASSWORD}
            raise RuntimeError("secretsmanager unavailable")

    client = OutageAfterFirstResolve()
    monkeypatch.setattr(db_credentials.boto3, "client", lambda *a, **kw: client)
    connect = RecordingConnect(failures=[FakeAuthError(), None])
    monkeypatch.setattr(engine.dialect, "connect", connect)
    caplog.set_level(logging.ERROR)

    db_credentials.register_rotating_credentials(engine)

    with pytest.raises(Exception):
        drive_connect(engine)

    assert connect.passwords == [OLD_PASSWORD], (
        f"the retry must NOT re-present the known-bad password — that is "
        f"what makes an SM outage look like a healthy no-op; got "
        f"{connect.passwords!r}"
    )
    assert caplog.records, (
        "the SM-outage-during-retry case must be visible in logs; a silent "
        "fallback is the failure mode this contract exists to remove"
    )


# ---------------------------------------------------------------------------
# T6.3b — E-6's second clause, against the live engines
# ---------------------------------------------------------------------------


@pytest.fixture
def utils_database_with_sqlite_url(monkeypatch, tmp_path):
    """Reload `utils.services.database` against a real, driver-free URL.

    The module builds its engines at import time from
    `utils.constants.DATABASE_URL`. Pointing that at a file-backed SQLite
    database gives genuine `Engine` objects (QueuePool, so the
    pool_size/max_overflow kwargs apply) without pinning psycopg2 into
    `libraries/utils`. The async engine stays `None` here — asyncpg is
    not pinned either — which is why the assertion is written over
    "every engine the module actually built".
    """
    url = f"sqlite:///{tmp_path / 'probe.db'}"
    for var in ("DB_HOST", "DB_USERNAME", "DB_PASSWORD", "DB_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("DB_PASSWORD_SECRET_ARN", raising=False)
    monkeypatch.setenv("DATABASE_URL", url)

    import utils.constants as constants

    importlib.reload(constants)
    import utils.services.database as database

    yield importlib.reload(database)

    # Leave the process as we found it: many other tests import these.
    monkeypatch.undo()
    importlib.reload(constants)
    importlib.reload(database)


def test_real_engine_modules_are_inert_when_arn_unset(
    db_credentials, boto_spy, utils_database_with_sqlite_url
):
    """E-6 clause 2, proven where E-6 points.

    Phase 6 wires `register_rotating_credentials` into the three
    `database.py` engine sites. With `DB_PASSWORD_SECRET_ARN` unset the
    wiring must be completely inert: no Secrets Manager client, no
    listener on any engine that was actually constructed.
    """
    database = utils_database_with_sqlite_url

    engines = [
        (name, getattr(database, name, None))
        for name in ("db_engine", "async_db_engine", "error_log_engine")
    ]
    live = [(name, eng) for name, eng in engines if eng is not None]
    assert live, (
        "expected utils.services.database to build at least one engine from "
        "the SQLite URL; the fixture is not exercising the real module"
    )

    for name, eng in live:
        sync_engine = getattr(eng, "sync_engine", eng)
        assert len(sync_engine.dialect.dispatch.do_connect) == 0, (
            f"{name} registered a do_connect listener with "
            f"DB_PASSWORD_SECRET_ARN unset — engine construction must be "
            f"unchanged from today on local, docker-compose and CI"
        )

    assert boto_spy == [], (
        f"0 Secrets Manager clients may be constructed at import time with "
        f"the ARN unset; got {boto_spy!r}"
    )


def test_database_module_registers_all_three_of_its_engine_sites():
    """The other half of "inert": wired, but off.

    A module that never calls `register_rotating_credentials` also
    reports 0 listeners — so the zero-listener assertion above is only
    meaningful alongside proof the call sites exist. Source-level, because
    with the ARN unset there is by construction nothing at runtime to
    observe.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "utils"
        / "services"
        / "database.py"
    ).read_text()
    count = source.count("register_rotating_credentials")
    assert count >= 3, (
        f"expected all three long-lived engine sites in database.py "
        f"(db_engine, async engine, error_log_engine) to register; found "
        f"{count} reference(s)"
    )


@pytest.mark.parametrize("site", AGENT_ENGINE_SITES, ids=lambda p: p.name)
def test_agent_engine_sites_register_too(site):
    """`libraries/agent` is the easy miss (plan.md:681-687).

    `runner.py` and `tasks.py` each build their own engine, lazily,
    inside `_get_session_factory()` — so there is no import-time engine to
    inspect, and the package is not installed in the `libraries/utils`
    venv. Asserted at the source level here; Phase 6's T6.3 enumeration
    guard is what makes it run under the `agent` project's own test
    target.
    """
    assert site.exists(), f"{site} not found"
    tree = ast.parse(site.read_text(), filename=str(site))
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "register_rotating_credentials" in names, (
        f"{site.name} builds a long-lived engine but never registers rotating "
        f"credentials — after a rotation this engine keeps failing while the "
        f"rest of the fleet self-heals"
    )
