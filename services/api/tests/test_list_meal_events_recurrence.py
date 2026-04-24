"""Tests for ListMealEvents materialization hook.

aam-14: the materialize() helper is sync + takes a sync Session, so the
async handler dispatches it through `_run_materialize` (module-level
helper that `run_in_threadpool`s a fresh-SessionLocal wrapper). Tests
patch `_run_materialize` because patching `materialize` inside the
threadpool wrapper wouldn't fire under the async path (the wrapper
imports `materialize` lazily from utils.recurrence.materializer).
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from conftest import MockExecuteResult, MockMealEvent, MockModel


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
        self, client, mock_async_db, mock_user
    ):
        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            materialized_through=None,
        )
        # Execute order in ListMealEvents:
        # (1) SELECT CalendarUser.calendar_id  (scoped ids)
        # (2) SELECT MealRecurrenceRule (active rules within window)
        # (3) SELECT COUNT(*)
        # (4) SELECT MealEvent ... LIMIT (paged)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=["cal-1"]),
            MockExecuteResult(items=[rule]),
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[]),
        ]

        with patch(
            "api.v1.meal_event.list_meal_events._run_materialize",
            new_callable=AsyncMock,
        ) as mock_run:
            today = date.today()
            end = today + timedelta(days=14)
            response = client.get(
                f"/v1/meal-events?start_date={today.isoformat()}&end_date={end.isoformat()}"
            )
            assert response.status_code == 200
            assert mock_run.called

    def test_hook_skips_when_watermark_sufficient(
        self, client, mock_async_db, mock_user
    ):
        end = date.today() + timedelta(days=14)
        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            materialized_through=end + timedelta(days=30),
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=["cal-1"]),
            MockExecuteResult(items=[rule]),
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[]),
        ]

        with patch(
            "api.v1.meal_event.list_meal_events._run_materialize",
            new_callable=AsyncMock,
        ) as mock_run:
            response = client.get(
                f"/v1/meal-events?start_date={date.today().isoformat()}&end_date={end.isoformat()}"
            )
            assert response.status_code == 200
            assert not mock_run.called

    def test_list_response_includes_recurrence_rule_id(
        self, client, mock_async_db, mock_user
    ):
        rule_id = str(uuid.uuid4())
        event = MockMealEvent(
            owner_id=str(mock_user.id),
            recurrence_rule_id=rule_id,
            participants=[],
            recipe=None,
        )
        # No end_date → no rule SELECT, so only scoped_ids / count / page
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=["cal-1"]),
            MockExecuteResult(items=[1]),
            MockExecuteResult(items=[event]),
        ]

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["recurrence_rule_id"] == rule_id
