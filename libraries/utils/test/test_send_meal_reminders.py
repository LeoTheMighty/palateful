"""Tests for the `send_meal_reminders` Celery beat task (meal-3)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils.tasks.meal_event_tasks.send_meal_reminders import (
    BEAT_WINDOW_SECONDS,
    _owner_timezone,
    _resolve_reminder_moment,
    _should_fire,
)


def _owner(tz="UTC"):
    return SimpleNamespace(
        id="owner-1",
        name="Owen",
        notification_preferences={"timezone": tz},
    )


def _event(
    *,
    scheduled_at,
    meal_type="lunch",
    meal_reminder_time=None,
    last_reminder_sent_at=None,
    status="planned",
    owner=None,
):
    return SimpleNamespace(
        id="evt-x",
        scheduled_at=scheduled_at,
        meal_type=meal_type,
        meal_reminder_time=meal_reminder_time,
        last_reminder_sent_at=last_reminder_sent_at,
        status=status,
        owner=owner or _owner(),
    )


class TestOwnerTimezone:
    def test_valid_pref_returns_zoneinfo(self):
        owner = _owner(tz="America/Los_Angeles")
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
            owner=owner,
        )
        tz = _owner_timezone(event)
        assert str(tz) == "America/Los_Angeles"

    def test_missing_pref_defaults_utc(self):
        owner = SimpleNamespace(notification_preferences=None, id="o")
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
            owner=owner,
        )
        tz = _owner_timezone(event)
        assert str(tz) == "UTC"

    def test_invalid_pref_falls_back_to_utc(self):
        owner = SimpleNamespace(
            notification_preferences={"timezone": "Not/A_Real_Zone"},
            id="o",
        )
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
            owner=owner,
        )
        tz = _owner_timezone(event)
        assert str(tz) == "UTC"


class TestResolveReminderMoment:
    def test_override_wins_over_slot_default(self):
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
            meal_type="lunch",
            meal_reminder_time=time(11, 45),
        )
        moment = _resolve_reminder_moment(event, _owner_timezone(event))
        # UTC date stays the same; reminder-time pins it.
        assert moment.hour == 11
        assert moment.minute == 45

    def test_slot_default_used_when_null(self):
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
            meal_type="dinner",
        )
        moment = _resolve_reminder_moment(event, _owner_timezone(event))
        # Dinner default is 18:30.
        assert moment.hour == 18
        assert moment.minute == 30


class TestShouldFire:
    def _build(self, now_hour=12, now_min=0, **kwargs):
        now = datetime(2026, 5, 1, now_hour, now_min, tzinfo=timezone.utc)
        window_end = now + timedelta(seconds=BEAT_WINDOW_SECONDS)
        return now, window_end

    def test_inside_window_fires(self):
        now, end = self._build(now_hour=12, now_min=0)
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, 2, tzinfo=timezone.utc),
            meal_type="lunch",
        )
        assert _should_fire(event, now, end) is True

    def test_outside_window_skips(self):
        now, end = self._build(now_hour=12, now_min=0)
        # Reminder is 6 min from now — past the 5-min window.
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, 6, tzinfo=timezone.utc),
            meal_type="lunch",
            meal_reminder_time=time(12, 6),
        )
        assert _should_fire(event, now, end) is False

    def test_terminal_status_skipped(self):
        now, end = self._build(now_hour=12, now_min=0)
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, 2, tzinfo=timezone.utc),
            status="completed",
        )
        assert _should_fire(event, now, end) is False

        event.status = "skipped"
        assert _should_fire(event, now, end) is False

    def test_already_sent_gate_dedupes(self):
        now, end = self._build(now_hour=12, now_min=0)
        event = _event(
            scheduled_at=datetime(2026, 5, 1, 12, 2, tzinfo=timezone.utc),
            meal_type="lunch",
            last_reminder_sent_at=now,  # already fired this tick
        )
        assert _should_fire(event, now, end) is False


class TestSendMealRemindersExecute:
    def _make_task(self, candidates):
        """Build a task instance with a faked database layer."""
        from utils.tasks.meal_event_tasks.send_meal_reminders import (
            SendMealRemindersTask,
        )

        task = SendMealRemindersTask()
        db = MagicMock()
        # Chainable query mock — every .filter() returns self; .all()
        # returns the passed-in candidates list.
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.return_value = candidates
        db_session = MagicMock()
        db_session.query.return_value = chain
        db.db = db_session
        db.create = MagicMock()
        task.database = db
        return task, db

    def test_calls_notify_for_in_window_events(self):
        """Use a real `now()` and schedule the event 2 min in the future
        so the window check passes. Rather than patching the `datetime`
        class (tricky — the module uses it for both .now and .combine),
        we anchor the test around the real clock."""
        now = datetime.now(timezone.utc)
        event = _event(
            scheduled_at=now + timedelta(minutes=2),
            meal_type="lunch",
            # Pin the override to the resolved minute so the wall-clock
            # lookup lands inside the 5-min window regardless of the
            # owner's default slot time.
            meal_reminder_time=(now + timedelta(minutes=2)).time().replace(second=0, microsecond=0),
        )
        task, _db = self._make_task([event])

        with patch(
            "utils.tasks.meal_event_tasks.send_meal_reminders."
            "notify_meal_event_reminder"
        ) as notify_mock:
            notify_mock.return_value = {
                "sent": 1,
                "suppressed": 0,
                "attempted": 1,
            }
            result = task.execute()

        assert result["data"]["events_fired"] == 1
        assert result["data"]["pushes_sent"] == 1
        # `last_reminder_sent_at` stamped on the event (some close-to-now value).
        assert event.last_reminder_sent_at is not None

    def test_exception_in_one_event_continues_batch(self):
        """If `notify_meal_event_reminder` raises, the row rolls back,
        an error_log is written, and the task returns the other
        events' counts without propagating."""
        now = datetime.now(timezone.utc)
        target_time = (now + timedelta(minutes=2)).time().replace(second=0, microsecond=0)
        good = _event(
            scheduled_at=now + timedelta(minutes=2),
            meal_reminder_time=target_time,
        )
        bad = _event(
            scheduled_at=now + timedelta(minutes=3),
            meal_reminder_time=target_time,
        )
        bad.id = "evt-bad"
        task, _db = self._make_task([bad, good])

        with patch(
            "utils.tasks.meal_event_tasks.send_meal_reminders."
            "notify_meal_event_reminder"
        ) as notify_mock:
            def _notify(event, **kwargs):
                if event.id == "evt-bad":
                    raise RuntimeError("boom")
                return {"sent": 1, "suppressed": 0, "attempted": 1}

            notify_mock.side_effect = _notify
            result = task.execute()

        # The good event went out; the bad one's failure was swallowed.
        assert result["data"]["pushes_sent"] == 1
        # Only the good row got its idempotency stamp.
        assert good.last_reminder_sent_at is not None
        assert bad.last_reminder_sent_at is None
