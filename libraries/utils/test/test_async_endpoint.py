"""Unit tests for AsyncEndpoint (aam-3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode


class _HappyPath(AsyncEndpoint):
    async def execute(self, echo: str = "hi"):
        return success({"echo": echo})


class _APIErrorPath(AsyncEndpoint):
    async def execute(self):
        raise APIException(
            status_code=400, detail="nope", code=ErrorCode.INVALID_REQUEST
        )


class _BoomPath(AsyncEndpoint):
    async def execute(self):
        raise RuntimeError("kaboom")


class _BadShapePath(AsyncEndpoint):
    async def execute(self):
        # Not a valid endpoint result dict.
        return "totally wrong"


async def test_async_run_success_returns_valid_result():
    ep = _HappyPath("hello")
    result = await ep.run()
    assert result["success"] is True
    assert result["data"] == {"echo": "hello"}


async def test_async_run_api_exception_returns_failure_result():
    ep = _APIErrorPath()
    result = await ep.run()
    assert result["success"] is False
    assert result["error_message"] == "nope"
    assert result["status"] == 400


async def test_async_run_unhandled_exception_logs_and_fails():
    ep = _BoomPath()
    with patch.object(_BoomPath, "_log_error_to_db_async", new_callable=AsyncMock) as logmock:
        result = await ep.run()
    assert result["success"] is False
    assert "kaboom" in result["error_message"]
    logmock.assert_awaited_once()


async def test_async_run_invalid_shape_raises_internal_error():
    ep = _BadShapePath()
    with patch.object(_BadShapePath, "_log_error_to_db_async", new_callable=AsyncMock):
        result = await ep.run()
    assert result["success"] is False
    # Inner APIException path — but wrapped in failure()
    assert result["status"] == 500


async def test_async_call_dispatches_to_run_and_renders():
    response = await _HappyPath.call("world")
    assert response.status_code == 200


async def test_async_execute_raises_when_not_overridden():
    class _Unimplemented(AsyncEndpoint):
        pass

    ep = _Unimplemented()
    with pytest.raises(NotImplementedError):
        await ep.execute()


async def test_log_error_to_db_async_dispatches_to_threadpool():
    """Verify the run_in_threadpool hop exists — the async path MUST
    never block the event loop on the sync error-log write."""
    ep = _BoomPath()
    with patch(
        "fastapi.concurrency.run_in_threadpool", new_callable=AsyncMock
    ) as tp:
        tp.return_value = None
        await ep._log_error_to_db_async(RuntimeError("x"))
    tp.assert_awaited_once()


async def test_log_error_to_db_async_swallows_threadpool_exceptions():
    """The writer must never break the response — even if the threadpool
    hop itself raises."""
    ep = _BoomPath()
    with patch(
        "fastapi.concurrency.run_in_threadpool",
        new_callable=AsyncMock,
        side_effect=RuntimeError("tp-boom"),
    ):
        # Should not raise
        await ep._log_error_to_db_async(RuntimeError("x"))
