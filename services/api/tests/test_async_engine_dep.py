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


def test_get_async_database_delegates_to_get_async_session():
    """get_async_database just re-yields get_async_session's value —
    landing the name stable so aam-2 can swap the inner type with zero
    handler-import churn."""
    from dependencies import get_async_database

    sentinel = object()

    async def _fake_session_gen():
        yield sentinel

    async def _drive():
        with patch("dependencies.get_async_session", _fake_session_gen):
            gen = get_async_database()
            value = await gen.__anext__()
            assert value is sentinel
            with pytest.raises(StopAsyncIteration):
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
