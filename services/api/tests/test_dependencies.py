"""Tests for FastAPI dependency injection functions."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetDb:
    """Tests for get_db generator."""

    def test_get_db_yields_session_and_closes(self):
        """get_db yields a session and closes it in finally block."""
        with patch("dependencies.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            from dependencies import get_db

            gen = get_db()
            session = next(gen)
            assert session is mock_session

            # Exhaust the generator (triggers finally)
            with pytest.raises(StopIteration):
                next(gen)
            mock_session.close.assert_called_once()

    def test_get_db_closes_on_exception(self):
        """get_db closes the session even when an exception occurs."""
        with patch("dependencies.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            from dependencies import get_db

            gen = get_db()
            next(gen)
            # Simulate exception by throwing into the generator
            with pytest.raises(ValueError):
                gen.throw(ValueError("test error"))
            mock_session.close.assert_called_once()


class TestGetDatabase:
    """Tests for get_database generator."""

    def test_get_database_yields_database_and_closes(self):
        """get_database yields a Database instance and closes it."""
        with patch("dependencies.Database") as mock_database_cls:
            mock_database = MagicMock()
            mock_database_cls.return_value = mock_database

            from dependencies import get_database

            gen = get_database()
            database = next(gen)
            assert database is mock_database

            with pytest.raises(StopIteration):
                next(gen)
            mock_database.close.assert_called_once()


class TestGetCurrentUser:
    """Tests for get_current_user async dependency."""

    @pytest.mark.asyncio
    async def test_invalid_auth_header_raises_401(self):
        """Missing 'Bearer ' prefix raises 401."""
        from dependencies import get_current_user

        mock_database = MagicMock()

        with pytest.raises(Exception) as exc_info:
            await get_current_user(authorization="Token abc123", database=mock_database)
        assert "401" in str(exc_info.value) or "Invalid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_valid_bearer_token_returns_user(self):
        """Valid Bearer token is verified and user is returned."""
        from dependencies import get_current_user

        mock_database = MagicMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_database.find_or_create_by.return_value = mock_user

        mock_verifier = AsyncMock()
        mock_verifier.verify_token.return_value = {
            "sub": "auth0|123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": None,
            "email_verified": True,
        }

        with patch("utils.services.auth0.get_auth0_verifier", return_value=mock_verifier):
            user = await get_current_user(
                authorization="Bearer valid-token-123",
                database=mock_database,
            )

        assert user is mock_user
        mock_verifier.verify_token.assert_called_once_with("valid-token-123")
        mock_database.find_or_create_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_token_with_missing_email(self):
        """Token claims without email still work (email set to None)."""
        from dependencies import get_current_user

        mock_database = MagicMock()
        mock_user = MagicMock()
        mock_database.find_or_create_by.return_value = mock_user

        mock_verifier = AsyncMock()
        mock_verifier.verify_token.return_value = {
            "sub": "apple|456",
            "name": "Apple User",
        }

        with patch("utils.services.auth0.get_auth0_verifier", return_value=mock_verifier):
            user = await get_current_user(
                authorization="Bearer token-789",
                database=mock_database,
            )

        assert user is mock_user
        # Verify defaults applied for missing claims
        call_kwargs = mock_database.find_or_create_by.call_args
        defaults = call_kwargs.kwargs.get("defaults") or call_kwargs[1].get("defaults")
        assert defaults["email"] is None
        assert defaults["email_verified"] is False

    @pytest.mark.asyncio
    async def test_e2e_test_mode_bypass(self):
        """E2E test mode with correct token returns test user."""
        from dependencies import get_current_user

        mock_database = MagicMock()
        mock_user = MagicMock()
        mock_user.has_completed_onboarding = True
        mock_database.find_or_create_by.return_value = mock_user

        mock_settings = MagicMock()
        mock_settings.e2e_test_mode = True
        mock_settings.environment = "test"

        with patch("dependencies.settings", mock_settings):
            user = await get_current_user(
                authorization="Bearer e2e-test-token",
                database=mock_database,
            )

        assert user is mock_user

    @pytest.mark.asyncio
    async def test_e2e_test_mode_blocked_in_production(self):
        """E2E test mode is blocked when environment is production."""
        from dependencies import get_current_user

        mock_database = MagicMock()

        mock_settings = MagicMock()
        mock_settings.e2e_test_mode = True
        mock_settings.environment = "production"

        with patch("dependencies.settings", mock_settings), \
             patch("utils.services.auth0.get_auth0_verifier") as mock_verifier:
            mock_verifier.return_value = AsyncMock()
            mock_verifier.return_value.verify_token.return_value = {"sub": "auth0|x"}
            mock_database.find_or_create_by.return_value = MagicMock()
            # Should NOT use E2E bypass, should go through normal auth
            user = await get_current_user(
                authorization="Bearer e2e-test-token",
                database=mock_database,
            )
            # Verify Auth0 verifier was called (not bypassed)
            mock_verifier.return_value.verify_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_e2e_onboarding_update(self):
        """E2E test mode updates onboarding if not completed."""
        from dependencies import get_current_user

        mock_database = MagicMock()
        mock_user = MagicMock()
        mock_user.has_completed_onboarding = False
        mock_database.find_or_create_by.return_value = mock_user

        mock_settings = MagicMock()
        mock_settings.e2e_test_mode = True
        mock_settings.environment = "development"

        with patch("dependencies.settings", mock_settings):
            await get_current_user(
                authorization="Bearer e2e-test-token",
                database=mock_database,
            )

        mock_database.update.assert_called_once_with(mock_user, has_completed_onboarding=True)


class TestFinalizeAuth:
    """Tests for _finalize_auth helper that syncs Auth0 claims onto the user."""

    def test_fills_missing_fields_from_claims(self):
        from dependencies import _finalize_auth

        mock_database = MagicMock()
        user = MagicMock()
        user.email = None
        user.name = None
        user.picture = None
        user.email_verified = False
        user.auth0_profile = None

        claims = {
            "sub": "auth0|abc",
            "email": "new@example.com",
            "name": "New Name",
            "picture": "https://img/x.png",
            "email_verified": True,
            "nickname": "newnick",
        }

        result = _finalize_auth(mock_database, user, claims)
        assert result is user
        mock_database.update.assert_called_once()
        update_kwargs = mock_database.update.call_args.kwargs
        assert update_kwargs["email"] == "new@example.com"
        assert update_kwargs["name"] == "New Name"
        assert update_kwargs["picture"] == "https://img/x.png"
        assert update_kwargs["email_verified"] is True
        assert "auth0_profile" in update_kwargs
        assert update_kwargs["auth0_profile"]["nickname"] == "newnick"
        # JWT-only claims should be stripped from the snapshot
        assert "sub" not in update_kwargs["auth0_profile"]

    def test_no_updates_when_user_already_complete(self):
        from dependencies import _finalize_auth

        mock_database = MagicMock()
        user = MagicMock()
        user.email = "existing@example.com"
        user.name = "Existing"
        user.picture = "https://img/old.png"
        user.email_verified = True
        # auth0_profile snapshot must equal what _finalize_auth would build
        # (claims minus the JWT-only keys), or it'll trigger an update.
        snapshot = {
            "email": "existing@example.com",
            "name": "Existing",
            "picture": "https://img/old.png",
            "email_verified": True,
        }
        user.auth0_profile = snapshot

        claims = {
            "sub": "auth0|abc",
            "iat": 1,
            "email": "existing@example.com",
            "name": "Existing",
            "picture": "https://img/old.png",
            "email_verified": True,
        }

        _finalize_auth(mock_database, user, claims)
        mock_database.update.assert_not_called()


class TestRequireAdmin:
    """Tests for the `require_admin` dependency (cla-1b coverage fill)."""

    @pytest.mark.asyncio
    async def test_admin_user_passes_through(self):
        from dependencies import require_admin

        admin = MagicMock()
        admin.is_admin = True

        result = await require_admin(user=admin)
        assert result is admin

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        from dependencies import require_admin
        from utils.api.endpoint import APIException

        non_admin = MagicMock()
        non_admin.is_admin = False

        with pytest.raises(APIException) as exc_info:
            await require_admin(user=non_admin)
        assert exc_info.value.status_code == 403


class TestGetOptionalUser:
    """Tests for `get_optional_user` — powers anonymous ingest paths
    like `POST /v1/client-latencies` (cla-1b)."""

    @pytest.mark.asyncio
    async def test_missing_header_returns_none(self):
        from dependencies import get_optional_user

        result = await get_optional_user(
            authorization=None, database=MagicMock()
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_non_bearer_header_returns_none(self):
        from dependencies import get_optional_user

        result = await get_optional_user(
            authorization="Token abc", database=MagicMock()
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_bearer_returns_resolved_user(self):
        from dependencies import get_optional_user

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_database = MagicMock()
        mock_database.find_or_create_by.return_value = mock_user

        verifier = AsyncMock()
        verifier.verify_token.return_value = {
            "sub": "auth0|opt",
            "email": "opt@example.test",
        }

        with patch(
            "utils.services.auth0.get_auth0_verifier", return_value=verifier
        ):
            result = await get_optional_user(
                authorization="Bearer ok-token",
                database=mock_database,
            )

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_invalid_token_falls_back_to_none(self):
        """APIException from the inner `get_current_user` resolves
        to anonymous (None) rather than propagating 401."""
        from dependencies import get_optional_user
        from utils.api.endpoint import APIException
        from utils.classes.error_code import ErrorCode

        async def raising_get_current_user(**_):
            raise APIException(
                status_code=401,
                detail="bad token",
                code=ErrorCode.INVALID_TOKEN,
            )

        with patch(
            "dependencies.get_current_user",
            side_effect=raising_get_current_user,
        ):
            result = await get_optional_user(
                authorization="Bearer bogus",
                database=MagicMock(),
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_exception_falls_back_to_none(self):
        """Any non-APIException also fails open — telemetry ingest must
        never 500 because auth resolution blew up."""
        from dependencies import get_optional_user

        async def exploding_get_current_user(**_):
            raise RuntimeError("auth0 down")

        with patch(
            "dependencies.get_current_user",
            side_effect=exploding_get_current_user,
        ):
            result = await get_optional_user(
                authorization="Bearer anything",
                database=MagicMock(),
            )
        assert result is None


class TestEnsureDefaultCalendarDepCaching:
    """pbq-8 spike — verify FastAPI's `Depends` cache dedupes
    `_ensure_default_calendar` invocations within a single request.

    The concern: `_ensure_default_calendar` is called inside
    `get_current_user`, which is a FastAPI dependency used by every
    authed route. Routes typically depend on `get_current_user` via
    multiple parameters (handler arg + sub-dependencies). If those
    referenced the function separately, the `SELECT FROM calendars`
    inside `_ensure_default_calendar` would fire N times.

    FastAPI caches dependencies by callable identity within one
    request (the `use_cache=True` default on `Depends`), so the
    function runs exactly once regardless of how many parameters
    reference it. The spike's conclusion: no per-request cache is
    needed; this test is regression coverage only.
    """

    def test_dep_cache_dedupes_ensure_default_calendar(self):
        """Build a minimal FastAPI app whose route depends on
        `get_current_user` through TWO Depends entries. Spy the
        `_ensure_default_calendar` import and assert exactly **one**
        invocation per request.
        """
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        import dependencies as deps_module
        from dependencies import get_current_user, get_database

        call_count = {"n": 0}

        def spy_ensure(database, user):
            call_count["n"] += 1
            return None

        app = FastAPI()

        async def inner_dep(user=Depends(get_current_user)):
            return user

        @app.get("/spike")
        async def spike_route(
            primary=Depends(get_current_user),
            aliased=Depends(inner_dep),
        ):
            # Two Depends(get_current_user) references — one direct,
            # one via inner_dep. FastAPI's dep cache ensures both
            # resolve to the same cached `User` instance.
            assert primary is aliased
            return {"ok": True}

        # Stub Auth0 + DB so the real `get_current_user` can run to
        # completion. Return a fixed user for both "find_or_create_by"
        # and subsequent `_finalize_auth` calls.
        mock_database = MagicMock()
        fixed_user = MagicMock()
        fixed_user.id = uuid.uuid4()
        fixed_user.email = "spike@example.test"
        fixed_user.name = "Spike"
        fixed_user.picture = None
        fixed_user.email_verified = True
        fixed_user.auth0_profile = {}
        mock_database.find_or_create_by.return_value = fixed_user

        async def verify_token_stub(_token):
            return {"sub": "auth0|spike", "iat": 1}

        verifier = MagicMock()
        verifier.verify_token = AsyncMock(side_effect=verify_token_stub)

        def override_get_database():
            yield mock_database

        app.dependency_overrides[get_database] = override_get_database

        with patch.object(deps_module, "_ensure_default_calendar", spy_ensure):
            with patch(
                "utils.services.auth0.get_auth0_verifier", return_value=verifier
            ):
                client = TestClient(app)
                response = client.get(
                    "/spike",
                    headers={"Authorization": "Bearer stub-token"},
                )
                assert response.status_code == 200

        # HARD AC — FastAPI's Depends cache dedupes. Exactly one call
        # despite the route pulling `get_current_user` twice.
        assert call_count["n"] == 1, (
            f"Expected 1 invocation of `_ensure_default_calendar` per "
            f"request (FastAPI Depends cache dedupes), got "
            f"{call_count['n']}. If >1, the spike's assumption no "
            f"longer holds and an explicit request.state cache is "
            f"needed (see pbq-8 story)."
        )


class TestEnsureSystemTryingOut:
    """recipe-defaults-2 — sync helper that seeds a system Trying Out
    book on first authed request and sets the user's default."""

    def _make_database(self):
        from sqlalchemy.exc import IntegrityError

        database = MagicMock()
        database.db = MagicMock()
        database.db.query = MagicMock()
        database.db.flush = MagicMock()
        database.create = MagicMock()
        database.update = MagicMock()

        # begin_nested() is used as `with database.db.begin_nested(): ...`
        class _NoopCM:
            def __init__(self, raises=None):
                self._raises = raises

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                if self_inner._raises:
                    raise self_inner._raises
                return None

        database._NoopCM = _NoopCM
        database._IntegrityError = IntegrityError
        return database

    def test_ensure_system_trying_out_returns_existing(self):
        """Fast path — book already present; no INSERT, no default touch."""
        from dependencies import _ensure_system_trying_out

        database = self._make_database()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.default_recipe_book_id = uuid.uuid4()  # custom default already

        existing = MagicMock()
        existing.id = uuid.uuid4()
        # query(...).join(...).filter(...).first() chain returns `existing`.
        database.db.query.return_value.join.return_value.filter.return_value.first.return_value = existing

        result = _ensure_system_trying_out(database, user)
        assert result is existing
        database.create.assert_not_called()
        database.update.assert_not_called()

    def test_ensure_system_trying_out_creates_when_missing(self):
        """Happy creation — book + membership + default-set."""
        from dependencies import _ensure_system_trying_out

        database = self._make_database()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.default_recipe_book_id = None

        # First .first() returns None (miss); after create, the book has an id.
        database.db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        database.db.begin_nested = MagicMock(return_value=database._NoopCM())

        result = _ensure_system_trying_out(database, user)

        # Book + membership both created.
        assert database.create.call_count == 2
        # Default set (book got an id from the construction; mock retains it).
        assert database.update.call_count == 1
        update_call = database.update.call_args
        assert "default_recipe_book_id" in update_call.kwargs
        assert result is not None

    def test_ensure_system_trying_out_preserves_existing_default(self):
        """User has a non-null default — helper does not call update."""
        from dependencies import _ensure_system_trying_out

        database = self._make_database()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.default_recipe_book_id = uuid.uuid4()  # already set

        # Miss path so we exercise creation.
        database.db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        database.db.begin_nested = MagicMock(return_value=database._NoopCM())

        _ensure_system_trying_out(database, user)
        database.update.assert_not_called()

    def test_ensure_system_trying_out_handles_race_loss(self):
        """SAVEPOINT INSERT raises IntegrityError → re-read returns winner."""
        from dependencies import _ensure_system_trying_out

        database = self._make_database()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.default_recipe_book_id = None

        winner = MagicMock()
        winner.id = uuid.uuid4()
        # First .first() (initial probe) returns None; second (re-read) returns winner.
        first_mock = MagicMock(side_effect=[None, winner])
        database.db.query.return_value.join.return_value.filter.return_value.first = first_mock

        # Have begin_nested context manager raise IntegrityError on exit.
        integrity = database._IntegrityError("INSERT", {}, Exception("dup"))
        database.db.begin_nested = MagicMock(
            return_value=database._NoopCM(raises=integrity)
        )

        result = _ensure_system_trying_out(database, user)
        assert result is winner
        # default_recipe_book_id was None and winner exists → update once.
        database.update.assert_called_once()
