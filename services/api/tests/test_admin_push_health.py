"""Tests for GET /v1/admin/notifications/health/{user_id_or_email}."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from conftest import MockExecuteResult, MockModel, MockUser


def _mock_error_log(
    *,
    error_type: str = "PushSendFailure",
    error_message: str = "FCM UNREGISTERED",
    service: str = "push_notifications",
    user_id=None,
    request_id: str | None = "req-abc",
):
    row = MockModel(
        error_type=error_type,
        error_message=error_message,
        service=service,
        user_id=user_id,
        request_id=request_id,
        created_at=datetime.now(UTC),
    )
    return row


class TestAdminPushHealthByUuid:
    def test_uuid_lookup_returns_health_blob(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        target = MockUser(
            email="target@example.com",
            auth0_id="auth0|target-abc",
            push_tokens=["fcm-token-aaaaaaaa-zzzz"],
            notification_permission_status="granted",
        )
        error_row = _mock_error_log(user_id=target.id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([target]),       # uuid lookup hits
            MockExecuteResult([error_row]),    # recent errors
        ]

        response = client.get(
            f"/v1/admin/notifications/health/{target.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(target.id)
        assert data["email"] == "target@example.com"
        assert data["notification_permission_status"] == "granted"
        assert data["push_tokens_count"] == 1
        assert data["push_tokens"][0]["fcm_token_prefix"].startswith("fcm-toke")
        assert data["recent_errors_count"] == 1
        assert data["recent_errors"][0]["error_type"] == "PushSendFailure"
        assert data["last_successful_send_at"] is None
        assert data["last_successful_send_type"] is None
        assert "crashlytics" in data["crashlytics_query_url"]
        assert "auth0|target-abc" in data["crashlytics_query_url"]


class TestAdminPushHealthByEmail:
    def test_email_lookup_resolves_same_user(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        target = MockUser(
            email="target@example.com",
            auth0_id="auth0|target-xyz",
            push_tokens=[],
            notification_permission_status="declined",
        )

        # First execute: UUID lookup — raw string won't parse as UUID, so
        # the endpoint skips the first select(). Actually it tries both.
        # Implementation does try/except on uuid.UUID(raw) — if raw is not
        # a UUID it proceeds directly to email lookup, so only one
        # execute for user resolution, then one for error rows.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([target]),  # email lookup
            MockExecuteResult([]),        # no recent errors
        ]

        response = client.get(
            "/v1/admin/notifications/health/TARGET@example.com"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(target.id)
        assert data["email"] == "target@example.com"
        assert data["push_tokens_count"] == 0
        assert data["recent_errors_count"] == 0


class TestAdminPushHealth404:
    def test_nonexistent_uuid_returns_404(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        missing = uuid.uuid4()
        # Both UUID and email lookups come back empty.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
            MockExecuteResult([]),
        ]

        response = client.get(
            f"/v1/admin/notifications/health/{missing}"
        )

        assert response.status_code == 404

    def test_nonexistent_email_returns_404(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        # Non-UUID input → endpoint goes straight to email lookup.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
        ]

        response = client.get(
            "/v1/admin/notifications/health/noone@example.com"
        )

        assert response.status_code == 404


class TestAdminPushHealthAuthz:
    def test_non_admin_raises_403(self, client, mock_user, mock_async_db):
        from utils.classes.error_code import ErrorCode
        mock_user.is_admin = False
        response = client.get(
            f"/v1/admin/notifications/health/{uuid.uuid4()}"
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == ErrorCode.FORBIDDEN.value


class TestAdminPushHealthAudit:
    def test_one_audit_row_per_call(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        target = MockUser(
            email="audit@example.com",
            auth0_id="auth0|audit",
            push_tokens=[],
            notification_permission_status="granted",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
        ]

        response = client.get(
            f"/v1/admin/notifications/health/{target.id}"
        )

        assert response.status_code == 200
        added = [c.args[0] for c in mock_async_db.db.add.call_args_list]
        audit_rows = [r for r in added if getattr(r, "service", None) == "audit"]
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit.error_type == "AdminPushHealthCheck"
        assert "admin:push_health_check" in audit.error_message
        assert f"target={target.id}" in audit.error_message
        assert f"admin_user={mock_user.id}" in audit.error_message


class TestAdminPushHealthErrorLimit:
    def test_error_limit_out_of_range_returns_400(
        self, client, mock_user, mock_async_db
    ):
        mock_user.is_admin = True
        response = client.get(
            f"/v1/admin/notifications/health/{uuid.uuid4()}"
            "?error_limit=0"
        )
        # FastAPI query-param validation intercepts ge=1 constraints → 422
        # (unprocessable entity) before the endpoint runs.
        assert response.status_code == 422

        response2 = client.get(
            f"/v1/admin/notifications/health/{uuid.uuid4()}"
            "?error_limit=51"
        )
        assert response2.status_code == 422
