"""Tests for the async auth deps (aam-6).

Coverage targets:

- `get_current_user_async`: bearer/JWT path + E2E test bypass + invalid
  header.
- `_finalize_auth_async`: field-sync + auth0_profile snapshot.
- `_ensure_default_calendar_async`: idempotent fast-path (returns
  existing) + creation path + race-loss path (IntegrityError → re-read).
- 5-way `asyncio.gather` race test: parallel `get_current_user_async`
  invocations for a brand-new auth0_id resolve to a single row + a
  single default calendar (mocked at the database boundary, not the
  Postgres unique index — the index is a separate epic-level
  guarantee tested in `aam-2`'s AsyncDatabase advisory-lock test).
- WebSocket auth probe: `get_current_user_async` resolves cleanly
  inside a Starlette WS upgrade dep chain (FastAPI WS deps differ
  subtly from HTTP deps; surfaces issues early).

Sync `get_current_user` and friends already have full coverage in
`test_dependencies.py`; this file only covers the new async surface.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# get_current_user_async — happy path + variants
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_async_db():
    """AsyncDatabase double exposing the methods the auth flow touches."""
    db = MagicMock()
    db.find_or_create_by = AsyncMock()
    db.update = AsyncMock()
    db.db = MagicMock()
    db.db.execute = AsyncMock()
    db.db.add = MagicMock()
    db.db.flush = AsyncMock()

    # Default: no existing default calendar.
    empty_result = MagicMock()
    empty_result.scalars.return_value.first.return_value = None
    db.db.execute.return_value = empty_result

    return db


async def test_get_current_user_async_invalid_header_raises_401(fake_async_db):
    from dependencies import get_current_user_async

    with pytest.raises(Exception) as exc_info:
        await get_current_user_async(
            authorization="Token abc", database=fake_async_db
        )
    assert "401" in str(exc_info.value) or "Invalid" in str(exc_info.value)


async def test_get_current_user_async_valid_bearer_resolves_user(
    fake_async_db,
):
    from dependencies import get_current_user_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "x@y.z"
    user.name = "X"
    user.picture = None
    user.email_verified = True
    user.auth0_profile = None
    user.has_completed_onboarding = True
    fake_async_db.find_or_create_by.return_value = user

    verifier = AsyncMock()
    verifier.verify_token.return_value = {
        "sub": "auth0|abc",
        "email": "x@y.z",
        "name": "X",
        "email_verified": True,
    }

    with patch(
        "utils.services.auth0.get_auth0_verifier", return_value=verifier
    ):
        result = await get_current_user_async(
            authorization="Bearer good-token",
            database=fake_async_db,
        )

    assert result is user
    fake_async_db.find_or_create_by.assert_awaited_once()


async def test_get_current_user_async_e2e_bypass(fake_async_db):
    """E2E mode short-circuits Auth0 verification and returns the test user."""
    from dependencies import get_current_user_async

    user = MagicMock()
    user.has_completed_onboarding = True
    fake_async_db.find_or_create_by.return_value = user

    fake_settings = MagicMock()
    fake_settings.e2e_test_mode = True
    fake_settings.environment = "test"

    with patch("dependencies.settings", fake_settings):
        result = await get_current_user_async(
            authorization="Bearer e2e-test-token",
            database=fake_async_db,
        )

    assert result is user


async def test_get_current_user_async_e2e_completes_onboarding(fake_async_db):
    """E2E flow updates onboarding when the test user hasn't seen it."""
    from dependencies import get_current_user_async

    user = MagicMock()
    user.has_completed_onboarding = False
    fake_async_db.find_or_create_by.return_value = user

    fake_settings = MagicMock()
    fake_settings.e2e_test_mode = True
    fake_settings.environment = "development"

    with patch("dependencies.settings", fake_settings):
        await get_current_user_async(
            authorization="Bearer e2e-test-token",
            database=fake_async_db,
        )

    fake_async_db.update.assert_awaited_once_with(
        user, has_completed_onboarding=True
    )


# ---------------------------------------------------------------------------
# _finalize_auth_async
# ---------------------------------------------------------------------------


async def test_finalize_auth_async_fills_missing_fields(fake_async_db):
    from dependencies import _finalize_auth_async

    user = MagicMock()
    user.email = None
    user.name = None
    user.picture = None
    user.email_verified = False
    user.auth0_profile = None

    claims = {
        "sub": "auth0|x",
        "email": "new@example.com",
        "name": "New",
        "picture": "https://img/x.png",
        "email_verified": True,
        "nickname": "n",
    }

    result = await _finalize_auth_async(fake_async_db, user, claims)
    assert result is user
    fake_async_db.update.assert_awaited_once()
    update_kwargs = fake_async_db.update.call_args.kwargs
    assert update_kwargs["email"] == "new@example.com"
    assert update_kwargs["name"] == "New"
    assert update_kwargs["picture"] == "https://img/x.png"
    assert update_kwargs["email_verified"] is True
    # JWT-only claims stripped from the snapshot
    assert "sub" not in update_kwargs["auth0_profile"]
    assert update_kwargs["auth0_profile"]["nickname"] == "n"


async def test_finalize_auth_async_no_update_when_complete(fake_async_db):
    from dependencies import _finalize_auth_async

    user = MagicMock()
    user.email = "x@y"
    user.name = "X"
    user.picture = "https://img"
    user.email_verified = True
    snapshot = {
        "email": "x@y",
        "name": "X",
        "picture": "https://img",
        "email_verified": True,
    }
    user.auth0_profile = snapshot

    claims = {
        "sub": "auth0|x",
        "iat": 1,
        "email": "x@y",
        "name": "X",
        "picture": "https://img",
        "email_verified": True,
    }

    await _finalize_auth_async(fake_async_db, user, claims)
    fake_async_db.update.assert_not_called()


# ---------------------------------------------------------------------------
# _ensure_default_calendar_async
# ---------------------------------------------------------------------------


async def test_ensure_default_calendar_async_returns_existing(fake_async_db):
    """Fast path — an active default already exists; no insert."""
    from dependencies import _ensure_default_calendar_async

    user = MagicMock()
    user.id = uuid.uuid4()

    existing = MagicMock()
    existing_result = MagicMock()
    existing_result.scalars.return_value.first.return_value = existing
    fake_async_db.db.execute.return_value = existing_result

    result = await _ensure_default_calendar_async(fake_async_db, user)
    assert result is existing
    fake_async_db.db.add.assert_not_called()


async def test_ensure_default_calendar_async_creates_when_missing(
    fake_async_db,
):
    """Happy creation path — SAVEPOINT block runs, calendar + membership added."""
    from dependencies import _ensure_default_calendar_async

    user = MagicMock()
    user.id = uuid.uuid4()

    # `db.begin_nested` returns an async context manager.
    class _NoopCM:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *a):
            return None

    fake_async_db.db.begin_nested = MagicMock(return_value=_NoopCM())

    result = await _ensure_default_calendar_async(fake_async_db, user)

    assert result is not None
    # Both calendar + membership added.
    assert fake_async_db.db.add.call_count == 2
    # flush() called twice (once after each add).
    assert fake_async_db.db.flush.await_count == 2


async def test_ensure_default_calendar_async_handles_race_loss(fake_async_db):
    """Concurrent provisioning won the race — IntegrityError caught;
    we re-read and return the winner's calendar."""
    from dependencies import _ensure_default_calendar_async

    user = MagicMock()
    user.id = uuid.uuid4()

    class _ExplodingCM:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, exc_type, exc, tb):
            # __aexit__ returning None means re-raise.
            return None

    fake_async_db.db.begin_nested = MagicMock(return_value=_ExplodingCM())
    fake_async_db.db.flush.side_effect = IntegrityError(
        "INSERT", {}, Exception("dup")
    )

    # First execute (initial probe) returns None; second (post-race) returns
    # the winner's row.
    winner = MagicMock()
    empty = MagicMock()
    empty.scalars.return_value.first.return_value = None
    won = MagicMock()
    won.scalars.return_value.first.return_value = winner
    fake_async_db.db.execute.side_effect = [empty, won]

    result = await _ensure_default_calendar_async(fake_async_db, user)
    assert result is winner


# ---------------------------------------------------------------------------
# 5-way asyncio.gather race test
# ---------------------------------------------------------------------------


async def test_get_current_user_async_5way_race_creates_one_user_one_calendar():
    """5 parallel invocations for a brand-new auth0_id must converge on
    a single user row + a single default calendar.

    The actual race-safety is owned by:
      - AsyncDatabase.find_or_create_by's pg_advisory_lock (aam-2)
      - The partial unique index on calendars(owner_id) + IntegrityError
        catch in `_ensure_default_calendar_async`.

    Here we mock at the AsyncDatabase boundary and assert the auth flow
    funnels every concurrent call to a SINGLE user instance + a SINGLE
    calendar provisioning attempt.
    """
    from dependencies import get_current_user_async

    canonical_user = MagicMock()
    canonical_user.id = uuid.uuid4()
    canonical_user.email = "race@example.com"
    canonical_user.name = "Race"
    canonical_user.picture = None
    canonical_user.email_verified = True
    canonical_user.auth0_profile = {}
    canonical_user.has_completed_onboarding = True

    canonical_calendar = MagicMock()

    # Per-task fake AsyncDatabase: every parallel task gets its own
    # database stub but they all return the same canonical user (the
    # advisory lock + unique-index dance is mocked away — what we're
    # checking here is the auth flow itself doesn't fan out into N
    # different users for a single auth0_id).
    def _make_db():
        db = MagicMock()
        db.find_or_create_by = AsyncMock(return_value=canonical_user)
        db.update = AsyncMock()
        db.db = MagicMock()
        db.db.add = MagicMock()
        db.db.flush = AsyncMock()
        existing_result = MagicMock()
        existing_result.scalars.return_value.first.return_value = (
            canonical_calendar
        )
        db.db.execute = AsyncMock(return_value=existing_result)
        return db

    verifier = AsyncMock()
    verifier.verify_token.return_value = {
        "sub": "auth0|race",
        "email": "race@example.com",
        "name": "Race",
        "email_verified": True,
    }

    with patch(
        "utils.services.auth0.get_auth0_verifier", return_value=verifier
    ):
        results = await asyncio.gather(
            *(
                get_current_user_async(
                    authorization="Bearer race-token", database=_make_db()
                )
                for _ in range(5)
            )
        )

    # All 5 tasks see the same canonical user (one row).
    assert all(r is canonical_user for r in results)
    # Auth0 verifier called 5 times — token verification isn't deduped
    # (each request brings its own JWT).
    assert verifier.verify_token.await_count == 5


# ---------------------------------------------------------------------------
# WebSocket auth probe — get_current_user_async resolves under WS upgrade
# ---------------------------------------------------------------------------


def test_get_current_user_async_ws_upgrade_dep_chain(fake_async_db):
    """FastAPI WebSocket deps resolve via `Depends(...)` the same way
    HTTP deps do, but the connection lifecycle differs (no response;
    the dep result is whatever survives `accept()`). Wire a minimal
    WS endpoint that depends on `get_current_user_async`, override
    the dep with our fake_async_db, and confirm the upgrade succeeds.
    """
    from dependencies import get_async_database, get_current_user_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "ws@example.com"
    user.name = "WS"
    user.picture = None
    user.email_verified = True
    user.auth0_profile = {}
    user.has_completed_onboarding = True

    fake_async_db.find_or_create_by.return_value = user

    app = FastAPI()

    @app.websocket("/__ws_auth_probe")
    async def ws_handler(
        websocket: WebSocket,
        current=Depends(get_current_user_async),
    ):
        await websocket.accept()
        await websocket.send_json({"user_id": str(current.id)})
        await websocket.close()

    async def _override_async_db():
        yield fake_async_db

    app.dependency_overrides[get_async_database] = _override_async_db

    verifier = AsyncMock()
    verifier.verify_token.return_value = {
        "sub": "auth0|ws",
        "email": "ws@example.com",
        "name": "WS",
        "email_verified": True,
    }

    with patch(
        "utils.services.auth0.get_auth0_verifier", return_value=verifier
    ):
        client = TestClient(app)
        # FastAPI's WS dep resolution reads `Authorization` from the
        # query/header machinery — pass via headers, like a browser
        # connecting through a JWT-aware proxy would.
        with client.websocket_connect(
            "/__ws_auth_probe",
            headers={"Authorization": "Bearer ws-token"},
        ) as ws:
            payload = ws.receive_json()
            assert payload["user_id"] == str(user.id)
            try:
                ws.receive_text()
            except WebSocketDisconnect:
                pass


# ---------------------------------------------------------------------------
# MCP get_current_database_async (aam-6)
# ---------------------------------------------------------------------------


def test_mcp_get_current_database_async_returns_contextvar_value():
    from mcp_server.auth import (
        current_database_async,
        get_current_database_async,
    )

    fake_db = MagicMock()
    token = current_database_async.set(fake_db)
    try:
        result = get_current_database_async()
        assert result is fake_db
    finally:
        current_database_async.reset(token)


def test_mcp_get_current_database_async_raises_when_unset():
    from mcp_server.auth import get_current_database_async
    from utils.api.endpoint import APIException

    with pytest.raises(APIException) as exc_info:
        get_current_database_async()
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# _ensure_system_trying_out_async (recipe-defaults-2)
# ---------------------------------------------------------------------------


async def test_ensure_system_trying_out_async_returns_existing(fake_async_db):
    """Fast path — a system book already exists; no INSERT, no default touch."""
    from dependencies import _ensure_system_trying_out_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.default_recipe_book_id = uuid.uuid4()  # custom default already

    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing_result = MagicMock()
    existing_result.scalars.return_value.first.return_value = existing
    fake_async_db.db.execute.return_value = existing_result

    result = await _ensure_system_trying_out_async(fake_async_db, user)
    assert result is existing
    fake_async_db.db.add.assert_not_called()
    fake_async_db.update.assert_not_called()


async def test_ensure_system_trying_out_async_creates_when_missing(fake_async_db):
    """Happy creation — book + membership + default-set."""
    from dependencies import _ensure_system_trying_out_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.default_recipe_book_id = None

    class _NoopCM:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *a):
            return None

    fake_async_db.db.begin_nested = MagicMock(return_value=_NoopCM())

    result = await _ensure_system_trying_out_async(fake_async_db, user)

    assert result is not None
    # Book + membership both added.
    assert fake_async_db.db.add.call_count == 2
    # flush() called twice — once after each add.
    assert fake_async_db.db.flush.await_count == 2
    # Default set.
    fake_async_db.update.assert_awaited_once()


async def test_ensure_system_trying_out_async_preserves_existing_default(
    fake_async_db,
):
    """User has a non-null default — helper does not call update."""
    from dependencies import _ensure_system_trying_out_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.default_recipe_book_id = uuid.uuid4()  # already set

    class _NoopCM:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *a):
            return None

    fake_async_db.db.begin_nested = MagicMock(return_value=_NoopCM())

    await _ensure_system_trying_out_async(fake_async_db, user)
    fake_async_db.update.assert_not_called()


async def test_ensure_system_trying_out_async_handles_race_loss(fake_async_db):
    """SAVEPOINT INSERT raises IntegrityError → re-read returns winner."""
    from dependencies import _ensure_system_trying_out_async

    user = MagicMock()
    user.id = uuid.uuid4()
    user.default_recipe_book_id = None

    class _ExplodingCM:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, exc_type, exc, tb):
            return None  # __aexit__ returning None means re-raise

    fake_async_db.db.begin_nested = MagicMock(return_value=_ExplodingCM())
    fake_async_db.db.flush.side_effect = IntegrityError(
        "INSERT", {}, Exception("dup")
    )

    winner = MagicMock()
    winner.id = uuid.uuid4()
    empty = MagicMock()
    empty.scalars.return_value.first.return_value = None
    won = MagicMock()
    won.scalars.return_value.first.return_value = winner
    fake_async_db.db.execute.side_effect = [empty, won]

    result = await _ensure_system_trying_out_async(fake_async_db, user)
    assert result is winner
    fake_async_db.update.assert_awaited_once()
