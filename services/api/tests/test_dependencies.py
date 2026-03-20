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
