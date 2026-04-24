"""Unit tests for `notify_via_threadpool` (aam-foundations-notify-threadpool-helper).

The bridge lets an `AsyncEndpoint` fan out to any existing sync
notification helper that takes `database: Database`, while keeping the
event loop unblocked (sync body runs on the threadpool) and guaranteeing
the sync session is closed even if the helper raises. Failures are
swallowed and written to `error_logs` with `service='push_notifications'`
so they remain triage-able via `bin/prod-logs` / `audit_errors.py`.

Every behaviour here is a property callers will rely on when adopting
the helper in D-01..D-13 — don't weaken any of them without also
updating aam-phase1-dev-snippets.md § 3.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils.services.notifications_bridge import notify_via_threadpool


_DEFAULT = object()


def _patch_sessions(*, session_local=_DEFAULT, error_log_session_local=_DEFAULT):
    """Patch SessionLocal + ErrorLogSessionLocal on the database module.

    Passing `None` explicitly is a valid value (simulating a worker/script
    environment where the session factory wasn't wired). Callers that
    don't pass the arg get a fresh MagicMock so `X()` returns a callable
    mock session.
    """
    sl = MagicMock(name="SessionLocal") if session_local is _DEFAULT else session_local
    els = (
        MagicMock(name="ErrorLogSessionLocal")
        if error_log_session_local is _DEFAULT
        else error_log_session_local
    )
    return (
        patch("utils.services.database.SessionLocal", sl),
        patch("utils.services.database.ErrorLogSessionLocal", els),
        sl,
        els,
    )


class _FakeDatabase:
    """Captures construction + close order so tests can assert lifecycle."""

    instances: list["_FakeDatabase"] = []

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        self.closed = False
        self.created: list = []
        type(self).instances.append(self)

    def create(self, obj):
        self.created.append(obj)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_database():
    _FakeDatabase.instances = []
    yield
    _FakeDatabase.instances = []


async def test_happy_path_injects_database_kwarg():
    sl_patch, els_patch, sl, _ = _patch_sessions()
    captured: dict = {}

    def fake_helper(*, database, user_id: str):
        captured["database"] = database
        captured["user_id"] = user_id

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        result = await notify_via_threadpool(fake_helper, user_id="u-1")

    assert result is None
    assert captured["user_id"] == "u-1"
    assert isinstance(captured["database"], _FakeDatabase)
    # Session built from the sync SessionLocal (not the error_log one).
    assert captured["database"].init_kwargs["db"] is sl.return_value


async def test_session_closed_on_success():
    sl_patch, els_patch, _, _ = _patch_sessions()

    def fake_helper(*, database):
        pass

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    # Exactly one Database was built (for the fn call) and it was closed.
    assert len(_FakeDatabase.instances) == 1
    assert _FakeDatabase.instances[0].closed is True


async def test_session_closed_on_exception_and_no_reraise():
    sl_patch, els_patch, _, _ = _patch_sessions()

    def fake_helper(*, database):
        raise RuntimeError("notify blew up")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        # Must NOT re-raise.
        result = await notify_via_threadpool(fake_helper)

    assert result is None
    # The fn's Database is the first one; it must be closed.
    assert _FakeDatabase.instances[0].closed is True


async def test_exception_logs_error_row_with_push_service():
    sl_patch, els_patch, _, _ = _patch_sessions()

    def fake_helper(*, database, target):
        raise ValueError(f"bad recipient {target}")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper, target="t-1")

    # Two Database instances: [0] the fn session, [1] the error-log session.
    assert len(_FakeDatabase.instances) == 2
    error_db = _FakeDatabase.instances[1]
    assert len(error_db.created) == 1
    row = error_db.created[0]
    assert row.service == "push_notifications"
    assert row.error_type == "ValueError"
    assert "fake_helper" in row.error_message
    assert "bad recipient" in row.error_message
    assert error_db.closed is True


async def test_reserved_database_kwarg_raises_typeerror():
    with pytest.raises(TypeError, match="reserves the `database` kwarg"):
        await notify_via_threadpool(lambda **_: None, database="anything")


async def test_error_log_uses_error_log_engine_when_available():
    sl_patch, els_patch, _, els = _patch_sessions()

    def fake_helper(*, database):
        raise RuntimeError("boom")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    # Error-log session was constructed from ErrorLogSessionLocal (the sub-pool).
    error_db = _FakeDatabase.instances[1]
    assert error_db.init_kwargs["db"] is els.return_value


async def test_error_log_falls_back_to_default_engine_when_sub_pool_missing():
    # ErrorLogSessionLocal is None (workers / scripts mode).
    sl_patch, els_patch, _, _ = _patch_sessions(error_log_session_local=None)

    def fake_helper(*, database):
        raise RuntimeError("boom")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    # Error-log Database was built with NO kwargs (uses default engine).
    error_db = _FakeDatabase.instances[1]
    assert error_db.init_kwargs == {}
    assert error_db.init_args == ()


async def test_session_local_missing_logs_runtime_error():
    # SessionLocal itself is None → helper must not call fn and must still log.
    sl_patch, els_patch, _, _ = _patch_sessions(session_local=None)

    calls = []

    def fake_helper(*, database):
        calls.append(database)

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    assert calls == []  # fn never called
    # Only one Database built — the error-log one.
    assert len(_FakeDatabase.instances) == 1
    row = _FakeDatabase.instances[0].created[0]
    assert row.service == "push_notifications"
    assert row.error_type == "RuntimeError"
    assert "SessionLocal" in row.error_message


async def test_error_log_write_failure_is_swallowed():
    sl_patch, els_patch, _, _ = _patch_sessions()

    class _ExplodingDatabase(_FakeDatabase):
        """First instance (the fn session) behaves normally; the second
        (error-log) raises on create() so we can assert the outer failure
        is swallowed."""

        def create(self, obj):
            if len(type(self).instances) >= 2:
                raise RuntimeError("db write failure")
            super().create(obj)

    def fake_helper(*, database):
        raise ValueError("primary failure")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _ExplodingDatabase),
    ):
        # Must return cleanly despite BOTH the helper AND the error-log write failing.
        result = await notify_via_threadpool(fake_helper)

    assert result is None


async def test_positional_args_forwarded():
    """Regression — helpers using positional args (not all sync helpers
    are keyword-first) still compose with notify_via_threadpool."""
    sl_patch, els_patch, _, _ = _patch_sessions()
    captured = {}

    def fake_helper(recipe_book_id, *, database, invited_by=None):
        captured["recipe_book_id"] = recipe_book_id
        captured["invited_by"] = invited_by

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper, "rb-42", invited_by="user-9")

    assert captured == {"recipe_book_id": "rb-42", "invited_by": "user-9"}


async def test_session_construction_failure_is_swallowed():
    """Review fix: if `Database(db=SessionLocal())` itself raises (engine
    closed mid-shutdown, pool exhausted), the helper MUST NOT propagate
    the exception to the caller. The failure is logged instead."""
    sl_patch, els_patch, _, _ = _patch_sessions()
    logged: list = []

    class _BlowUpOnFirstConstruct:
        """First construct (fn session) raises; subsequent constructs
        (error-log session) behave like _FakeDatabase."""

        count = 0

        def __new__(cls, *args, **kwargs):
            if _BlowUpOnFirstConstruct.count == 0:
                _BlowUpOnFirstConstruct.count += 1
                raise RuntimeError("engine closed")
            _BlowUpOnFirstConstruct.count += 1
            inst = _FakeDatabase(*args, **kwargs)
            logged.append(inst)
            return inst

    def fake_helper(*, database):
        pytest.fail("fn should never run if session construction fails")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _BlowUpOnFirstConstruct),
    ):
        result = await notify_via_threadpool(fake_helper)

    assert result is None  # must NOT re-raise
    # The error-log Database was still built.
    assert len(logged) == 1
    row = logged[0].created[0]
    assert row.service == "push_notifications"
    assert row.error_type == "RuntimeError"
    assert "engine closed" in row.error_message


async def test_stack_trace_is_real_for_fn_exception():
    """Review fix: the stack_trace stored on the ErrorLog row must
    include the fn's actual traceback, not 'NoneType: None'."""
    sl_patch, els_patch, _, _ = _patch_sessions()

    def fake_helper(*, database):
        def inner():
            raise ValueError("inner frame")

        inner()

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    error_db = _FakeDatabase.instances[1]
    row = error_db.created[0]
    assert "NoneType: None" not in row.stack_trace
    assert "ValueError: inner frame" in row.stack_trace
    # Both frames should show up in the trace.
    assert "inner" in row.stack_trace


async def test_stack_trace_is_not_nonetype_for_fabricated_error():
    """Review fix: the SessionLocal-is-None path constructs but does not
    raise a RuntimeError, so `traceback.format_exc()` would have returned
    'NoneType: None\\n'. The row must still carry a useful trace line."""
    sl_patch, els_patch, _, _ = _patch_sessions(session_local=None)

    def fake_helper(*, database):
        pytest.fail("fn must not run when SessionLocal is None")

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
    ):
        await notify_via_threadpool(fake_helper)

    row = _FakeDatabase.instances[0].created[0]
    assert "NoneType: None" not in row.stack_trace
    assert "RuntimeError" in row.stack_trace


async def test_runs_via_run_in_threadpool():
    """The sync body MUST dispatch through fastapi's run_in_threadpool —
    otherwise the whole point of the helper (keeping the event loop free)
    is moot."""
    sl_patch, els_patch, _, _ = _patch_sessions()

    def fake_helper(*, database):
        pass

    from unittest.mock import AsyncMock

    with (
        sl_patch,
        els_patch,
        patch("utils.services.database.Database", _FakeDatabase),
        patch(
            "utils.services.notifications_bridge.run_in_threadpool",
            new_callable=AsyncMock,
        ) as tp,
    ):
        await notify_via_threadpool(fake_helper)

    tp.assert_awaited_once()
