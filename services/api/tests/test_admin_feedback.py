"""Tests for admin feedback inbox endpoints and stats extension."""

from __future__ import annotations

import uuid

from conftest import MockExecuteResult, MockModel, MockUser


class MockUserFeedback(MockModel):
    """Mock UserFeedback row."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "body": "Share sheet bounces to home",
            "category": "bug",
            "context": {
                "app_version": "1.0.13",
                "platform": "ios",
                "route": "/recipes/import",
            },
            "status": "unread",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


# ---------------------------------------------------------------------------
# GET /v1/admin/feedback
# ---------------------------------------------------------------------------


class TestListFeedback:
    def test_defaults_to_unread_filter(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        author = MockUser(email="author@example.com", name="Jane Doe")
        fb = MockUserFeedback(user_id=author.id)
        mock_db.db.execute.side_effect = [
            MockExecuteResult([1]),            # count
            MockExecuteResult([(fb, author)]), # listing — iterable of (UserFeedback, User) tuples
        ]
        response = client.get("/v1/admin/feedback")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["status"] == "unread"
        assert data["offset"] == 0
        assert data["limit"] == 25
        assert len(data["items"]) == 1
        assert data["items"][0]["body"] == fb.body
        assert data["items"][0]["user_display_name"] == "Jane Doe"
        assert data["items"][0]["user_email"] == "author@example.com"

    def test_explicit_status_filter(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.side_effect = [
            MockExecuteResult([0]),
            MockExecuteResult([]),
        ]
        response = client.get("/v1/admin/feedback?status=archived")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

    def test_status_all_returns_all(self, client, mock_user, mock_db):
        """`status=all` drops the status filter on both count and listing."""
        mock_user.is_admin = True
        author = MockUser()
        mock_db.db.execute.side_effect = [
            MockExecuteResult([3]),
            MockExecuteResult([
                (MockUserFeedback(status="unread"), author),
                (MockUserFeedback(status="read"), author),
                (MockUserFeedback(status="archived"), author),
            ]),
        ]
        response = client.get("/v1/admin/feedback?status=all")
        assert response.status_code == 200
        assert response.json()["total"] == 3

    def test_invalid_status_returns_400(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        response = client.get("/v1/admin/feedback?status=spam")
        assert response.status_code == 400

    def test_pagination_bounds(self, client, mock_user, mock_db):
        """limit clamped to MAX_LIMIT=100 by the FastAPI Query validator (le=100)."""
        mock_user.is_admin = True
        response = client.get("/v1/admin/feedback?limit=500")
        # FastAPI rejects out-of-range with 422
        assert response.status_code == 422

    def test_display_name_falls_back_to_username_then_email(
        self, client, mock_user, mock_db,
    ):
        mock_user.is_admin = True
        no_name = MockUser(name=None, username="janedoe", email="j@example.com")
        fb = MockUserFeedback(user_id=no_name.id)
        mock_db.db.execute.side_effect = [
            MockExecuteResult([1]),
            MockExecuteResult([(fb, no_name)]),
        ]
        response = client.get("/v1/admin/feedback")
        assert response.json()["items"][0]["user_display_name"] == "janedoe"


# ---------------------------------------------------------------------------
# PUT /v1/admin/feedback/{id}/status
# ---------------------------------------------------------------------------


class TestUpdateFeedbackStatus:
    def test_unread_to_read_writes_audit_row(
        self, client, mock_user, mock_db,
    ):
        mock_user.is_admin = True
        fb = MockUserFeedback(status="unread")
        mock_db.db.execute.return_value = MockExecuteResult([fb])

        response = client.put(
            f"/v1/admin/feedback/{fb.id}/status",
            json={"status": "read"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == fb.id
        assert body["status"] == "read"
        assert body["updated_at"] is not None

        # Audit row written
        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        audit_rows = [
            r for r in added if getattr(r, "service", None) == "audit"
        ]
        assert len(audit_rows) == 1
        row = audit_rows[0]
        assert row.error_type == "FeedbackStatusChange"
        assert f"feedback={fb.id}" in row.error_message
        assert "from=unread" in row.error_message
        assert "to=read" in row.error_message
        assert f"by_admin={mock_user.id}" in row.error_message

    def test_read_to_archived_allowed(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        fb = MockUserFeedback(status="read")
        mock_db.db.execute.return_value = MockExecuteResult([fb])
        response = client.put(
            f"/v1/admin/feedback/{fb.id}/status",
            json={"status": "archived"},
        )
        assert response.status_code == 200

    def test_invalid_status_rejected(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        fb = MockUserFeedback()
        mock_db.db.execute.return_value = MockExecuteResult([fb])
        response = client.put(
            f"/v1/admin/feedback/{fb.id}/status",
            json={"status": "closed"},
        )
        assert response.status_code == 422

    def test_not_found_returns_404(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.put(
            f"/v1/admin/feedback/{uuid.uuid4()}/status",
            json={"status": "read"},
        )
        assert response.status_code == 404

    def test_same_status_no_op_still_writes_audit(
        self, client, mock_user, mock_db,
    ):
        """unread → unread still writes an audit row so the action appears
        in the history, even though nothing really changed."""
        mock_user.is_admin = True
        fb = MockUserFeedback(status="unread")
        mock_db.db.execute.return_value = MockExecuteResult([fb])
        response = client.put(
            f"/v1/admin/feedback/{fb.id}/status",
            json={"status": "unread"},
        )
        assert response.status_code == 200
        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        audit_rows = [
            r for r in added if getattr(r, "service", None) == "audit"
        ]
        assert len(audit_rows) == 1


# ---------------------------------------------------------------------------
# GET /v1/admin/stats — unread_feedback addition
# ---------------------------------------------------------------------------


class TestGetStatsUnreadFeedback:
    def test_stats_includes_unread_feedback_count(
        self, client, mock_user, mock_db,
    ):
        mock_user.is_admin = True
        # Queries: total_users, total_recipes, total_recipe_books,
        # errors_24h, active_users_7d, unread_feedback,
        # overall_p95_ms, slowest_endpoint.
        mock_db.db.execute.side_effect = [
            MockExecuteResult([100]),
            MockExecuteResult([500]),
            MockExecuteResult([50]),
            MockExecuteResult([3]),
            MockExecuteResult([42]),
            MockExecuteResult([7]),
            MockExecuteResult([None]),  # overall_p95_ms
            MockExecuteResult([]),       # slowest_endpoint
        ]
        response = client.get("/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["unread_feedback"] == 7
        # Existing fields still present
        assert data["total_users"] == 100
        assert data["errors_24h"] == 3


# ---------------------------------------------------------------------------
# Placeholder test to exercise an unreachable-in-normal-flow branch: status
# that is not a known outcome but slips through upstream validation (the
# Literal on Params rejects everything else, so this test just confirms the
# validator rejects bogus shape too).
# ---------------------------------------------------------------------------


class TestUpdateFeedbackStatusParams:
    def test_missing_status_field_returns_422(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        response = client.put(
            f"/v1/admin/feedback/{uuid.uuid4()}/status",
            json={},
        )
        assert response.status_code == 422


