"""Tests for admin endpoints and require_admin dependency."""

import uuid
from unittest.mock import patch

import pytest
from conftest import MockExecuteResult, MockModel, MockUser


class MockErrorLog(MockModel):
    """Mock ErrorLog row for error_logs table."""

    def __init__(self, **kwargs):
        defaults = {
            "error_type": "ValueError",
            "error_message": "something broke",
            "stack_trace": "Traceback...",
            "error_code": None,
            "method": "GET",
            "path": "/v1/test",
            "status_code": 500,
            "user_id": None,
            "service": "api",
            "request_id": str(uuid.uuid4()),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


# ---------------------------------------------------------------------------
# require_admin dependency (tested directly — the middleware stack mangles
# bare APIExceptions, so testing the function gives us clean coverage of the
# raise path without fighting the test client).
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    async def test_admin_user_allowed(self, mock_user):
        from dependencies import require_admin

        mock_user.is_admin = True
        result = await require_admin(user=mock_user)
        assert result is mock_user

    async def test_non_admin_forbidden(self, mock_user):
        from dependencies import require_admin
        from utils.api.endpoint import APIException

        mock_user.is_admin = False
        with pytest.raises(APIException) as exc_info:
            await require_admin(user=mock_user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/admin/stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_returns_aggregate_counts(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        # Queries in order: total_users, total_recipes, total_recipe_books,
        # errors_24h, active_users_7d, unread_feedback, overall_p95_ms,
        # slowest_endpoint.
        mock_db.db.execute.side_effect = [
            MockExecuteResult([7]),
            MockExecuteResult([7]),
            MockExecuteResult([7]),
            MockExecuteResult([7]),
            MockExecuteResult([7]),
            MockExecuteResult([7]),
            MockExecuteResult([None]),  # overall_p95_ms null on cold start
            MockExecuteResult([]),      # slowest_endpoint null on cold start
        ]
        response = client.get("/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 7
        assert data["total_recipes"] == 7
        assert data["total_recipe_books"] == 7
        assert data["errors_24h"] == 7
        assert data["active_users_7d"] == 7


# ---------------------------------------------------------------------------
# GET /v1/admin/errors and /v1/admin/errors/{id}
# ---------------------------------------------------------------------------


class TestGetErrors:
    def test_list_errors_with_service_filter(
        self, client, mock_user, mock_db
    ):
        mock_user.is_admin = True
        err = MockErrorLog(service="api")
        # First call = count, second = paginated list
        mock_db.db.execute.side_effect = [
            MockExecuteResult([3]),
            MockExecuteResult([err]),
        ]
        response = client.get("/v1/admin/errors?service=api&limit=50&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["errors"]) == 1
        assert data["errors"][0]["service"] == "api"

    def test_list_errors_no_filter(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.side_effect = [
            MockExecuteResult([0]),
            MockExecuteResult([]),
        ]
        response = client.get("/v1/admin/errors")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestGetErrorDetail:
    def test_returns_full_error(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        err = MockErrorLog(user_id=str(uuid.uuid4()))
        mock_db.db.execute.return_value = MockExecuteResult([err])
        response = client.get(f"/v1/admin/errors/{err.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == err.id
        assert data["stack_trace"] == "Traceback..."

    def test_returns_404_when_missing(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.get(f"/v1/admin/errors/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/admin/users and PUT /v1/admin/users/{id}/admin
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_returns_users_with_total(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        other = MockUser(email="a@b.com", username="alice")
        mock_db.db.execute.side_effect = [
            MockExecuteResult([2]),
            MockExecuteResult([mock_user, other]),
        ]
        response = client.get("/v1/admin/users?limit=50&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2


class TestUpdateUserAdmin:
    def test_grants_admin_to_other_user(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        target = MockUser(is_admin=False, email="t@b.com")
        mock_db.db.execute.return_value = MockExecuteResult([target])
        response = client.put(
            f"/v1/admin/users/{target.id}/admin",
            json={"is_admin": True},
        )
        assert response.status_code == 200
        assert response.json()["is_admin"] is True

    def test_user_not_found_returns_404(
        self, client, mock_user, mock_db
    ):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.put(
            f"/v1/admin/users/{uuid.uuid4()}/admin",
            json={"is_admin": True},
        )
        assert response.status_code == 404

    def test_cannot_remove_admin_from_last_admin(
        self, client, mock_user, mock_db
    ):
        """Self-demote blocked when admin_count <= 1."""
        mock_user.is_admin = True
        # target = self, admin_count query returns 1
        mock_db.db.execute.side_effect = [
            MockExecuteResult([mock_user]),  # target lookup
            MockExecuteResult([1]),  # admin count
        ]
        response = client.put(
            f"/v1/admin/users/{mock_user.id}/admin",
            json={"is_admin": False},
        )
        assert response.status_code == 400

    def test_self_demote_succeeds_when_other_admins_exist(
        self, client, mock_user, mock_db
    ):
        """Self-demote allowed when admin_count > 1 — covers branch 40->47."""
        mock_user.is_admin = True
        mock_db.db.execute.side_effect = [
            MockExecuteResult([mock_user]),  # target lookup
            MockExecuteResult([5]),  # admin count > 1
        ]
        response = client.put(
            f"/v1/admin/users/{mock_user.id}/admin",
            json={"is_admin": False},
        )
        assert response.status_code == 200
        assert response.json()["is_admin"] is False


# ---------------------------------------------------------------------------
# GET /v1/admin/logs — boto3 path + exception-fallback path
# ---------------------------------------------------------------------------


class TestGetLogs:
    @patch("boto3.client")
    def test_returns_cloudwatch_events(
        self, mock_boto3_client, client, mock_user
    ):
        mock_user.is_admin = True
        mock_client = mock_boto3_client.return_value
        mock_client.filter_log_events.return_value = {
            "events": [
                {
                    "timestamp": 1700000000000,
                    "message": "hello",
                    "logStreamName": "api/1",
                }
            ]
        }
        response = client.get(
            "/v1/admin/logs?service=api&level=INFO&search=hello"
            "&start_time=1&end_time=2&limit=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["events"][0]["message"] == "hello"
        # Filter pattern assembled from level+search
        call_kwargs = mock_client.filter_log_events.call_args.kwargs
        assert call_kwargs["filterPattern"]
        assert call_kwargs["startTime"] == 1
        assert call_kwargs["endTime"] == 2

    def test_cloudwatch_unavailable_returns_empty(
        self, client, mock_user
    ):
        """boto3 raises → endpoint returns empty list with error message."""
        mock_user.is_admin = True
        # No mock — real boto3.client will fail without creds
        response = client.get("/v1/admin/logs?service=api")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["error"] is not None
