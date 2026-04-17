"""Tests for AdvanceRecurrenceWindowsTask."""

import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_rule(**overrides):
    base = {
        "id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "title": "Pizza",
        "recipe_id": None,
        "meal_type": "dinner",
        "weekdays": ["fri"],
        "interval": "weekly",
        "monthly_nth": None,
        "start_date": date.today(),
        "end_date": None,
        "tz_name": "America/Los_Angeles",
        "is_shared": False,
        "materialized_through": None,
        "archived_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _database_with_rules(rules, updated_rows: int = 0):
    """Return a Database mock whose query API yields the supplied rules and
    an UPDATE that claims to have touched `updated_rows` rows."""
    db = MagicMock()

    def _query(model):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.return_value = rules
        chain.update.return_value = updated_rows
        return chain

    db.query.side_effect = _query
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    database = MagicMock()
    database.db = db
    return database


def _make_task(database):
    from utils.tasks.recurrence_tasks.advance_recurrence_windows import (
        AdvanceRecurrenceWindowsTask,
    )

    task = AdvanceRecurrenceWindowsTask()
    task.database = database
    return task


class TestAdvanceRecurrenceWindowsTask:
    def test_runs_with_no_rules(self):
        database = _database_with_rules([])
        task = _make_task(database)
        result = task.execute()
        assert result["success"] is True
        assert result["data"]["rule_count"] == 0

    def test_materializes_each_rule(self):
        r1 = _make_rule()
        r2 = _make_rule()
        database = _database_with_rules([r1, r2])
        task = _make_task(database)

        with patch(
            "utils.tasks.recurrence_tasks.advance_recurrence_windows.materialize"
        ) as mock_materialize:
            mock_materialize.return_value = [1, 2, 3]
            result = task.execute()

        assert mock_materialize.call_count == 2
        assert result["data"]["rows_touched"] == 6
        assert result["data"]["per_rule_failures"] == 0

    def test_per_rule_failure_does_not_abort_run(self):
        r1 = _make_rule()
        r2 = _make_rule()
        database = _database_with_rules([r1, r2])
        task = _make_task(database)

        calls = {"count": 0}

        def _materialize_sometimes(rule, through, db):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("boom")
            return [1]

        with patch(
            "utils.tasks.recurrence_tasks.advance_recurrence_windows.materialize",
            side_effect=_materialize_sometimes,
        ):
            result = task.execute()

        assert result["data"]["per_rule_failures"] == 1
        assert result["data"]["rows_touched"] == 1

    def test_archives_old_rows(self):
        database = _database_with_rules([], updated_rows=7)
        task = _make_task(database)

        with patch(
            "utils.tasks.recurrence_tasks.advance_recurrence_windows.materialize"
        ):
            result = task.execute()

        assert result["data"]["archived_count"] == 7
