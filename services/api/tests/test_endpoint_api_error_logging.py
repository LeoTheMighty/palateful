"""Tests for Endpoint / AsyncEndpoint 4xx audit logging.

Covers the prod-only write path added to surface which APIException
branch fired for a given 4xx — the observability gap flagged by the
2026-04-24 /audit triage of the 86-event `client:DioException` cluster
on `/v1/recipe-books/.../import`.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from utils.api.endpoint import (
    APIException,
    AsyncEndpoint,
    Endpoint,
    success,
)
from utils.classes.error_code import ErrorCode


class _ParamsA(BaseModel):
    source_type: str
    url: str | None = None


class _ParamsB(BaseModel):
    raw_text: str | None = None


class _Boom(Endpoint):
    """Synchronous endpoint that always raises a 400 APIException."""

    def execute(self, *args, **kwargs):
        raise APIException(
            status_code=400,
            detail="URL is required for url source type",
            code=ErrorCode.INVALID_REQUEST,
        )


class _Boom500(Endpoint):
    """Synchronous endpoint that raises a 500 APIException (not 4xx)."""

    def execute(self, *args, **kwargs):
        raise APIException(
            status_code=500,
            detail="boom",
            code=ErrorCode.INTERNAL_ERROR,
        )


class _Ok(Endpoint):
    """Happy-path endpoint — never raises."""

    def execute(self, *args, **kwargs):
        return success(data={"ok": True})


class _AsyncBoom(AsyncEndpoint):
    async def execute(self, *args, **kwargs):
        raise APIException(
            status_code=403,
            detail="nope",
            code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
        )


def _build_request():
    req = MagicMock()
    req.method = "POST"
    req.url.path = "/v1/recipe-books/abc/import"
    req.state.request_id = "req-abc"
    return req


class _FakeDb:
    """Captures the ErrorLog row the writer passes to `database.create`."""

    def __init__(self):
        self.created: list = []
        self.closed = False

    def create(self, model):
        self.created.append(model)
        return model

    def close(self):
        self.closed = True


@pytest.fixture
def fake_error_log_db(monkeypatch):
    """Patch the sub-pool ErrorLogSessionLocal and Database to our fake.

    Endpoint._log_api_error_to_db imports Database + ErrorLogSessionLocal
    from `utils.services.database` at call time, so we patch both
    references there.
    """
    from utils.services import database as db_module

    fake_db = _FakeDb()

    class _FakeDatabase:
        def __init__(self, db=None):
            self._backing = fake_db

        def create(self, model):
            return fake_db.create(model)

        def close(self):
            fake_db.close()

    # Drive the else-branch (no ErrorLogSessionLocal) or the main branch;
    # both must route through our fake. Simplest: force ErrorLogSessionLocal
    # to None so the fallback Database() constructor is the one called.
    monkeypatch.setattr(db_module, "ErrorLogSessionLocal", None)
    monkeypatch.setattr(db_module, "Database", _FakeDatabase)
    yield fake_db


@pytest.fixture
def prod_env(monkeypatch):
    """Flip ENVIRONMENT=prod for the duration of a test.

    `_log_api_error_to_db` imports ENVIRONMENT at call-time from
    `utils.constants`, so we patch the module attribute directly.
    """
    from utils import constants

    monkeypatch.setattr(constants, "ENVIRONMENT", "prod")
    yield


class TestLogApiErrorProd:
    """Prod: every 4xx APIException writes one error_logs row."""

    def test_writes_row_with_expected_columns(
        self, prod_env, fake_error_log_db
    ):
        params_a = _ParamsA(source_type="url")
        params_b = _ParamsB()  # nothing set — must not contribute body_keys
        request = _build_request()
        user = MagicMock()
        user.id = "user-123"

        response = _Boom.call(params_a, params_b, user=user, request=request)

        # Caller still sees the 400 envelope
        assert response.status_code == 400

        # Exactly one row written
        assert len(fake_error_log_db.created) == 1
        row = fake_error_log_db.created[0]
        assert row.service == "api"
        assert row.error_type == "APIException"
        assert row.status_code == 400
        assert row.error_code == ErrorCode.INVALID_REQUEST.value
        assert row.method == "POST"
        assert row.path == "/v1/recipe-books/abc/import"
        assert row.user_id == "user-123"
        assert row.request_id == "req-abc"
        assert row.error_message == "URL is required for url source type"

        # body_keys captures only Pydantic-set fields — source_type was
        # explicitly set, url was not. The empty ParamsB contributes
        # nothing. Crucially, the VALUE ("url") is never persisted.
        body_payload = json.loads(row.stack_trace)
        assert body_payload == {"body_keys": ["source_type"]}
        assert "url" not in row.stack_trace or "url" in {
            "source_type"
        } is False  # value sanity

        assert fake_error_log_db.closed

    def test_500_apiexception_is_not_4xx_logged(
        self, prod_env, fake_error_log_db
    ):
        """5xx APIExceptions must NOT be caught by the 4xx logger.

        They're handled by the Exception branch (generic 500 logger) or
        by the middleware — writing them twice would skew aggregate
        counts in `audit_errors.py`.
        """
        response = _Boom500.call(user=MagicMock(id="u"), request=_build_request())

        assert response.status_code == 500
        assert fake_error_log_db.created == []

    def test_no_body_keys_when_no_pydantic_args(
        self, prod_env, fake_error_log_db
    ):
        """stack_trace stays null when no BaseModel arg was passed."""
        response = _Boom(user=MagicMock(id="u"), request=_build_request()).run()
        assert response["status"] == 400
        row = fake_error_log_db.created[0]
        assert row.stack_trace is None

    def test_writer_swallows_db_failure(self, prod_env, monkeypatch):
        """Any exception from the writer must never fail the response.

        Matches the existing 5xx writer's contract — audit is
        best-effort; silence beats breaking prod traffic.
        """
        from utils.services import database as db_module

        class _ExplodingDatabase:
            def __init__(self, db=None):
                raise RuntimeError("error-log pool exhausted")

        monkeypatch.setattr(db_module, "ErrorLogSessionLocal", None)
        monkeypatch.setattr(db_module, "Database", _ExplodingDatabase)

        # No raise — caller still sees the 400 envelope.
        response = _Boom.call(user=MagicMock(id="u"), request=_build_request())
        assert response.status_code == 400


class TestLogApiErrorNonProd:
    """Non-prod env (test, dev): no 4xx rows written.

    The test suite runs thousands of 4xx assertions; mirroring each one
    into error_logs would pollute CI coverage traces and silently lose
    the env-gate regression.
    """

    def test_test_env_does_not_write(self, fake_error_log_db):
        # No prod_env fixture — default conftest sets ENVIRONMENT=test
        response = _Boom.call(
            _ParamsA(source_type="url"),
            user=MagicMock(id="u"),
            request=_build_request(),
        )
        assert response.status_code == 400
        assert fake_error_log_db.created == []


class TestAsyncLogApiError:
    """Async endpoints dispatch the sync writer onto a threadpool."""

    @pytest.mark.asyncio
    async def test_async_4xx_writes_row_in_prod(
        self, prod_env, fake_error_log_db
    ):
        response = await _AsyncBoom.call(
            _ParamsA(source_type="photo"),
            user=MagicMock(id="async-user"),
            request=_build_request(),
        )
        assert response.status_code == 403
        assert len(fake_error_log_db.created) == 1
        row = fake_error_log_db.created[0]
        assert row.status_code == 403
        assert row.error_code == ErrorCode.RECIPE_BOOK_ACCESS_DENIED.value
        assert row.user_id == "async-user"
        body_payload = json.loads(row.stack_trace)
        assert body_payload == {"body_keys": ["source_type"]}


class TestExtractBodyKeys:
    """Direct unit test for the body-keys helper — verifies the
    values-never-leak contract independent of the DB-write path."""

    def test_only_set_fields_are_collected(self):
        params = _ParamsA(source_type="url", url="https://example.com/path")
        ep = _Ok(params, user=None, request=None)
        keys = ep._extract_body_keys()
        assert keys == ["source_type", "url"]
        # Values NEVER leak — the returned list carries names only.
        assert "https://example.com/path" not in json.dumps(keys)

    def test_returns_none_when_no_pydantic_args(self):
        ep = _Ok(user=None, request=None)
        assert ep._extract_body_keys() is None

    def test_kwargs_pydantic_args_are_collected(self):
        params = _ParamsA(source_type="text")
        ep = _Ok(params=params, user=None, request=None)
        keys = ep._extract_body_keys()
        assert keys == ["source_type"]
