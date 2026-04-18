"""Tests for POST /v1/users/me/feedback (CreateUserFeedback)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Each test starts with a clean rate-limit window."""
    from api.v1.user.create_user_feedback import _reset_rate_limit_for_test
    _reset_rate_limit_for_test()
    yield
    _reset_rate_limit_for_test()


@pytest.fixture
def mock_send_task():
    """Patch celery_app.send_task so tests don't actually enqueue."""
    with patch(
        "api.v1.user.create_user_feedback.celery_app.send_task",
    ) as m:
        yield m


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreateFeedbackHappyPath:
    def test_minimal_valid_body_persists_and_enqueues(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Share sheet bounces me to home"},
        )

        assert response.status_code == 201
        data = response.json()
        assert uuid.UUID(data["id"])  # valid UUID
        assert data["status"] == "unread"

        # DB write happened
        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        feedback_rows = [
            r for r in added if type(r).__name__ == "UserFeedback"
        ]
        assert len(feedback_rows) == 1
        assert feedback_rows[0].body == "Share sheet bounces me to home"
        assert feedback_rows[0].category is None
        assert feedback_rows[0].context is None
        assert feedback_rows[0].status == "unread"
        assert str(feedback_rows[0].user_id) == str(mock_user.id)

        # Fan-out task enqueued
        mock_send_task.assert_called_once()
        task_name, call_kwargs = (
            mock_send_task.call_args.args[0],
            mock_send_task.call_args.kwargs,
        )
        assert task_name == "notify_admins_new_feedback"
        assert call_kwargs["args"] == [str(feedback_rows[0].id)]

    def test_all_optional_fields_populated(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        recipe_id = str(uuid.uuid4())
        response = client.post(
            "/v1/users/me/feedback",
            json={
                "body": "Would love dark mode in Cooking Mode",
                "category": "idea",
                "context": {
                    "app_version": "1.0.13",
                    "platform": "ios",
                    "route": "/cook/123",
                    "recipe_id": recipe_id,
                },
            },
        )

        assert response.status_code == 201
        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        feedback_rows = [
            r for r in added if type(r).__name__ == "UserFeedback"
        ]
        assert len(feedback_rows) == 1
        row = feedback_rows[0]
        assert row.category == "idea"
        assert row.context == {
            "app_version": "1.0.13",
            "platform": "ios",
            "route": "/cook/123",
            "recipe_id": recipe_id,
        }

    def test_enqueue_failure_does_not_break_response(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        """If the Celery broker is flaky, the user still gets 201 —
        the feedback row is durable, fan-out is best-effort."""
        mock_send_task.side_effect = RuntimeError("broker down")

        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Test"},
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# Validation (422)
# ---------------------------------------------------------------------------


class TestCreateFeedbackValidation:
    def test_empty_body_rejected(self, client, mock_user, mock_db, mock_send_task):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": ""},
        )
        assert response.status_code == 422
        mock_send_task.assert_not_called()

    def test_whitespace_only_body_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "   \n\t  "},
        )
        assert response.status_code == 422

    def test_body_over_4000_chars_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "a" * 4001},
        )
        assert response.status_code == 422

    def test_body_at_exact_4000_chars_accepted(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "a" * 4000},
        )
        assert response.status_code == 201

    def test_invalid_category_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi", "category": "rant"},
        )
        assert response.status_code == 422

    def test_invalid_platform_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={
                "body": "Hi",
                "context": {"platform": "windows"},
            },
        )
        assert response.status_code == 422

    def test_unknown_context_key_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        """The tight context schema must reject unknown keys — NFR52
        plus the 'users submit knowing admins see this' design
        principle relies on the envelope being predictable."""
        response = client.post(
            "/v1/users/me/feedback",
            json={
                "body": "Hi",
                "context": {
                    "app_version": "1.0.0",
                    "fingerprint": "evil",  # not in the schema
                },
            },
        )
        assert response.status_code == 422

    def test_unknown_top_level_key_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi", "extra_field": "evil"},
        )
        assert response.status_code == 422

    def test_invalid_recipe_id_rejected(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={
                "body": "Hi",
                "context": {"recipe_id": "not-a-uuid"},
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestCreateFeedbackAuth:
    def test_unauthenticated_returns_401(
        self, unauthed_client, mock_db, mock_send_task,
    ):
        """Submission requires auth — prevents drive-by spam."""
        response = unauthed_client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi"},
        )
        # Missing Authorization header trips the FastAPI `Header()`
        # requirement → 422 from the validation layer *before* the
        # `get_current_user` dependency runs. Either way, no write.
        assert response.status_code in (401, 422)
        mock_send_task.assert_not_called()


# ---------------------------------------------------------------------------
# Rate-limiting
# ---------------------------------------------------------------------------


class TestCreateFeedbackRateLimit:
    def test_11th_request_returns_429_and_does_not_enqueue(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        for _ in range(10):
            resp = client.post(
                "/v1/users/me/feedback",
                json={"body": "Hi"},
            )
            assert resp.status_code == 201

        pre_add_count = len(mock_db.db.add.call_args_list)
        pre_send_count = mock_send_task.call_count

        # 11th request — over limit
        resp = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi"},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["data"]["error"] == "rate_limited"
        assert body["data"]["retry_after_s"] >= 1

        # No new row, no new task dispatched
        assert len(mock_db.db.add.call_args_list) == pre_add_count
        assert mock_send_task.call_count == pre_send_count

    def test_rate_limit_keyed_per_user(
        self, client, mock_user, mock_db, mock_send_task,
    ):
        """One user over the limit does not affect another user."""
        other_user = MagicMock(id=uuid.uuid4())
        other_user.push_tokens = []
        other_user.is_admin = False

        from api.v1.user.create_user_feedback import _check_rate_limit

        # Saturate other_user's window directly (simulating their prior use)
        for _ in range(10):
            ok, _ = _check_rate_limit(str(other_user.id))
            assert ok

        # mock_user's window is fresh — first call succeeds
        resp = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi"},
        )
        assert resp.status_code == 201


