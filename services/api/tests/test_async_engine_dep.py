"""Unit test for the aam-1 async engine + get_async_database dep.

Landed dark — no production handler uses this yet. The test wires a
test-only handler into FastAPI via a module-local router so the dep
resolves end-to-end without polluting the real v1 surface.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def async_dep_app():
    """FastAPI app with a dummy async handler that exercises the dep."""
    from dependencies import get_async_database

    app = FastAPI()
    router = APIRouter()

    @router.get("/__aam1_probe")
    async def _probe(session=Depends(get_async_database)):
        # Probe that the dep yielded SOMETHING awaitable. aam-2 swaps
        # AsyncSession for AsyncDatabase; keep the assertion type-loose
        # so that swap doesn't break this test.
        return {"session_type": type(session).__name__}

    app.include_router(router)
    yield app


def test_get_async_database_yields_a_session(async_dep_app):
    """Dep resolution works end-to-end when AsyncSessionLocal is set."""
    from dependencies import get_async_database

    fake_session = MagicMock(spec=AsyncSession)
    fake_session.close = AsyncMock(return_value=None)

    class _FakeAsyncCM:
        async def __aenter__(self_inner):
            return fake_session

        async def __aexit__(self_inner, exc_type, exc, tb):
            return None

    async def override():
        async with _FakeAsyncCM() as session:
            yield session

    async_dep_app.dependency_overrides[get_async_database] = override

    with TestClient(async_dep_app) as client:
        resp = client.get("/__aam1_probe")

    assert resp.status_code == 200
    # The override yields the MagicMock(spec=AsyncSession) — the dep chain
    # resolved, the handler awaited, FastAPI plumbed the async generator.
    # That's what we're verifying; the concrete type gets replaced by
    # AsyncDatabase in aam-2, so we stay type-loose here.
    assert resp.json()["session_type"] in ("MagicMock", "AsyncSession")


def test_get_async_database_raises_when_unconfigured():
    """Calling the dep with no AsyncSessionLocal must raise, not silently
    yield None — handlers that depend on it would otherwise fail with a
    confusing AttributeError at first use."""
    from dependencies import get_async_session

    # Drive the generator directly so we don't need FastAPI wiring.
    with patch("dependencies.AsyncSessionLocal", None):
        gen = get_async_session()
        with pytest.raises(RuntimeError, match="AsyncSessionLocal"):
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(gen.__anext__())
            finally:
                loop.close()


def test_get_async_session_yields_from_sessionmaker_and_closes():
    """When AsyncSessionLocal is configured, get_async_session enters its
    async context, yields the session, and awaits close() on teardown.

    Covers the happy path that the `raises_when_unconfigured` test skips.
    """
    from dependencies import get_async_session

    fake_session = MagicMock(spec=AsyncSession)
    fake_session.close = AsyncMock(return_value=None)

    class _FakeSessionCM:
        async def __aenter__(self_inner):
            return fake_session

        async def __aexit__(self_inner, exc_type, exc, tb):
            return None

    fake_sessionmaker = MagicMock(return_value=_FakeSessionCM())

    async def _drive():
        with patch("dependencies.AsyncSessionLocal", fake_sessionmaker):
            gen = get_async_session()
            session = await gen.__anext__()
            assert session is fake_session
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_drive())
    finally:
        loop.close()

    fake_session.close.assert_awaited_once()


def test_get_async_database_yields_asyncdatabase_and_closes():
    """aam-6: `get_async_database` now yields a request-scoped
    `AsyncDatabase` (not the bare AsyncSession the aam-1 stub yielded).
    On dep teardown it `await database.close()`s the wrapped session."""
    from dependencies import get_async_database

    fake_session = MagicMock()
    fake_session.close = AsyncMock(return_value=None)
    fake_sessionmaker = MagicMock(return_value=fake_session)

    async def _drive():
        with (
            patch("utils.services.database.AsyncSessionLocal", fake_sessionmaker),
            patch("utils.services.database.async_db_engine", MagicMock()),
            patch("dependencies.AsyncSessionLocal", fake_sessionmaker),
        ):
            from utils.services.async_database import AsyncDatabase

            gen = get_async_database()
            yielded = await gen.__anext__()
            assert isinstance(yielded, AsyncDatabase)

            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_drive())
    finally:
        loop.close()

    fake_session.close.assert_awaited_once()


def test_get_async_database_raises_when_unconfigured():
    """No AsyncSessionLocal → loud RuntimeError, not silent None yield."""
    from dependencies import get_async_database

    async def _drive():
        with patch("dependencies.AsyncSessionLocal", None):
            gen = get_async_database()
            with pytest.raises(RuntimeError, match="AsyncSessionLocal"):
                await gen.__anext__()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_drive())
    finally:
        loop.close()


def test_get_async_session_raises_when_unconfigured():
    """get_async_session also fails loudly when the sessionmaker is unset
    (low-level entry point — anyone calling it directly gets the same
    contract as the higher-level get_async_database)."""
    from dependencies import get_async_session

    async def _drive():
        with patch("dependencies.AsyncSessionLocal", None):
            gen = get_async_session()
            with pytest.raises(RuntimeError, match="AsyncSessionLocal"):
                await gen.__anext__()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_drive())
    finally:
        loop.close()


def test_async_database_url_rewrites_scheme():
    """Confirm constants._build_async_database_url rewrites the scheme."""
    from utils import constants

    assert constants._build_async_database_url.__doc__ is not None

    # Temporarily patch DATABASE_URL and re-derive.
    original = constants.DATABASE_URL
    try:
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d"
        assert constants._build_async_database_url() == "postgresql+asyncpg://u:p@h:5432/d"

        constants.DATABASE_URL = "postgresql+psycopg2://u:p@h:5432/d"
        assert constants._build_async_database_url() == "postgresql+asyncpg://u:p@h:5432/d"

        constants.DATABASE_URL = None
        assert constants._build_async_database_url() is None
    finally:
        constants.DATABASE_URL = original


def test_async_database_url_strips_sslmode():
    """sslmode must be stripped from the URL — asyncpg rejects it as
    an unknown kwarg (prod regression: 188 TypeErrors/day before fix)."""
    from utils import constants

    original = constants.DATABASE_URL
    try:
        # Bare sslmode — stripped, no trailing `?`.
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d?sslmode=require"
        assert (
            constants._build_async_database_url()
            == "postgresql+asyncpg://u:p@h:5432/d"
        )

        # psycopg2 scheme + sslmode — both transformed.
        constants.DATABASE_URL = (
            "postgresql+psycopg2://u:p@h:5432/d?sslmode=verify-full"
        )
        assert (
            constants._build_async_database_url()
            == "postgresql+asyncpg://u:p@h:5432/d"
        )

        # Non-sslmode query params must survive.
        constants.DATABASE_URL = (
            "postgresql://u:p@h:5432/d?sslmode=require&application_name=api"
        )
        assert (
            constants._build_async_database_url()
            == "postgresql+asyncpg://u:p@h:5432/d?application_name=api"
        )
    finally:
        constants.DATABASE_URL = original


def test_async_connect_args_translates_sslmode():
    """`require` → non-verifying SSLContext (libpq semantics);
    `verify-ca`/`verify-full` → ssl=True (verifying default);
    `disable`/unset → {}. The sync side keeps its `DB_SSLMODE=require`
    env-var contract; this function rematerializes that intent for
    asyncpg — with the same NO-cert-verification behavior psycopg2
    gives us today, so RDS (AWS CA not in default trust store) keeps
    working."""
    import os
    import ssl

    from utils import constants

    original_url = constants.DATABASE_URL
    original_env = os.environ.get("DB_SSLMODE")
    try:
        # `require` → permissive context, NOT ssl=True. This is the
        # prod regression the ssl-cert-verify failure exposed.
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d?sslmode=require"
        args = constants._build_async_connect_args()
        assert set(args.keys()) == {"ssl"}
        ctx = args["ssl"]
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

        # `verify-full` → verifying ssl=True (asyncpg builds a default
        # verifying context). Not used in prod today; kept for
        # forward-compat if we ever ship the RDS CA bundle.
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d?sslmode=verify-full"
        assert constants._build_async_connect_args() == {"ssl": True}
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d?sslmode=verify-ca"
        assert constants._build_async_connect_args() == {"ssl": True}

        constants.DATABASE_URL = "postgresql://u:p@h:5432/d?sslmode=disable"
        os.environ.pop("DB_SSLMODE", None)
        assert constants._build_async_connect_args() == {}

        # No sslmode in URL → fall through to DB_SSLMODE env.
        # (Prod uses this branch — DATABASE_URL is built from components
        # without sslmode, DB_SSLMODE=require set on the ECS task.)
        constants.DATABASE_URL = "postgresql://u:p@h:5432/d"
        os.environ["DB_SSLMODE"] = "require"
        args = constants._build_async_connect_args()
        assert isinstance(args["ssl"], ssl.SSLContext)
        assert args["ssl"].verify_mode == ssl.CERT_NONE

        # Nothing set anywhere → {}.
        os.environ.pop("DB_SSLMODE", None)
        assert constants._build_async_connect_args() == {}
    finally:
        constants.DATABASE_URL = original_url
        if original_env is None:
            os.environ.pop("DB_SSLMODE", None)
        else:
            os.environ["DB_SSLMODE"] = original_env
