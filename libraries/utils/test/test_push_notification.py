"""Unit tests for PushNotificationService.

Covers log-only mode, structured logging, quiet-hours suppression, and
the force flag. These are unit tests — no real Firebase SDK or DB writes.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

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


def _make_notification(ntype: NotificationType = NotificationType.SYSTEM) -> PushNotification:
    return PushNotification(
        title="Hello",
        body="World",
        notification_type=ntype,
        data={"route": "/"},
    )


def _make_user(
    push_enabled: bool = True,
    quiet_start: str | None = None,
    quiet_end: str | None = None,
    tokens: list[str] | None = None,
):
    user = MagicMock()
    user.id = "user-abc-123"
    user.push_tokens = tokens if tokens is not None else ["token-dev-1"]
    user.notification_preferences = {
        "push_enabled": push_enabled,
        "quiet_hours_start": quiet_start,
        "quiet_hours_end": quiet_end,
    }
    return user


# ----------------------------------------------------------------------
# Test A — __init__ with no creds triggers log-only mode and does NOT
# init Firebase. Exactly one INFO log emitted.
# ----------------------------------------------------------------------

def test_init_no_creds_is_log_only(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
        mock_fa._apps = {}
        service = PushNotificationService()

    assert service.log_only is True
    assert service.is_available is False
    mock_fa.initialize_app.assert_not_called()

    log_only_msgs = [
        r for r in caplog.records
        if "running in log-only mode" in r.getMessage()
    ]
    assert len(log_only_msgs) == 1


# ----------------------------------------------------------------------
# Test B — send in log-only mode returns the log-only dict, does NOT
# touch the FCM client, and logs an INFO line with payload shape.
# ----------------------------------------------------------------------

def test_send_to_user_in_log_only_mode(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()

        user = _make_user()
        notification = _make_notification(NotificationType.SYSTEM)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["log_only"] is True
    assert result["message_id"] == "log-only"
    assert result["success_count"] == len(user.push_tokens)
    mock_messaging.send.assert_not_called()
    mock_messaging.send_each_for_multicast.assert_not_called()

    payload_logs = [
        r for r in caplog.records
        if "[log-only] would multicast" in r.getMessage()
    ]
    assert len(payload_logs) == 1
    msg = payload_logs[0].getMessage()
    assert "type=system" in msg
    assert "Hello" in msg


# ----------------------------------------------------------------------
# Test C — send with FCM raising → returns structured error, logs ERROR,
# writes error_logs row with service="push_notifications", never raises.
# ----------------------------------------------------------------------

def test_send_to_user_fcm_exception_writes_error_log(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')

    # Mock the Firebase SDK: credentials.Certificate returns a cred,
    # initialize_app returns an app, but messaging.send_each_for_multicast
    # raises.
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock(name="fake-app")
        mock_creds.Certificate.return_value = MagicMock()

        # send_each_for_multicast raises
        fcm_error = RuntimeError("FCM 500: boom")
        mock_messaging.send_each_for_multicast.side_effect = fcm_error

        # Intercept the error_logs write path (dynamically imported inside
        # _log_send_failure) by patching the modules at their source.
        mock_error_log_cls = MagicMock(name="ErrorLog")
        mock_db_cls = MagicMock(name="Database")
        mock_db = mock_db_cls.return_value

        with patch.dict(
            "sys.modules",
            {
                "utils.models.error_log": MagicMock(ErrorLog=mock_error_log_cls),
                "utils.services.database": MagicMock(Database=mock_db_cls),
            },
        ), caplog.at_level(logging.ERROR, logger="utils.services.push_notification"):
            service = PushNotificationService()
            assert service.log_only is False

            user = _make_user()
            notification = _make_notification(NotificationType.SYSTEM)

            # Must not raise
            result = service.send_to_user(user, notification)

    assert result["success_count"] == 0
    assert result["failure_count"] >= 1
    assert result["log_only"] is False

    # ERROR log emitted
    error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("multicast failed" in r.getMessage() for r in error_logs)

    # error_logs row written with service="push_notifications"
    mock_error_log_cls.assert_called_once()
    call_kwargs = mock_error_log_cls.call_args.kwargs
    assert call_kwargs["service"] == "push_notifications"
    assert call_kwargs["error_type"] == "PushSendFailure"
    mock_db.create.assert_called_once()


# ----------------------------------------------------------------------
# Test D — force=True during quiet hours → FCM IS called, no
# quiet-hours suppression log emitted.
# ----------------------------------------------------------------------

def test_send_to_user_force_bypasses_quiet_hours(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock()
        mock_creds.Certificate.return_value = MagicMock()

        mock_response = MagicMock()
        mock_response.success_count = 1
        mock_response.failure_count = 0
        mock_response.responses = [MagicMock(success=True, message_id="fcm-123", exception=None)]
        mock_messaging.send_each_for_multicast.return_value = mock_response

        service = PushNotificationService()
        # Quiet hours that encompass all clock times
        user = _make_user(quiet_start="00:00", quiet_end="23:59")
        notification = _make_notification(NotificationType.SYSTEM)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification, force=True)

    assert result["success_count"] == 1
    assert result["suppressed_by_quiet_hours"] is False
    mock_messaging.send_each_for_multicast.assert_called_once()

    quiet_logs = [
        r for r in caplog.records
        if "suppressed (quiet hours)" in r.getMessage()
    ]
    assert quiet_logs == []


# ----------------------------------------------------------------------
# Test E — force=False during quiet hours → FCM NOT called, suppression
# log emitted with reason.
# ----------------------------------------------------------------------

def test_send_to_user_quiet_hours_suppression(monkeypatch, caplog):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock()
        mock_creds.Certificate.return_value = MagicMock()

        service = PushNotificationService()
        user = _make_user(quiet_start="00:00", quiet_end="23:59")
        notification = _make_notification(NotificationType.SYSTEM)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification, force=False)

    assert result["suppressed_by_quiet_hours"] is True
    assert result["quiet_hours_active"] is True
    assert result["message_id"] is None
    mock_messaging.send.assert_not_called()
    mock_messaging.send_each_for_multicast.assert_not_called()

    quiet_logs = [
        r for r in caplog.records
        if "suppressed (quiet hours)" in r.getMessage()
    ]
    assert len(quiet_logs) == 1


# ----------------------------------------------------------------------
# Bonus: NotificationType.TEST bypasses user prefs even without force=True.
# ----------------------------------------------------------------------

def test_test_type_bypasses_user_prefs(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock()
        mock_creds.Certificate.return_value = MagicMock()

        mock_response = MagicMock()
        mock_response.success_count = 1
        mock_response.failure_count = 0
        mock_response.responses = [MagicMock(success=True, message_id="fcm-test", exception=None)]
        mock_messaging.send_each_for_multicast.return_value = mock_response

        service = PushNotificationService()
        # User has push_enabled=False but the diagnostic type should still send
        user = _make_user(push_enabled=False)
        notification = _make_notification(NotificationType.TEST)

        result = service.send_to_user(user, notification, force=False)

    assert result["success_count"] == 1
    assert result["suppressed_by_prefs"] is False


# ----------------------------------------------------------------------
# Bonus: no tokens registered → returns cleanly with 0/0, no send attempt.
# ----------------------------------------------------------------------

def test_send_to_user_no_tokens(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()

        user = _make_user(tokens=[])
        notification = _make_notification(NotificationType.TEST)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["success_count"] == 0
    assert result["failure_count"] == 0
    assert result["message_id"] is None
    mock_messaging.send.assert_not_called()
    no_token_logs = [r for r in caplog.records if "no tokens registered" in r.getMessage()]
    assert len(no_token_logs) == 1
