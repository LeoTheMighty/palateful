"""Tests the MealEventCompleted dispatch from update_meal_event (pantry-4)."""

import uuid
from unittest.mock import patch

from conftest import (
    MockMealEvent,
    MockQuery,
)


class TestMealEventCompletedDispatch:
    def test_planned_to_completed_dispatches_event(
        self, client, mock_db, mock_user
    ):
        meal_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        me = MockMealEvent(
            id=meal_id,
            status="planned",
            owner_id=str(mock_user.id),
            recipe_id=recipe_id,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, me, id=meal_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "api.v1.meal_event.update_meal_event.dispatch"
        ) as dispatch_mock:
            response = client.put(
                f"/v1/meal-events/{meal_id}",
                json={"status": "completed"},
            )

        assert response.status_code == 200
        assert dispatch_mock.called
        event_name, payload = dispatch_mock.call_args[0]
        assert event_name == "MealEventCompleted"
        assert str(payload.recipe_id) == recipe_id

    def test_completed_to_completed_does_not_dispatch(
        self, client, mock_db, mock_user
    ):
        meal_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        me = MockMealEvent(
            id=meal_id,
            status="completed",
            owner_id=str(mock_user.id),
            recipe_id=recipe_id,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, me, id=meal_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "api.v1.meal_event.update_meal_event.dispatch"
        ) as dispatch_mock:
            response = client.put(
                f"/v1/meal-events/{meal_id}",
                json={"status": "completed"},
            )

        assert response.status_code == 200
        assert not dispatch_mock.called

    def test_skipped_does_not_dispatch(self, client, mock_db, mock_user):
        meal_id = str(uuid.uuid4())
        me = MockMealEvent(
            id=meal_id,
            status="planned",
            owner_id=str(mock_user.id),
            recipe_id=str(uuid.uuid4()),
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, me, id=meal_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "api.v1.meal_event.update_meal_event.dispatch"
        ) as dispatch_mock:
            response = client.put(
                f"/v1/meal-events/{meal_id}",
                json={"status": "skipped"},
            )

        assert response.status_code == 200
        assert not dispatch_mock.called

    def test_no_recipe_does_not_dispatch(self, client, mock_db, mock_user):
        meal_id = str(uuid.uuid4())
        me = MockMealEvent(
            id=meal_id,
            status="planned",
            owner_id=str(mock_user.id),
            recipe_id=None,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, me, id=meal_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "api.v1.meal_event.update_meal_event.dispatch"
        ) as dispatch_mock:
            response = client.put(
                f"/v1/meal-events/{meal_id}",
                json={"status": "completed"},
            )

        assert response.status_code == 200
        assert not dispatch_mock.called

    def test_dispatch_failure_does_not_break_request(
        self, client, mock_db, mock_user
    ):
        meal_id = str(uuid.uuid4())
        me = MockMealEvent(
            id=meal_id,
            status="planned",
            owner_id=str(mock_user.id),
            recipe_id=str(uuid.uuid4()),
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, me, id=meal_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "api.v1.meal_event.update_meal_event.dispatch",
            side_effect=RuntimeError("kaboom"),
        ):
            response = client.put(
                f"/v1/meal-events/{meal_id}",
                json={"status": "completed"},
            )

        # Even when the hook blows up, the request still succeeds.
        assert response.status_code == 200
