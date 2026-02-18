"""Tests for meal event endpoints."""

from datetime import date

from conftest import (
    MockMealEvent,
    MockMealEventParticipant,
    MockQuery,
    MockUser,
)


class TestListMealEvents:
    """Tests for GET /v1/meal-events."""

    def test_list_meal_events_success(self, client, mock_db, mock_user):
        """Test listing meal events."""
        event = MockMealEvent(owner_id=str(mock_user.id))
        participant = MockMealEventParticipant(
            meal_event_id=str(event.id),
            user_id=str(mock_user.id),
        )
        mock_db.db.query.return_value = MockQuery([(event, participant)])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200

    def test_list_meal_events_empty(self, client, mock_db, mock_user):
        """Test listing when no meal events exist."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200


class TestCreateMealEvent:
    """Tests for POST /v1/meal-events."""

    def test_create_meal_event_success(self, client, mock_db, mock_user):
        """Test creating a meal event."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Sunday Dinner",
                "meal_type": "dinner",
                "event_date": str(date.today()),
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Sunday Dinner"
        assert data["meal_type"] == "dinner"

    def test_create_meal_event_missing_title(self, client, mock_db):
        """Test creating a meal event without title fails."""
        response = client.post(
            "/v1/meal-events",
            json={"meal_type": "dinner", "event_date": str(date.today())}
        )
        assert response.status_code == 422


class TestGetMealEvent:
    """Tests for GET /v1/meal-events/{event_id}."""

    def test_get_meal_event_success(self, client, mock_db, mock_user):
        """Test getting a meal event."""
        event_id = "test-event-id"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id=str(mock_user.id),
            role="host",
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.db.query.return_value = MockQuery([(participant, mock_user)])

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id

    def test_get_meal_event_not_found(self, client, mock_db, mock_user):
        """Test getting a nonexistent meal event."""
        response = client.get("/v1/meal-events/nonexistent")
        assert response.status_code == 404


class TestDeleteMealEvent:
    """Tests for DELETE /v1/meal-events/{event_id}."""

    def test_delete_meal_event_success(self, client, mock_db, mock_user):
        """Test deleting a meal event as owner."""
        event_id = "test-event-id"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.delete(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200

    def test_delete_meal_event_not_owner(self, client, mock_db, mock_user):
        """Test deleting a meal event you don't own."""
        event_id = "test-event-id"
        event = MockMealEvent(id=event_id, owner_id="other-user-id")

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.delete(f"/v1/meal-events/{event_id}")
        assert response.status_code == 403
