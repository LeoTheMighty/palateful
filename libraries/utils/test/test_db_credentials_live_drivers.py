"""T2.3 — `is_auth_error` against **live** driver failures.

Every other test of the classifier hands it a constructed exception. That
proves the traversal and the matching, but it cannot prove the thing the
story actually depends on: that a *real* psycopg2 and a *real* asyncpg
connect-time authentication failure carry signals this matcher reads. If
the real errors differ from the fixtures — different attribute, different
wording, SQLSTATE absent where we assumed present — the probe returns
`UNREACHABLE` during a genuine rotation, fails open, and the self-heal
never fires. That is the 2026-07-21 outage, again, with more code.

So this leg connects to a real Postgres with a deliberately wrong
password and asserts on whatever the driver really raises.

Requires a running Postgres (`docker compose up -d db`). Skipped, loudly,
when one is not reachable — `libraries/utils` pins neither driver
(`pyproject.toml`), so this cannot be part of the default unit run. The
skip is the reason `test_db_credentials_classifier.py` exists alongside
it: that file always runs; this one is the reality check.

    PALATEFUL_LIVE_DB_HOST / _PORT / _USER / _DB override the defaults.
"""

from __future__ import annotations

import os

import pytest
from utils.services.db_credentials import is_auth_error

HOST = os.environ.get("PALATEFUL_LIVE_DB_HOST", "localhost")
PORT = int(os.environ.get("PALATEFUL_LIVE_DB_PORT", "5432"))
USER = os.environ.get("PALATEFUL_LIVE_DB_USER", "postgres")
DBNAME = os.environ.get("PALATEFUL_LIVE_DB_NAME", "test")
GOOD_PASSWORD = os.environ.get("PALATEFUL_LIVE_DB_PASSWORD", "postgres")
WRONG_PASSWORD = "definitely-not-the-password-abc123"

psycopg2 = pytest.importorskip(
    "psycopg2", reason="psycopg2 is not pinned in libraries/utils"
)


def _server_is_up() -> bool:
    try:
        conn = psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=GOOD_PASSWORD,
            dbname=DBNAME,
            connect_timeout=3,
        )
    except Exception:
        return False
    conn.close()
    return True


pytestmark = pytest.mark.skipif(
    not _server_is_up(),
    reason=(
        f"no Postgres reachable at {HOST}:{PORT} as {USER}/{DBNAME} — "
        f"run `docker compose up -d db` to exercise the live-driver leg"
    ),
)


def test_psycopg2_auth_failure_is_classified(capsys):
    """A real libpq connect-time rejection."""
    with pytest.raises(psycopg2.OperationalError) as excinfo:
        psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=WRONG_PASSWORD,
            dbname=DBNAME,
            connect_timeout=5,
        )

    exc = excinfo.value
    with capsys.disabled():
        print(
            f"\n[T2.3] psycopg2: {type(exc).__name__} "
            f"pgcode={exc.pgcode!r} message={str(exc).strip()!r}"
        )

    assert is_auth_error(exc), (
        f"a live psycopg2 auth failure must classify as an auth error; "
        f"pgcode={exc.pgcode!r} message={str(exc)!r}"
    )


def test_psycopg2_wrong_database_is_not_an_auth_error():
    """The nearest-neighbour negative, from the same live server.

    Proves the classifier is reading credentials specifically and not
    just "any connect-time OperationalError from libpq".
    """
    with pytest.raises(psycopg2.OperationalError) as excinfo:
        psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=GOOD_PASSWORD,
            dbname="database-that-does-not-exist",
            connect_timeout=5,
        )

    assert is_auth_error(excinfo.value) is False


def test_psycopg2_connection_refused_is_not_an_auth_error():
    """A closed port on the same host — must fail open."""
    with pytest.raises(psycopg2.OperationalError) as excinfo:
        psycopg2.connect(
            host=HOST,
            port=1,
            user=USER,
            password=GOOD_PASSWORD,
            dbname=DBNAME,
            connect_timeout=5,
        )

    assert is_auth_error(excinfo.value) is False


async def test_asyncpg_auth_failure_is_classified(capsys):
    """The driver the probe itself uses.

    asyncpg raises `InvalidPasswordError` with `.sqlstate`, not
    `.pgcode` — the reason `_sqlstate_of` checks both.
    """
    asyncpg = pytest.importorskip(
        "asyncpg", reason="asyncpg is not pinned in libraries/utils"
    )

    with pytest.raises(Exception) as excinfo:
        await asyncpg.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=WRONG_PASSWORD,
            database=DBNAME,
            timeout=5,
        )

    exc = excinfo.value
    with capsys.disabled():
        print(
            f"\n[T2.3] asyncpg: {type(exc).__name__} "
            f"sqlstate={getattr(exc, 'sqlstate', None)!r} "
            f"message={str(exc).strip()!r}"
        )

    assert is_auth_error(exc), (
        f"a live asyncpg auth failure must classify as an auth error; "
        f"sqlstate={getattr(exc, 'sqlstate', None)!r} message={str(exc)!r}"
    )


async def test_asyncpg_wrong_database_is_not_an_auth_error():
    asyncpg = pytest.importorskip("asyncpg")

    with pytest.raises(Exception) as excinfo:
        await asyncpg.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=GOOD_PASSWORD,
            database="database-that-does-not-exist",
            timeout=5,
        )

    assert is_auth_error(excinfo.value) is False


async def test_the_probe_itself_reports_auth_failed_against_a_live_server(
    monkeypatch,
):
    """End-to-end: real connection, real driver error, real verdict.

    The closest thing to the production failure that can be run on a
    laptop — `probe_async` opening a genuinely fresh connection with a
    password the server rejects, exactly as a task holds a rotated one.
    """
    pytest.importorskip("asyncpg")

    from utils.services import db_probe
    from utils.services.db_probe import ProbeVerdict

    bad = f"postgresql+asyncpg://{USER}:{WRONG_PASSWORD}@{HOST}:{PORT}/{DBNAME}"
    monkeypatch.setattr(db_probe, "_probe_url", lambda: bad)

    assert await db_probe.probe_async() is ProbeVerdict.AUTH_FAILED


async def test_the_probe_reports_ok_against_a_live_server_with_good_creds(
    monkeypatch,
):
    """The other half — a working credential must not read as rotated."""
    pytest.importorskip("asyncpg")

    from utils.services import db_probe
    from utils.services.db_probe import ProbeVerdict

    good = f"postgresql+asyncpg://{USER}:{GOOD_PASSWORD}@{HOST}:{PORT}/{DBNAME}"
    monkeypatch.setattr(db_probe, "_probe_url", lambda: good)

    assert await db_probe.probe_async() is ProbeVerdict.OK


# ---------------------------------------------------------------------------
# selfheal1 — measured: what each driver does with NO password at all
# ---------------------------------------------------------------------------
#
# rsh102 admitted `no password supplied` as an auth message and selfheal1
# removes it, so the two drivers' real behaviour here is the evidence the
# whole story rests on. It was never measured; these two tests measure it.


def test_psycopg2_with_no_password_says_no_password_supplied(capsys):
    """libpq refuses before contacting the server — the client-side case.

    A restart re-reads the same empty value, so this must NOT classify as
    an auth failure (which would drive an ECS replacement).
    """
    from utils.services.db_credentials import is_missing_password

    with pytest.raises(psycopg2.OperationalError) as excinfo:
        psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            dbname=DBNAME,
            connect_timeout=5,
        )

    exc = excinfo.value
    with capsys.disabled():
        print(
            f"\n[selfheal1] psycopg2 no-password: {type(exc).__name__} "
            f"pgcode={exc.pgcode!r} message={str(exc).strip()!r}"
        )

    assert is_missing_password(exc), (
        f"psycopg2 must still be recognisable as the client-side case; "
        f"message={str(exc)!r}"
    )
    assert is_auth_error(exc) is False, (
        f"a task with no password to send must not drive a replacement; "
        f"message={str(exc)!r}"
    )


async def test_asyncpg_with_no_password_looks_exactly_like_a_rotation(capsys):
    """The measurement that forced the URL check.

    asyncpg does not refuse client-side: with no password it md5-hashes the
    empty string and sends it, so the *server* answers `28P01 password
    authentication failed` — byte-for-byte a rotated credential. `/v1/health`
    runs this driver, so the message signal cannot save it and
    `db_probe._url_password_is_blank` has to decide from the URL instead.
    """
    asyncpg = pytest.importorskip("asyncpg")

    from utils.services.db_credentials import is_missing_password

    with pytest.raises(Exception) as excinfo:
        await asyncpg.connect(
            host=HOST,
            port=PORT,
            user=USER,
            database=DBNAME,
            timeout=5,
        )

    exc = excinfo.value
    with capsys.disabled():
        print(
            f"\n[selfheal1] asyncpg no-password: {type(exc).__name__} "
            f"sqlstate={getattr(exc, 'sqlstate', None)!r} "
            f"message={str(exc).strip()!r}"
        )

    assert is_missing_password(exc) is False, (
        "if asyncpg ever starts saying 'no password supplied', the "
        "URL-based downgrade can be narrowed — but today it does not, and "
        "that is why the downgrade exists"
    )


async def test_the_probe_does_not_replace_a_task_whose_url_has_no_password(
    monkeypatch,
):
    """End-to-end against the live server, on the driver `/v1/health` uses.

    Without the URL check this is a 503 from every task at once, over a
    password the deployment never supplied.
    """
    pytest.importorskip("asyncpg")

    from utils.services import db_probe
    from utils.services.db_probe import ProbeVerdict

    passwordless = f"postgresql+asyncpg://{USER}@{HOST}:{PORT}/{DBNAME}"
    monkeypatch.setattr(db_probe, "_probe_url", lambda: passwordless)

    assert await db_probe.probe_async() is ProbeVerdict.UNREACHABLE
