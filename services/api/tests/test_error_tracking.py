"""Tests for ErrorTrackingMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def middleware():
    from middleware.error_tracking import ErrorTrackingMiddleware

    return ErrorTrackingMiddleware(app=MagicMock())


def _build_request(user=None):
    """Build a minimal request object with the attributes the middleware reads."""
    request = MagicMock()
    request.method = "GET"
    request.url.path = "/v1/test"
    request.state = MagicMock(spec=["request_id", "user"])
    request.state.request_id = "req-abc"
    if user is not None:
        request.state.user = user
    else:
        del request.state.user
    return request


class TestLogError:
    """Direct tests for _log_error (user_id extraction, error/no-error paths)."""

    @patch("middleware.error_tracking.Database")
    def test_log_error_with_user_on_request_state(
        self, mock_database_cls, middleware
    ):
        """User on request.state.user → user_id is captured on the ErrorLog."""
        user = MagicMock()
        user.id = "user-123"
        request = _build_request(user=user)

        mock_db = MagicMock()
        mock_database_cls.return_value = mock_db

        middleware._log_error(
            request=request,
            request_id="req-abc",
            error=ValueError("boom"),
            status_code=500,
        )

        mock_db.create.assert_called_once()
        error_log = mock_db.create.call_args.args[0]
        assert error_log.user_id == "user-123"
        assert error_log.error_type == "ValueError"
        assert error_log.error_message == "boom"
        assert error_log.status_code == 500
        mock_db.close.assert_called_once()

    @patch("middleware.error_tracking.Database")
    def test_log_error_without_user_on_request_state(
        self, mock_database_cls, middleware
    ):
        """No user on state → user_id is None and error=None branch sets HTTP500."""
        request = _build_request(user=None)

        mock_db = MagicMock()
        mock_database_cls.return_value = mock_db

        middleware._log_error(
            request=request,
            request_id="req-xyz",
            error=None,
            status_code=503,
        )

        error_log = mock_db.create.call_args.args[0]
        assert error_log.user_id is None
        assert error_log.error_type == "HTTP500"
        assert error_log.status_code == 503

    @patch("middleware.error_tracking.Database")
    def test_log_error_swallows_db_exceptions(
        self, mock_database_cls, middleware
    ):
        """Failures inside _log_error never propagate."""
        mock_database_cls.side_effect = RuntimeError("db down")
        request = _build_request(user=None)

        # Should not raise
        middleware._log_error(
            request=request,
            request_id="req-1",
            error=ValueError("oops"),
            status_code=500,
        )


class TestDispatchExceptionPath:
    """call_next raises → middleware logs + re-raises."""

    @pytest.mark.asyncio
    @patch("middleware.error_tracking.Database")
    async def test_unhandled_exception_is_logged_and_reraised(
        self, mock_database_cls, middleware
    ):
        request = _build_request(user=None)

        async def call_next(_req):
            raise ValueError("kaboom")

        mock_db = MagicMock()
        mock_database_cls.return_value = mock_db

        with pytest.raises(ValueError, match="kaboom"):
            await middleware.dispatch(request, call_next)

        # Logged via _log_error
        mock_db.create.assert_called_once()
        error_log = mock_db.create.call_args.args[0]
        assert error_log.error_type == "ValueError"
        assert error_log.status_code == 500


class TestDispatch500ResponsePath:
    """5xx response is logged."""

    @pytest.mark.asyncio
    @patch("middleware.error_tracking.Database")
    async def test_500_response_is_logged(
        self, mock_database_cls, middleware
    ):
        request = _build_request(user=None)
        response = MagicMock()
        response.status_code = 500

        async def call_next(_req):
            return response

        mock_db = MagicMock()
        mock_database_cls.return_value = mock_db

        result = await middleware.dispatch(request, call_next)
        assert result is response
        mock_db.create.assert_called_once()


class TestThreadpoolDispatch:
    """aam-22: both dispatch paths hand the sync write to run_in_threadpool."""

    @pytest.mark.asyncio
    async def test_exception_path_uses_threadpool(self, middleware):
        request = _build_request(user=None)

        async def call_next(_req):
            raise ValueError("kaboom")

        with patch(
            "middleware.error_tracking.run_in_threadpool", new_callable=AsyncMock
        ) as mock_rtp:
            with pytest.raises(ValueError, match="kaboom"):
                await middleware.dispatch(request, call_next)

        mock_rtp.assert_awaited_once()
        assert mock_rtp.await_args.args[0] == middleware._log_error
        assert mock_rtp.await_args.kwargs["status_code"] == 500
        assert isinstance(mock_rtp.await_args.kwargs["error"], ValueError)

    @pytest.mark.asyncio
    async def test_500_response_path_uses_threadpool(self, middleware):
        request = _build_request(user=None)
        response = MagicMock()
        response.status_code = 503

        async def call_next(_req):
            return response

        with patch(
            "middleware.error_tracking.run_in_threadpool", new_callable=AsyncMock
        ) as mock_rtp:
            result = await middleware.dispatch(request, call_next)

        assert result is response
        mock_rtp.assert_awaited_once()
        assert mock_rtp.await_args.args[0] == middleware._log_error
        assert mock_rtp.await_args.kwargs["status_code"] == 503
        assert mock_rtp.await_args.kwargs["error"] is None


class TestErrorLogSubPool:
    """aam-22: the write lands on the aam-3 error-log sub-pool, never the main pool."""

    @patch("middleware.error_tracking.Database")
    @patch("utils.services.database.ErrorLogSessionLocal")
    def test_uses_error_log_session(
        self, mock_session_local, mock_database_cls, middleware
    ):
        session = MagicMock()
        mock_session_local.return_value = session
        mock_database_cls.return_value = MagicMock()

        middleware._log_error(
            request=_build_request(user=None),
            request_id="req-1",
            error=ValueError("boom"),
            status_code=500,
        )

        mock_database_cls.assert_called_once_with(db=session)

    @patch("middleware.error_tracking.Database")
    def test_falls_back_to_default_pool_when_subpool_missing(
        self, mock_database_cls, middleware
    ):
        mock_database_cls.return_value = MagicMock()

        with patch("utils.services.database.ErrorLogSessionLocal", None):
            middleware._log_error(
                request=_build_request(user=None),
                request_id="req-1",
                error=None,
                status_code=500,
            )

        mock_database_cls.assert_called_once_with()

    @patch("utils.services.database.SessionLocal")
    @patch("utils.services.database.ErrorLogSessionLocal")
    def test_no_main_pool_checkout_during_write(
        self, mock_error_session_local, mock_main_session_local, middleware
    ):
        """Real Database + mocked session factories: the main-pool factory
        is never invoked during an error-log write."""
        session = MagicMock()
        mock_error_session_local.return_value = session

        middleware._log_error(
            request=_build_request(user=None),
            request_id="req-1",
            error=ValueError("boom"),
            status_code=500,
        )

        mock_main_session_local.assert_not_called()
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()
