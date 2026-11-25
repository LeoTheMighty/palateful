"""Unit tests for the async send variants (aam-8-firebase-threadpool-wrap).

The Firebase Admin SDK's `messaging.send*` calls are blocking HTTP, so
async-path callers must reach FCM via a threadpool hop. These tests pin
the two properties every async caller relies on:

1. Each `*_async` variant dispatches its sync counterpart through
   fastapi's `run_in_threadpool` (mirrors
   `test_notifications_bridge.test_runs_via_run_in_threadpool`).
2. The FCM call genuinely executes off the event-loop thread, and the
   sync result dict round-trips unchanged.

The sync methods themselves are covered by `test_push_notification.py`
and stay contract-frozen for the worker.
"""

from __future__ import annotations

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    PushNotificationService,
)


@pytest.fixture(autouse=True)
def _reset_service_state(monkeypatch):
    """Reset class-level state + scrub env between tests so each starts fresh."""
    monkeypatch.delenv("FIREBASE_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("FIREBASE_CREDENTIALS_PATH", raising=False)
    PushNotificationService._initialized = False
    PushNotificationService._app = None
    PushNotificationService._log_only = False
    yield
    PushNotificationService._initialized = False
    PushNotificationService._app = None
    PushNotificationService._log_only = False


def _make_notification() -> PushNotification:
    return PushNotification(
        title="Hello",
        body="World",
        notification_type=NotificationType.SYSTEM,
        data={"route": "/"},
    )


def _make_user(tokens: list[str] | None = None):
    user = MagicMock()
    user.id = "user-abc-123"
    user.push_tokens = tokens if tokens is not None else ["token-dev-1"]
    user.notification_preferences = {"push_enabled": True}
    return user


def _log_only_service() -> PushNotificationService:
    with patch("utils.services.push_notification.firebase_admin") as mock_fa:
        mock_fa._apps = {}
        return PushNotificationService()


# ----------------------------------------------------------------------
# Every async variant MUST dispatch through run_in_threadpool with its
# sync counterpart — otherwise the event loop blocks on FCM's HTTP call.
# ----------------------------------------------------------------------

async def test_send_to_token_async_dispatches_via_threadpool():
    service = _log_only_service()
    notification = _make_notification()

    with patch(
        "utils.services.push_notification.run_in_threadpool",
        new_callable=AsyncMock,
    ) as tp:
        tp.return_value = {"message_id": "m-1"}
        result = await service.send_to_token_async("tok-1", notification)

    tp.assert_awaited_once_with(service.send_to_token, "tok-1", notification)
    assert result == {"message_id": "m-1"}


async def test_send_to_tokens_async_dispatches_via_threadpool():
    service = _log_only_service()
    notification = _make_notification()

    with patch(
        "utils.services.push_notification.run_in_threadpool",
        new_callable=AsyncMock,
    ) as tp:
        tp.return_value = {"success_count": 2}
        result = await service.send_to_tokens_async(["t-1", "t-2"], notification)

    tp.assert_awaited_once_with(service.send_to_tokens, ["t-1", "t-2"], notification)
    assert result == {"success_count": 2}


async def test_send_to_user_async_dispatches_via_threadpool():
    service = _log_only_service()
    notification = _make_notification()
    user = _make_user()
    db_session = MagicMock(name="sync_session")

    with patch(
        "utils.services.push_notification.run_in_threadpool",
        new_callable=AsyncMock,
    ) as tp:
        tp.return_value = {"success_count": 1}
        result = await service.send_to_user_async(
            user, notification, db_session, force=True
        )

    tp.assert_awaited_once_with(
        service.send_to_user, user, notification, db_session, force=True
    )
    assert result == {"success_count": 1}


async def test_send_to_users_async_dispatches_via_threadpool():
    service = _log_only_service()
    notification = _make_notification()
    users = [_make_user(), _make_user()]

    with patch(
        "utils.services.push_notification.run_in_threadpool",
        new_callable=AsyncMock,
    ) as tp:
        tp.return_value = {"users_notified": 2}
        result = await service.send_to_users_async(users, notification, None, force=False)

    tp.assert_awaited_once_with(
        service.send_to_users, users, notification, None, force=False
    )
    assert result == {"users_notified": 2}


# ----------------------------------------------------------------------
# End-to-end through the REAL run_in_threadpool: the FCM call must land
# on a worker thread (not the event-loop thread) and the sync result
# dict must round-trip unchanged.
# ----------------------------------------------------------------------

async def test_fcm_send_runs_off_event_loop_thread(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')
    loop_thread = threading.current_thread()
    send_thread: list[threading.Thread] = []

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock(name="fake-app")
        mock_creds.Certificate.return_value = MagicMock()

        def fake_send(message):
            send_thread.append(threading.current_thread())
            return "projects/p/messages/m-42"

        mock_messaging.send.side_effect = fake_send
        # UnregisteredError must remain an exception class for the
        # sync method's `except messaging.UnregisteredError` clause.
        mock_messaging.UnregisteredError = type("UnregisteredError", (Exception,), {})

        service = PushNotificationService()
        assert service.log_only is False

        result = await service.send_to_token_async("tok-1", _make_notification())

    assert result == {"message_id": "projects/p/messages/m-42", "log_only": False}
    assert len(send_thread) == 1
    assert send_thread[0] is not loop_thread


async def test_send_to_user_async_log_only_round_trip():
    service = _log_only_service()
    user = _make_user(tokens=["t-1", "t-2"])

    with patch("utils.services.push_notification.messaging") as mock_messaging:
        result = await service.send_to_user_async(user, _make_notification())

    assert result["log_only"] is True
    assert result["message_id"] == "log-only"
    assert result["success_count"] == 2
    mock_messaging.send.assert_not_called()
    mock_messaging.send_each_for_multicast.assert_not_called()
