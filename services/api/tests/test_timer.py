"""Tests for timer endpoints.

aam-21: handlers are now `AsyncEndpoint` — fixtures use
`mock_async_db`. `GetActiveTimers` switched from
`db.query(...).filter(...).all()` to `await db.execute(select(...))`, so
the mock is on `db.execute` + `MockExecuteResult` instead of
`db.query` + `MockQuery`.
"""

from datetime import UTC, datetime

from conftest import MockActiveTimer, MockExecuteResult


class TestGetActiveTimers:
    """Tests for GET /v1/timers/active."""

    def test_get_active_timers_success(self, client, mock_async_db, mock_user):
        """Test getting active timers."""
        timer = MockActiveTimer(user_id=str(mock_user.id))
        # GetActiveTimers uses `await db.execute(select(ActiveTimer)...)`
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[timer])

        response = client.get("/v1/timers/active")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_get_active_timers_empty(self, client, mock_async_db, mock_user):
        """Test getting active timers when none exist."""
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get("/v1/timers/active")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestCreateTimer:
    """Tests for POST /v1/timers."""

    def test_create_timer_success(self, client, mock_async_db, mock_user):
        """Test creating a timer."""
        response = client.post(
            "/v1/timers",
            json={
                "label": "Boil water",
                "duration_seconds": 600,
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "Boil water"
        assert data["duration_seconds"] == 600
        assert data["status"] == "running"

    def test_create_timer_missing_duration(self, client, mock_async_db):
        """Test creating a timer without duration fails."""
        response = client.post(
            "/v1/timers",
            json={"label": "Test"}
        )
        assert response.status_code == 422


class TestUpdateTimer:
    """Tests for PUT /v1/timers/{timer_id}."""

    def test_pause_timer(self, client, mock_async_db, mock_user):
        """Test pausing a running timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "paused"}
        )
        assert response.status_code == 200

    def test_update_timer_not_found(self, client, mock_async_db, mock_user):
        """Test updating a nonexistent timer."""
        response = client.put(
            "/v1/timers/nonexistent",
            json={"status": "paused"}
        )
        assert response.status_code == 404


class TestDeleteTimer:
    """Tests for DELETE /v1/timers/{timer_id}."""

    def test_delete_timer_success(self, client, mock_async_db, mock_user):
        """Test deleting a timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.delete(f"/v1/timers/{timer_id}")
        assert response.status_code == 200

    def test_delete_timer_not_found(self, client, mock_async_db, mock_user):
        """Test deleting a nonexistent timer."""
        response = client.delete("/v1/timers/nonexistent")
        assert response.status_code == 404

    def test_delete_timer_wrong_user(self, client, mock_async_db, mock_user):
        """Test deleting another user's timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id="other-user-id",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.delete(f"/v1/timers/{timer_id}")
        assert response.status_code == 403


class TestUpdateTimerMissingBranches:
    """Tests for missing branches in update_timer.py."""

    def test_update_timer_archived(self, client, mock_async_db, mock_user):
        """Test updating an archived timer returns 404 (line 32)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            archived_at=datetime.now(UTC),  # archived
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "paused"}
        )
        assert response.status_code == 404

    def test_update_timer_wrong_user(self, client, mock_async_db, mock_user):
        """Test updating another user's timer returns 403 (line 40-45)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id="other-user-id",
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "paused"}
        )
        assert response.status_code == 403

    def test_update_timer_invalid_status(self, client, mock_async_db, mock_user):
        """Test updating timer with invalid status returns 400 (line 48-53)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400

    def test_update_completed_timer_returns_400(self, client, mock_async_db, mock_user):
        """Test updating a completed timer returns 400 (line 57-62)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="completed",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "running"}
        )
        assert response.status_code == 400

    def test_update_cancelled_timer_returns_400(self, client, mock_async_db, mock_user):
        """Test updating a cancelled timer returns 400 (line 57-62)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="cancelled",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "paused"}
        )
        assert response.status_code == 400

    def test_resume_paused_timer(self, client, mock_async_db, mock_user):
        """Test resuming a paused timer (line 72-76)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="paused",
            paused_at=datetime.now(UTC),
            elapsed_when_paused=60,
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "running"}
        )
        assert response.status_code == 200
        assert timer.status == "running"
        assert timer.paused_at is None

    def test_complete_running_timer(self, client, mock_async_db, mock_user):
        """Test completing a running timer (line 78-79)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "completed"}
        )
        assert response.status_code == 200
        assert timer.status == "completed"

    def test_cancel_running_timer(self, client, mock_async_db, mock_user):
        """Test cancelling a running timer (line 78-79)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"status": "cancelled"}
        )
        assert response.status_code == 200
        assert timer.status == "cancelled"

    def test_add_seconds_to_timer(self, client, mock_async_db, mock_user):
        """Test adding seconds to a timer (line 82-83)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
            duration_seconds=300,
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"add_seconds": 60}
        )
        assert response.status_code == 200
        assert timer.duration_seconds == 360

    def test_add_seconds_zero_ignored(self, client, mock_async_db, mock_user):
        """Test that add_seconds=0 does not change duration (line 82 false branch)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
            duration_seconds=300,
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"add_seconds": 0}
        )
        assert response.status_code == 200
        assert timer.duration_seconds == 300

    def test_update_timer_no_status_no_add_seconds(self, client, mock_async_db, mock_user):
        """Test updating timer with no status or add_seconds (no-op commit)."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_async_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={}
        )
        assert response.status_code == 200
