"""Tests for ListMealEvents materialization hook."""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

from conftest import MockMealEvent, MockModel, MockQuery


class MockMealRecurrenceRule(MockModel):
    """Local copy to avoid cross-test-file import issues."""

    def __init__(self, **kwargs):
        defaults = {
            "title": "Pizza Friday",
            "recipe_id": None,
            "owner_id": str(uuid.uuid4()),
            "calendar_id": str(uuid.uuid4()),
            "meal_type": "dinner",
            "weekdays": ["fri"],
            "interval": "weekly",
            "monthly_nth": None,
            "start_date": date.today(),
            "end_date": None,
            "tz_name": "America/Los_Angeles",
            "is_shared": False,
            "materialized_through": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestListMealEventsMaterializeHook:
    def test_hook_calls_materialize_when_watermark_behind(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_event import MealEvent
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            materialized_through=None,
        )

        def _query(model):
            if model is MealRecurrenceRule:
                return MockQuery([rule])
            if model is MealEvent:
                return MockQuery([])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        with patch(
            "api.v1.meal_event.list_meal_events.materialize"
        ) as mock_materialize:
            mock_materialize.return_value = []
            today = date.today()
            end = today + timedelta(days=14)
            response = client.get(
                f"/v1/meal-events?start_date={today.isoformat()}&end_date={end.isoformat()}"
            )
            assert response.status_code == 200
            assert mock_materialize.called

    def test_hook_skips_when_watermark_sufficient(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_event import MealEvent
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        end = date.today() + timedelta(days=14)
        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            materialized_through=end + timedelta(days=30),
        )

        def _query(model):
            if model is MealRecurrenceRule:
                return MockQuery([rule])
            if model is MealEvent:
                return MockQuery([])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        with patch(
            "api.v1.meal_event.list_meal_events.materialize"
        ) as mock_materialize:
            response = client.get(
                f"/v1/meal-events?start_date={date.today().isoformat()}&end_date={end.isoformat()}"
            )
            assert response.status_code == 200
            assert not mock_materialize.called

    def test_list_response_includes_recurrence_rule_id(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_event import MealEvent

        rule_id = str(uuid.uuid4())
        event = MockMealEvent(
            owner_id=str(mock_user.id),
            recurrence_rule_id=rule_id,
            participants=[],
            recipe=None,
        )

        def _query(model):
            if model is MealEvent:
                return MockQuery([event])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["recurrence_rule_id"] == rule_id
