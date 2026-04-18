"""Tests for POST /v1/admin/notifications/test-push."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from conftest import MockExecuteResult, MockUser


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Each test starts with a clean rate-limit window."""
    from api.v1.admin.send_test_push import _reset_rate_limit_for_test
    _reset_rate_limit_for_test()
    yield
    _reset_rate_limit_for_test()


class _FakePushService:
    """Configurable stand-in for the real PushNotificationService."""

    def __init__(self, result=None):
        self.result = result or {
            "success_count": 1,
            "failure_count": 0,
            "cleaned_tokens": 0,
            "message_id": "fcm-msg-abc123",
            "log_only": False,
            "quiet_hours_active": False,
            "suppressed_by_prefs": False,
            "suppressed_by_quiet_hours": False,
        }
        self.calls = []

    def send_to_user(self, user, notification, db_session=None, force=False):
        self.calls.append({
            "user": user,
            "notification": notification,
            "force": force,
        })
        return self.result


class TestSendTestPushHappyPath:
    def test_success_writes_audit_row_and_returns_ok(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_user.push_tokens = ["token-abc"]
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        fake = _FakePushService()
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post(
                "/v1/admin/notifications/test-push",
                json={},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["message_id"] == "fcm-msg-abc123"
        assert data["log_only"] is False
        assert data["success_count"] == 1
        assert data["outcome"] == "ok"
        assert data["target_user_id"] == str(mock_user.id)

        # Force defaults to True — quiet-hour bypass on the send path
        assert fake.calls[0]["force"] is True
        # Audit row was added
        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        audit_rows = [r for r in added if getattr(r, "service", None) == "audit"]
        assert len(audit_rows) == 1
        assert audit_rows[0].error_type == "AdminTestPushAudit"
        assert "admin:test_push" in audit_rows[0].error_message
        assert "result=ok" in audit_rows[0].error_message
        assert "fcm-msg-abc123" in audit_rows[0].error_message


class TestSendTestPushLogOnlyMode:
    def test_log_only_returns_ok_with_flag_set(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        fake = _FakePushService(result={
            "success_count": 0,
            "failure_count": 0,
            "cleaned_tokens": 0,
            "message_id": "log-only",
            "log_only": True,
            "quiet_hours_active": False,
            "suppressed_by_prefs": False,
            "suppressed_by_quiet_hours": False,
        })
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post("/v1/admin/notifications/test-push", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["log_only"] is True
        assert data["outcome"] == "log_only"
        assert data["message_id"] == "log-only"


class TestSendTestPushQuietHours:
    def test_force_false_during_quiet_hours_reports_suppression(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_user.push_tokens = ["token-abc"]
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        fake = _FakePushService(result={
            "success_count": 0,
            "failure_count": 0,
            "cleaned_tokens": 0,
            "message_id": None,
            "log_only": False,
            "quiet_hours_active": True,
            "suppressed_by_prefs": False,
            "suppressed_by_quiet_hours": True,
        })
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post(
                "/v1/admin/notifications/test-push?force=false",
                json={},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["suppressed_by_quiet_hours"] is True
        assert data["quiet_hours_active"] is True
        assert data["outcome"] == "suppressed_quiet_hours"
        # send_to_user was called with force=False
        assert fake.calls[0]["force"] is False


class TestSendTestPushNoTokens:
    def test_no_tokens_registered_returns_specific_outcome(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_user.push_tokens = []
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        # Push service returns cleanly with no send happening
        fake = _FakePushService(result={
            "success_count": 0,
            "failure_count": 0,
            "cleaned_tokens": 0,
            "message_id": None,
            "log_only": False,
            "quiet_hours_active": False,
            "suppressed_by_prefs": False,
            "suppressed_by_quiet_hours": False,
        })
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post("/v1/admin/notifications/test-push", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["outcome"] == "no_tokens"
        assert data["tokens_registered"] == 0


class TestSendTestPushRateLimit:
    def test_11th_request_returns_429_no_audit_row(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_user.push_tokens = ["token-abc"]
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        fake = _FakePushService()
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            # 10 successful requests
            for _ in range(10):
                resp = client.post("/v1/admin/notifications/test-push", json={})
                assert resp.status_code == 200

            # Audit row count BEFORE rate-limited call
            pre_rate_limit_adds = len(mock_db.db.add.call_args_list)

            # 11th request is rate-limited
            resp = client.post("/v1/admin/notifications/test-push", json={})
            assert resp.status_code == 429
            body = resp.json()
            assert body["data"]["error"] == "rate_limited"
            assert body["data"]["retry_after_s"] >= 1

            # No audit row was added for the rate-limited call
            assert len(mock_db.db.add.call_args_list) == pre_rate_limit_adds
            # And the push service was NOT called
            assert len(fake.calls) == 10


class TestSendTestPushTargetUserNotFound:
    def test_unknown_target_user_id_returns_404(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        # target user lookup returns None
        mock_db.db.execute.return_value = MockExecuteResult([])

        fake = _FakePushService()
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post(
                "/v1/admin/notifications/test-push",
                json={"target_user_id": "00000000-0000-0000-0000-000000000000"},
            )

        assert response.status_code == 404
        # Push service was not called
        assert fake.calls == []


class TestSendTestPushExplicitTarget:
    def test_with_custom_title_body_targeting_another_user(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        target_user = MockUser(id="11111111-1111-1111-1111-111111111111", push_tokens=["tok"])
        mock_db.db.execute.return_value = MockExecuteResult([target_user])

        fake = _FakePushService()
        with patch(
            "api.v1.admin.send_test_push.get_push_service",
            return_value=fake,
        ):
            response = client.post(
                "/v1/admin/notifications/test-push",
                json={
                    "title": "Ping",
                    "body": "Are you alive?",
                    "target_user_id": str(target_user.id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["target_user_id"] == str(target_user.id)

        # Confirm custom title/body made it to the notification
        call = fake.calls[0]
        assert call["notification"].title == "Ping"
        assert call["notification"].body == "Are you alive?"
        assert call["user"] is target_user
