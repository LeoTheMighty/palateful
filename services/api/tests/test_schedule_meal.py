"""Tests for meal event schedule flow (Story 9.1).

Covers create-with-recipe, date-range filtering, delete, reschedule (update),
and access control scenarios.
"""

import uuid
from datetime import UTC, datetime

from conftest import (
    MockMealEvent,
    MockMealEventParticipant,
    MockQuery,
    MockRecipe,
)


class TestCreateMealEventWithRecipe:
    """Creating a meal event with an attached recipe."""

    def test_create_meal_event_with_recipe_id_returns_recipe_summary(
        self, client, mock_db, mock_user
    ):
        """recipe_summary in response when recipe_id is valid."""
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pasta Carbonara", image_url="https://example.com/img.jpg")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Pasta Night",
                "meal_type": "dinner",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "recipe_id": recipe_id,
                "is_shared": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["recipe"] is not None
        assert data["recipe"]["id"] == recipe_id
        assert data["recipe"]["name"] == "Pasta Carbonara"
        assert data["recipe"]["image_url"] == "https://example.com/img.jpg"
        assert data["is_shared"] is True

    def test_create_meal_event_with_invalid_recipe_id_returns_404(
        self, client, mock_db, mock_user
    ):
        """Returns 404 when recipe_id does not exist."""
        invalid_id = str(uuid.uuid4())
        # Recipe not configured → find_by returns None → 404

        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Mystery Dinner",
                "meal_type": "dinner",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "recipe_id": invalid_id,
            },
        )

        assert response.status_code == 404

    def test_create_meal_event_without_recipe_id_succeeds(
        self, client, mock_db, mock_user
    ):
        """Recipe field is None in response when recipe_id is omitted."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Freeform Lunch",
                "meal_type": "lunch",
                "scheduled_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["recipe"] is None


class TestListMealEventsDateRange:
    """Date-range filtering for GET /v1/meal-events."""

    def test_list_meal_events_returns_events_in_range(
        self, client, mock_db, mock_user
    ):
        """Events within the date range are returned."""
        in_range_event = MockMealEvent(
            owner_id=str(mock_user.id),
            scheduled_at=datetime(2026, 3, 18, 19, 0, tzinfo=UTC),
            participants=[],
            recipe=None,
        )
        mock_db.db.query.return_value = MockQuery([in_range_event])

        response = client.get(
            "/v1/meal-events",
            params={"start_date": "2026-03-16", "end_date": "2026-03-22"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_meal_events_empty_range(self, client, mock_db, mock_user):
        """Returns empty list when no events in the date range."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(
            "/v1/meal-events",
            params={"start_date": "2026-01-01", "end_date": "2026-01-07"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestDeleteMealEvent:
    """DELETE /v1/meal-events/{event_id} — remove a planned meal."""

    def test_delete_meal_event_owner_succeeds(self, client, mock_db, mock_user):
        """Owner can delete their own meal event."""
        event_id = str(uuid.uuid4())
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.delete(f"/v1/meal-events/{event_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_non_owner_cannot_delete_meal_event(self, client, mock_db, mock_user):
        """Non-owner gets 403 when trying to delete."""
        event_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())
        event = MockMealEvent(id=event_id, owner_id=other_owner_id)

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.delete(f"/v1/meal-events/{event_id}")

        assert response.status_code == 403

    def test_delete_nonexistent_event_returns_404(self, client, mock_db, mock_user):
        """Returns 404 when the event does not exist."""
        response = client.delete(f"/v1/meal-events/{uuid.uuid4()}")

        assert response.status_code == 404


class TestUpdateMealEventReschedule:
    """PUT /v1/meal-events/{event_id} — reschedule a planned meal."""

    def test_update_meal_event_reschedules_date_and_type(
        self, client, mock_db, mock_user
    ):
        """Owner can reschedule event's date and meal_type."""
        event_id = str(uuid.uuid4())
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            scheduled_at=datetime(2026, 3, 18, 18, 0, tzinfo=UTC),
            meal_type="dinner",
            participants=[],
            recipe=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant,
            None,
            meal_event_id=event_id,
            user_id=str(mock_user.id),
        )

        new_date = datetime(2026, 3, 20, 12, 0, tzinfo=UTC).isoformat()
        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"scheduled_at": new_date, "meal_type": "lunch"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["meal_type"] == "lunch"

    def test_non_owner_non_cohost_cannot_update(self, client, mock_db, mock_user):
        """Non-owner with no role gets 403."""
        event_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())
        event = MockMealEvent(id=event_id, owner_id=other_owner_id)

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant,
            None,
            meal_event_id=event_id,
            user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"meal_type": "breakfast"},
        )

        assert response.status_code == 403
