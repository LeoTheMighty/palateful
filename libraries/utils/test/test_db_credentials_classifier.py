"""Unit tests for `is_auth_error` (rsh102, FR-2).

The classifier decides whether the health probe reports 503 — which ECS
turns into a task replacement — or fails open. A false negative delays
the self-heal by one rotation; a false positive drains a service whose
`deployment_minimum_healthy_percent` is 0. The asymmetry is why the
non-auth cases below are as dense as the auth ones.

Classification against a **live** driver (real psycopg2 and asyncpg
connect failures) is a separate leg — see
`test_db_credentials_live_drivers.py`, which needs a running Postgres.
These tests are driver-free by construction so the default suite stays
runnable with no services.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError
from utils.services.db_credentials import (
    AUTH_MESSAGE_PATTERNS,
    AUTH_SQLSTATES,
    MISSING_PASSWORD_PATTERN,
    _chain,
    _sqlstate_of,
    is_auth_error,
    is_missing_password,
)


class PsycopgLike(Exception):
    """psycopg2 surfaces SQLSTATE as `.pgcode`."""

    def __init__(self, message, pgcode=None):
        super().__init__(message)
        self.pgcode = pgcode


class AsyncpgLike(Exception):
    """asyncpg surfaces SQLSTATE as `.sqlstate`."""

    def __init__(self, message, sqlstate=None):
        super().__init__(message)
        self.sqlstate = sqlstate


def wrapped(orig):
    """What SQLAlchemy hands callers above the pool creator."""
    return OperationalError("SELECT 1", {}, orig)


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sqlstate", sorted(AUTH_SQLSTATES))
def test_pgcode_sqlstate_is_an_auth_error(sqlstate):
    assert is_auth_error(PsycopgLike("some opaque text", pgcode=sqlstate))


@pytest.mark.parametrize("sqlstate", sorted(AUTH_SQLSTATES))
def test_asyncpg_sqlstate_is_an_auth_error(sqlstate):
    assert is_auth_error(AsyncpgLike("some opaque text", sqlstate=sqlstate))


@pytest.mark.parametrize("pattern", AUTH_MESSAGE_PATTERNS)
def test_message_alone_is_sufficient(pattern):
    """The case that matters most in production.

    libpq raises connect-time errors without a `PGresult`, so `.pgcode`
    is commonly `None` — if the message signal were not independently
    sufficient, the probe would miss a real rotation.
    """
    assert is_auth_error(PsycopgLike(f"FATAL:  {pattern} for user X"))


def test_message_match_is_case_insensitive():
    assert is_auth_error(Exception("FATAL: PASSWORD AUTHENTICATION FAILED"))


def test_auth_error_found_through_sqlalchemy_orig():
    """The shape the probe sees: wrapped above the pool creator."""
    assert is_auth_error(wrapped(PsycopgLike("nope", pgcode="28P01")))


def test_auth_error_found_through_cause_chain():
    """`raise ... from exc` — the shape a re-raising caller produces."""
    inner = PsycopgLike("nope", pgcode="28P01")
    try:
        raise inner
    except PsycopgLike as exc:
        outer = RuntimeError("probe failed")
        outer.__cause__ = exc
    assert is_auth_error(outer)


def test_auth_error_found_through_context_chain():
    """Implicit chaining — raised *during* handling of the auth error."""
    try:
        raise PsycopgLike("nope", pgcode="28P01")
    except PsycopgLike:
        try:
            raise RuntimeError("cleanup also failed")
        except RuntimeError as exc:
            assert is_auth_error(exc)


def test_unwrapped_dbapi_error_matches_too():
    """rsh105's `do_connect` listener sees the raw DBAPI error.

    SQLAlchemy only wraps above the pool creator, so the same classifier
    call has to handle the bare error as well as the wrapped one.
    """
    assert is_auth_error(PsycopgLike("password authentication failed"))


# ---------------------------------------------------------------------------
# Negative cases — every one of these must fail open
# ---------------------------------------------------------------------------


def test_none_is_not_an_auth_error():
    assert is_auth_error(None) is False


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(PsycopgLike("connection timed out", pgcode="57P03"), id="timeout"),
        pytest.param(PsycopgLike("could not connect to server"), id="refused"),
        pytest.param(OSError("nodename nor servname provided"), id="dns"),
        pytest.param(RuntimeError("something nobody anticipated"), id="unclassified"),
        pytest.param(
            PsycopgLike("permission denied for table recipes", pgcode="42501"),
            id="authorization-not-authentication",
        ),
        pytest.param(
            PsycopgLike("database does not exist", pgcode="3D000"),
            id="missing-database",
        ),
        pytest.param(wrapped(PsycopgLike("deadlock detected", pgcode="40P01")), id="deadlock"),
    ],
)
def test_non_auth_failures_are_not_auth_errors(exc):
    assert is_auth_error(exc) is False


def test_a_hostname_containing_auth_words_does_not_match():
    """Guards the narrowness of the patterns.

    A loose matcher keyed on 'password' or 'auth' would classify this
    DNS failure as a credential failure and replace every task in the
    service over an unrelated outage.
    """
    exc = OSError(
        "could not translate host name "
        '"password-authentication.internal" to address'
    )
    assert is_auth_error(exc) is False


def test_class_28_beyond_the_known_code_does_not_match():
    """`AUTH_SQLSTATES` is one code, not the whole 28 class — on purpose."""
    assert is_auth_error(PsycopgLike("opaque", pgcode="28P02")) is False


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # selfheal1: was `True` under rsh102's AC. The client had no
        # password to send — the server never evaluated a credential, and a
        # replacement task reads the same empty value. Same shape as the
        # pg_hba case below, so the same answer.
        pytest.param(
            "fe_sendauth: no password supplied", False, id="client-had-no-password"
        ),
        pytest.param(
            'password authentication failed for user "app"',
            True,
            id="genuine-rejection",
        ),
        pytest.param(
            'no pg_hba.conf entry for host "10.0.3.17", user "app", '
            'database "palateful", SSL off',
            False,
            id="pg_hba-rejection",
        ),
        pytest.param('role "app" does not exist', False, id="missing-role"),
        pytest.param(
            'user "app" is not permitted to log in', False, id="login-denied"
        ),
    ],
)
def test_28000_is_admitted_only_when_the_message_says_credentials(
    message, expected
):
    """`28000` is the dangerous code, and this is the whole reason why.

    PostgreSQL's `ClientAuthentication()` raises
    `invalid_authorization_specification` for a pg_hba rejection and for
    a missing role as well as for a credential problem. None of those
    three is fixed by replacing the task: a restarted task re-reads the
    same config and fails identically. Treating them as auth failures
    means a 503 from every task on the same tick, and with
    `deployment_minimum_healthy_percent = 0` the service drains to zero
    and stays there — an outage manufactured out of a config error.

    The `SSL off` case is reachable from this repo's own configuration:
    `constants._build_async_connect_args()` returns `{}` whenever
    `sslmode`/`DB_SSLMODE` is unset, so against an RDS instance with
    `rds.force_ssl=1` every connect is rejected exactly this way.

    So `28000` is admitted on the message, never on the code alone.
    """
    assert is_auth_error(AsyncpgLike(message, sqlstate="28000")) is expected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_sqlstate_prefers_pgcode_then_sqlstate():
    both = PsycopgLike("x", pgcode="28P01")
    both.sqlstate = "57P03"
    assert _sqlstate_of(both) == "28P01"


def test_sqlstate_of_ignores_empty_and_non_string_values():
    assert _sqlstate_of(PsycopgLike("x", pgcode="")) is None
    assert _sqlstate_of(PsycopgLike("x", pgcode=28001)) is None
    assert _sqlstate_of(Exception("no attrs at all")) is None


def test_sqlstate_of_falls_through_to_asyncpg_attribute():
    assert _sqlstate_of(AsyncpgLike("x", sqlstate="28000")) == "28000"


def test_chain_terminates_on_a_cycle():
    """`__context__` can form a cycle during nested exception handling."""
    a = RuntimeError("a")
    b = RuntimeError("b")
    a.__context__ = b
    b.__context__ = a

    assert len(list(_chain(a))) == 2
    assert is_auth_error(a) is False


def test_chain_is_breadth_first_outermost_first():
    inner = PsycopgLike("inner", pgcode="28P01")
    outer = wrapped(inner)
    assert list(_chain(outer))[0] is outer


# ---------------------------------------------------------------------------
# `is_missing_password` (selfheal1)
# ---------------------------------------------------------------------------


def test_a_task_with_no_password_is_not_an_auth_failure():
    """An empty `DB_PASSWORD` must never drive a replacement.

    Driver-realistic shape: psycopg2 carries no SQLSTATE at connect time,
    asyncpg may carry `28000`. Neither may admit it.
    """
    for exc in (
        wrapped(PsycopgLike("fe_sendauth: no password supplied", pgcode=None)),
        AsyncpgLike("no password supplied", sqlstate="28000"),
    ):
        assert is_auth_error(exc) is False
        assert is_missing_password(exc) is True


def test_missing_password_is_not_an_auth_message_pattern():
    """Pins the disjointness: re-adding it would restore the drain."""
    assert not any(MISSING_PASSWORD_PATTERN in p for p in AUTH_MESSAGE_PATTERNS)


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(None, id="none"),
        pytest.param(
            AsyncpgLike('password authentication failed for user "app"'),
            id="real-rejection",
        ),
        pytest.param(OSError("connection refused"), id="network"),
    ],
)
def test_is_missing_password_is_narrow(exc):
    assert is_missing_password(exc) is False


def test_is_missing_password_walks_the_chain():
    try:
        try:
            raise PsycopgLike("fe_sendauth: no password supplied")
        except PsycopgLike as inner:
            raise RuntimeError("probe failed") from inner
    except RuntimeError as outer:
        assert is_missing_password(outer) is True
