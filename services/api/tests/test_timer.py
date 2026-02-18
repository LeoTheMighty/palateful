"""Tests for timer endpoints."""

from conftest import MockActiveTimer, MockQuery


class TestGetActiveTimers:
    """Tests for GET /v1/timers/active."""

    def test_get_active_timers_success(self, client, mock_db, mock_user):
        """Test getting active timers."""
        timer = MockActiveTimer(user_id=str(mock_user.id))

        from utils.models.active_timer import ActiveTimer

        mock_db.set_where(ActiveTimer, [timer])

        response = client.get("/v1/timers/active")
        assert response.status_code == 200
        data = response.json()
        assert "timers" in data

    def test_get_active_timers_empty(self, client, mock_db, mock_user):
        """Test getting active timers when none exist."""
        from utils.models.active_timer import ActiveTimer

        mock_db.set_where(ActiveTimer, [])

        response = client.get("/v1/timers/active")
        assert response.status_code == 200
        data = response.json()
        assert data["timers"] == []


class TestCreateTimer:
    """Tests for POST /v1/timers."""

    def test_create_timer_success(self, client, mock_db, mock_user):
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

    def test_create_timer_missing_duration(self, client, mock_db):
        """Test creating a timer without duration fails."""
        response = client.post(
            "/v1/timers",
            json={"label": "Test"}
        )
        assert response.status_code == 422


class TestUpdateTimer:
    """Tests for PUT /v1/timers/{timer_id}."""

    def test_pause_timer(self, client, mock_db, mock_user):
        """Test pausing a running timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
            status="running",
        )

        from utils.models.active_timer import ActiveTimer

        mock_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.put(
            f"/v1/timers/{timer_id}",
            json={"action": "pause"}
        )
        assert response.status_code == 200

    def test_update_timer_not_found(self, client, mock_db, mock_user):
        """Test updating a nonexistent timer."""
        response = client.put(
            "/v1/timers/nonexistent",
            json={"action": "pause"}
        )
        assert response.status_code == 404


class TestDeleteTimer:
    """Tests for DELETE /v1/timers/{timer_id}."""

    def test_delete_timer_success(self, client, mock_db, mock_user):
        """Test deleting a timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id=str(mock_user.id),
        )

        from utils.models.active_timer import ActiveTimer

        mock_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.delete(f"/v1/timers/{timer_id}")
        assert response.status_code == 200

    def test_delete_timer_not_found(self, client, mock_db, mock_user):
        """Test deleting a nonexistent timer."""
        response = client.delete("/v1/timers/nonexistent")
        assert response.status_code == 404

    def test_delete_timer_wrong_user(self, client, mock_db, mock_user):
        """Test deleting another user's timer."""
        timer_id = "test-timer-id"
        timer = MockActiveTimer(
            id=timer_id,
            user_id="other-user-id",
        )

        from utils.models.active_timer import ActiveTimer

        mock_db.set_find_by(ActiveTimer, timer, id=timer_id)

        response = client.delete(f"/v1/timers/{timer_id}")
        assert response.status_code == 403
