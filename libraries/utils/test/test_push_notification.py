"""Unit tests for PushNotificationService.

Covers log-only mode, structured logging, quiet-hours suppression, and
the force flag. These are unit tests — no real Firebase SDK or DB writes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
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


# ======================================================================
# nfn-1: Per-category preference suppression tests.
# ======================================================================


def _make_user_with_categories(
    *,
    push_enabled: bool = True,
    categories: dict | None = None,
    legacy_partner_activity: bool | None = None,
    quiet_start: str | None = None,
    quiet_end: str | None = None,
    tokens: list[str] | None = None,
):
    """User mock with explicit prefs.categories control."""
    user = MagicMock()
    user.id = "user-cat-1"
    user.push_tokens = tokens if tokens is not None else ["token-cat-1"]
    prefs = {
        "push_enabled": push_enabled,
        "quiet_hours_start": quiet_start,
        "quiet_hours_end": quiet_end,
    }
    if categories is not None:
        prefs["categories"] = categories
    if legacy_partner_activity is not None:
        prefs["partner_activity"] = legacy_partner_activity
    user.notification_preferences = prefs
    return user


# Test A: categories.imports = False + IMPORT_NEEDS_REVIEW → suppressed,
# no FCM call, log line emitted, response shape correct.
def test_send_to_user_suppressed_by_category_imports(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(categories={"imports": False})
        notification = _make_notification(NotificationType.IMPORT_NEEDS_REVIEW)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is True
    assert result["suppressed_by_prefs"] is False
    assert result["suppressed_by_quiet_hours"] is False
    assert result["message_id"] is None
    mock_messaging.send_each_for_multicast.assert_not_called()
    suppression_logs = [
        r for r in caplog.records
        if "suppressed (category=imports)" in r.getMessage()
    ]
    assert len(suppression_logs) == 1


# Test B: categories absent + IMPORT_NEEDS_REVIEW → fires (default true).
def test_send_to_user_no_categories_key_defaults_to_on(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories()
        notification = _make_notification(NotificationType.IMPORT_NEEDS_REVIEW)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is False
    # Log-only mode by default in this test (no FCM creds): success_count
    # equals number of tokens.
    assert result["log_only"] is True
    assert result["success_count"] == 1


# Test C: legacy partner_activity=False (no categories key) + RECIPE_ADDED
# → suppressed via legacy fallback path.
def test_send_to_user_legacy_partner_activity_false_suppresses(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(legacy_partner_activity=False)
        notification = _make_notification(NotificationType.RECIPE_ADDED)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is True
    mock_messaging.send_each_for_multicast.assert_not_called()


# Test C2: legacy partner_activity=True (no categories key) + RECIPE_ADDED
# → fires.
def test_send_to_user_legacy_partner_activity_true_passes(caplog):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging"):
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(legacy_partner_activity=True)
        notification = _make_notification(NotificationType.RECIPE_ADDED)

        with caplog.at_level(logging.INFO, logger="utils.services.push_notification"):
            result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is False


# Test D: master push_enabled=False + any category True → still suppressed
# (master wins; never reaches the category check).
def test_send_to_user_master_off_suppresses_even_with_category_on():
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(
            push_enabled=False,
            categories={"imports": True},
        )
        notification = _make_notification(NotificationType.IMPORT_NEEDS_REVIEW)

        result = service.send_to_user(user, notification)

    assert result["suppressed_by_prefs"] is True
    assert result["suppressed_by_category"] is False  # Never reached.
    mock_messaging.send_each_for_multicast.assert_not_called()


# Bonus: force=True bypasses category opt-out.
def test_send_to_user_force_bypasses_category():
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(categories={"imports": False})
        notification = _make_notification(NotificationType.IMPORT_NEEDS_REVIEW)

        result = service.send_to_user(user, notification, force=True)

    assert result["suppressed_by_category"] is False
    assert result["log_only"] is True


# Bonus: TEST type bypasses category opt-out (diagnostic).
def test_send_to_user_test_type_bypasses_category():
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging"):
        mock_fa._apps = {}
        service = PushNotificationService()
        # Pretend admin set imports=False AND friends_invitations=False;
        # TEST should still go through.
        user = _make_user_with_categories(
            categories={"imports": False, "friends_invitations": False},
        )
        notification = _make_notification(NotificationType.TEST)

        result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is False


# Test E: each of the 5 new partner_activity types introduced by
# epic-notifications-partner-activity is suppressed when categories.partner_activity=False.
@pytest.mark.parametrize("ntype", [
    NotificationType.RECIPE_FORKED,
    NotificationType.RECIPE_NOTE_ADDED,
    NotificationType.RECIPE_COOKED_BY_PARTNER,
    NotificationType.MEAL_EVENT_INVITE_ACCEPTED,
    NotificationType.COOK_FEEDBACK_PROMPT,
])
def test_new_partner_activity_types_respect_category_opt_out(ntype):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging") as mock_messaging:
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(
            categories={"partner_activity": False},
        )
        notification = _make_notification(ntype)

        result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is True
    mock_messaging.send_each_for_multicast.assert_not_called()


# Bonus: SYSTEM type bypasses category check (no user-facing category).
def test_send_to_user_system_type_bypasses_category():
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.messaging"):
        mock_fa._apps = {}
        service = PushNotificationService()
        user = _make_user_with_categories(
            categories={k: False for k in (
                "meals", "timers", "shopping",
                "partner_activity", "imports", "friends_invitations",
            )},
        )
        notification = _make_notification(NotificationType.SYSTEM)

        result = service.send_to_user(user, notification)

    assert result["suppressed_by_category"] is False


# ----------------------------------------------------------------------
# btri01 — quiet hours are evaluated in the USER's timezone, not the
# container's (UTC). The shipped column default is
# quiet 22:00-08:00 + timezone America/Denver, so evaluating against
# server-local time suppressed every non-forced push from 16:00 to 02:00
# Denver — the entire evening. Regression tests below fail against the
# pre-fix `datetime.now()` implementation.
# ----------------------------------------------------------------------

def _frozen_datetime(fixed_utc: datetime):
    """Build a `datetime` stand-in whose `now(tz)` returns `fixed_utc`
    converted into `tz` (and server-local-naive when tz is None, which is
    what the pre-fix code called)."""

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:  # pragma: no cover — only reached if the fix regresses
                # Container local time == UTC; mirror the naive shape the
                # old `datetime.now()` implementation produced, so these
                # tests fail (rather than error) against a regression.
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)

    return _Frozen


def _default_prefs_user(now_tokens: list[str] | None = None):
    """User carrying the exact `notification_preferences` column default
    from `libraries/utils/utils/models/user.py`."""
    user = MagicMock()
    user.id = "user-denver-1"
    user.push_tokens = now_tokens if now_tokens is not None else ["token-dev-1"]
    user.notification_preferences = {
        "push_enabled": True,
        "email_digest": "daily",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "timezone": "America/Denver",
    }
    return user


@pytest.mark.parametrize(
    "utc_moment,expected_quiet,why",
    [
        # 23:30 UTC == 17:30 MDT — prime dinner/meal-planning hour.
        # Pre-fix this was INSIDE the naive 22:00-08:00 window → suppressed.
        (datetime(2026, 7, 27, 23, 30, tzinfo=UTC), False, "17:30 MDT"),
        # 07:00 UTC == 01:00 MDT — genuinely quiet, and also quiet naively.
        (datetime(2026, 7, 28, 7, 0, tzinfo=UTC), True, "01:00 MDT"),
        # 13:00 UTC == 07:00 MDT — inside the user's window but OUTSIDE the
        # naive one, so pre-fix this leaked a push at 7am local.
        (datetime(2026, 7, 28, 13, 0, tzinfo=UTC), True, "07:00 MDT"),
        # 16:00 UTC == 10:00 MDT — awake, not quiet, either way.
        (datetime(2026, 7, 28, 16, 0, tzinfo=UTC), False, "10:00 MDT"),
    ],
)
def test_quiet_hours_uses_user_timezone(utc_moment, expected_quiet, why):
    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.datetime", _frozen_datetime(utc_moment)):
        mock_fa._apps = {}
        service = PushNotificationService()
        prefs = _default_prefs_user().notification_preferences

        assert service._is_quiet_hours(prefs) is expected_quiet, why


def test_default_prefs_user_gets_evening_push_delivered(monkeypatch):
    """End-to-end: the shipped default prefs must NOT suppress a 17:30
    Denver push. This is the exact shape of every real user row."""
    evening_utc = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)  # 17:30 MDT
    monkeypatch.setenv("FIREBASE_CREDENTIALS_JSON", '{"fake": "creds"}')

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.credentials") as mock_creds, \
         patch("utils.services.push_notification.messaging") as mock_messaging, \
         patch("utils.services.push_notification.datetime", _frozen_datetime(evening_utc)):
        mock_fa._apps = {}
        mock_fa.initialize_app.return_value = MagicMock()
        mock_creds.Certificate.return_value = MagicMock()
        multicast = MagicMock()
        multicast.success_count = 1
        multicast.failure_count = 0
        multicast.responses = []
        mock_messaging.send_each_for_multicast.return_value = multicast

        service = PushNotificationService()
        user = _default_prefs_user()

        result = service.send_to_user(
            user, _make_notification(NotificationType.IMPORT_NEEDS_REVIEW)
        )

    assert result["suppressed_by_quiet_hours"] is False
    assert result["quiet_hours_active"] is False
    assert result["success_count"] == 1
    mock_messaging.send_each_for_multicast.assert_called_once()


@pytest.mark.parametrize("tz_value", [None, "", "  ", "Not/AZone", 42])
def test_quiet_hours_falls_back_to_utc_on_bad_timezone(tz_value):
    """A missing or malformed tz must not raise — it falls back to UTC,
    which is also the container clock (i.e. the pre-fix behaviour)."""
    # 23:30 UTC is inside the naive 22:00-08:00 window.
    utc_moment = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)

    with patch("utils.services.push_notification.firebase_admin") as mock_fa, \
         patch("utils.services.push_notification.datetime", _frozen_datetime(utc_moment)):
        mock_fa._apps = {}
        service = PushNotificationService()
        prefs = {
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "timezone": tz_value,
        }

        assert service._is_quiet_hours(prefs) is True
