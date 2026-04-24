"""Async → sync notification-helper bridge (aam-foundations-notify-threadpool-helper).

Every `AsyncEndpoint` that fans out notifications calls a sync helper
(`notify_import_needs_review`, `notify_book_shared`,
`notify_meal_event_updated`, ...) that still takes `database: Database`.
This module ships the single bridge every such endpoint uses, so
CHUNK-C4's later cleanup has one callsite to retire instead of 13.

Usage:

    from utils.services.notifications_bridge import notify_via_threadpool

    async def execute(self, ...):
        await self.database.commit()  # commit async state first
        await notify_via_threadpool(
            notify_book_shared,
            recipe_book_id=book.id,
            recipe_book_name=book.name,
            invited_user=target_snapshot,
            invited_by=user_snapshot,
        )

Contract:
    * `fn` accepts `database: Database` as a keyword argument; the
      helper injects it — callers must not pass `database` themselves.
    * The sync `Database(db=SessionLocal())` is built on the
      threadpool thread (not the event loop) so the sync pool is never
      touched from async code.
    * The session is always closed (finally) — even if `fn` raises.
    * Exceptions from `fn` are swallowed: notifications are
      fire-and-forget. Failures are persisted to `error_logs` with
      `service='push_notifications'` so they remain queryable via
      `bin/prod-logs` / `audit_errors.py`.
    * Returns `None`. Callers must not rely on the helper's return
      value — the one existing helper with a meaningful return
      (`notify_meal_event_reminder`) is only called from sync
      scheduler tasks, not through this bridge.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from typing import Any

from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# Max length matches `AsyncEndpoint._log_error_to_db` so rows stay
# consistent in size whether they came from endpoint failure or from
# this bridge.
_ERROR_MESSAGE_MAX = 4000


async def notify_via_threadpool(
    fn: Callable[..., Any], *args: Any, **kwargs: Any
) -> None:
    """Dispatch a sync notification helper on a fresh `Database` in the threadpool.

    See module docstring for contract + invariants.

    Raises:
        TypeError: if the caller passes `database` as a kwarg. The
            helper reserves that keyword and would otherwise silently
            shadow the caller's value.
    """
    if "database" in kwargs:
        raise TypeError(
            "notify_via_threadpool reserves the `database` kwarg — do not pass "
            "it; the helper injects a fresh sync session."
        )
    await run_in_threadpool(_invoke_sync, fn, args, kwargs)


def _invoke_sync(
    fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> None:
    """Threadpool-side body: build the sync session, call `fn`, close it.

    Any exception from `fn` or from session construction is caught and
    routed to `_log_bridge_failure` — notifications must never surface
    failures to the caller's request transaction.
    """
    # Imported here so the module stays import-safe in environments
    # without a configured DB (schema checks, offline tooling).
    from utils.services.database import Database, SessionLocal

    fn_name = getattr(fn, "__name__", repr(fn))

    if SessionLocal is None:
        _log_bridge_failure(
            fn_name=fn_name,
            error=RuntimeError(
                "SessionLocal is not configured — cannot dispatch "
                "notification helper"
            ),
        )
        return

    try:
        database = Database(db=SessionLocal())
    except Exception as exc:
        # Engine closed / pool exhausted / pool teardown mid-request —
        # must NOT bubble up. Notifications are fire-and-forget.
        _log_bridge_failure(fn_name=fn_name, error=exc)
        return

    try:
        try:
            fn(*args, database=database, **kwargs)
        except Exception as exc:
            _log_bridge_failure(fn_name=fn_name, error=exc)
    finally:
        database.close()


def _log_bridge_failure(*, fn_name: str, error: Exception) -> None:
    """Persist a failure row to `error_logs` with `service='push_notifications'`.

    Uses the dedicated `ErrorLogSessionLocal` sub-pool when available so
    a main-pool exhaustion incident can never silence these rows. Falls
    back to the default engine (workers / scripts) when the sub-pool
    isn't wired. Any failure inside this method is itself swallowed —
    best-effort, matching `PushNotificationService._log_send_failure`.
    """
    logger.exception("notify_via_threadpool: %s raised", fn_name)
    try:
        from utils.models.error_log import ErrorLog
        from utils.services.database import Database, ErrorLogSessionLocal
    except Exception:
        logger.exception("notify_via_threadpool: error_logs module unavailable")
        return

    try:
        if ErrorLogSessionLocal is not None:
            error_db = Database(db=ErrorLogSessionLocal())
        else:
            error_db = Database()
        try:
            message = f"notify_via_threadpool fn={fn_name} error={error!s}"
            # Format from the exception object (not sys.exc_info) — the
            # SessionLocal-is-None path constructs a RuntimeError without
            # raising it, so format_exc() would return "NoneType: None\n".
            stack = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            error_db.create(
                ErrorLog(
                    error_type=type(error).__name__,
                    error_message=message[:_ERROR_MESSAGE_MAX],
                    stack_trace=stack,
                    service="push_notifications",
                )
            )
        finally:
            error_db.close()
    except Exception:
        logger.exception("notify_via_threadpool: failed to write error_log row")
