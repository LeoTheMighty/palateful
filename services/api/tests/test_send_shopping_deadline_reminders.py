"""Tests for the deadline_reminder_task (morning shopping-deadline push).

Covers the party-mode-refined scenarios from epic-notifications-scheduled-reminders
story sched-1:

    A. 3 unchecked due-today items + user at 8:02 AM in their tz → 1 push,
       state-row `last_deadline_reminder_sent_at` set.
    B. Same list, later same morning → no 2nd push (state idempotency).
    C. All items checked → no push.
    D. Items due tomorrow → no push today.
    E. User at 9:00 AM in their tz → no push (window passed).
    F. Category-shopping disabled → suppressed (verified by
       send_to_user; handled via `send_to_user` prefs path).
    G. Two users sharing one list across tzs — each gets their own push
       at their 8:00 AM without silencing the other.

Tests operate by stubbing the task's `database` + `_candidate_timezones`,
`_users_in_timezone`, `_due_today_counts_for_user` methods so the SQL
surface is abstracted out. The logic under test is the idempotency
gate, window check, tz extraction, and per-list fan-out.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(tz="America/Denver"):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.name = "Leo"
    user.notification_preferences = {
        "push_enabled": True,
        "timezone": tz,
        "categories": {"shopping": True},
    }
    user.push_tokens = ["token-user"]
    return user


def _build_task(
    *,
    timezones,
    users_by_tz,
    list_due_counts_by_user,
    existing_state=None,
):
    """Wire up a DeadlineReminderTask with stubbed query methods.

    - `timezones`: list[str] returned from _candidate_timezones.
    - `users_by_tz`: dict[tz -> list[User]] for _users_in_timezone.
    - `list_due_counts_by_user`: dict[user_id -> dict[list_id, count]].
    - `existing_state`: dict[(user_id, list_id) -> state mock] for the
      state-row lookup.
    """
    from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
        DeadlineReminderTask,
    )

    task = DeadlineReminderTask()
    database = MagicMock()
    db = MagicMock()
    database.db = db
    task.database = database

    state_lookup = existing_state or {}

    # Stub the state-row query: db.query(state).filter_by(...).one_or_none()
    # and db.query(ShoppingList).filter_by(id=...) via find_by.
    def _fake_query(model):
        q = MagicMock()

        def _filter_by(**kwargs):
            inner = MagicMock()
            if (
                "user_id" in kwargs
                and "shopping_list_id" in kwargs
            ):
                inner.one_or_none.return_value = state_lookup.get(
                    (kwargs["user_id"], kwargs["shopping_list_id"])
                )
            else:
                inner.one_or_none.return_value = None
            return inner

        q.filter_by.side_effect = _filter_by
        return q

    db.query.side_effect = _fake_query

    # find_by returns a real-looking ShoppingList for any id lookup.
    def _fake_find_by(_model, **kwargs):
        sl = MagicMock()
        sl.id = kwargs.get("id")
        sl.name = "Weekend BBQ"
        return sl

    database.find_by.side_effect = _fake_find_by

    # Track inserts for assertions.
    task._added = []  # noqa: SLF001
    db.add.side_effect = task._added.append  # noqa: SLF001

    task._candidate_timezones = MagicMock(return_value=timezones)
    task._users_in_timezone = MagicMock(
        side_effect=lambda tz: users_by_tz.get(tz, [])
    )
    task._due_today_counts_for_user = MagicMock(
        side_effect=lambda user, tz, today: list_due_counts_by_user.get(
            user.id, {}
        )
    )
    return task, database


# Pick a fixed "now" inside the 08:02 window for America/Denver.
# UTC for Denver 2026-04-22 08:02 with DST:
#     Denver is UTC-6 in April (MDT), so 08:02 MDT == 14:02 UTC.
_NOW_DENVER_8AM = datetime(2026, 4, 22, 14, 2, tzinfo=UTC)
# 08:02 America/New_York in April (EDT, UTC-4) = 12:02 UTC.
_NOW_NY_8AM = datetime(2026, 4, 22, 12, 2, tzinfo=UTC)
# 09:00 Denver = 15:00 UTC (past the window).
_NOW_DENVER_9AM = datetime(2026, 4, 22, 15, 0, tzinfo=UTC)


def _patch_now(value):
    return patch(
        "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
        wraps=datetime,
        now=MagicMock(return_value=value),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeadlineReminderTask:

    def test_A_fires_push_and_persists_state_when_in_window(self):
        user = _make_user(tz="America/Denver")
        list_id = uuid.uuid4()

        task, database = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {list_id: 3}},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result = task.execute()

        assert result["data"]["pushes_fired"] == 1
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["item_count"] == 3
        assert call_kwargs["user"] is user

        # A new state row was added and committed.
        assert len(task._added) == 1  # noqa: SLF001
        new_state = task._added[0]  # noqa: SLF001
        assert new_state.user_id == user.id
        assert new_state.shopping_list_id == list_id
        assert new_state.last_deadline_reminder_sent_at == _NOW_DENVER_8AM
        database.db.commit.assert_called()

    def test_B_second_run_same_morning_does_not_double_push(self):
        user = _make_user(tz="America/Denver")
        list_id = uuid.uuid4()

        # Existing state says we already fired at 8:02 this morning.
        existing = MagicMock()
        existing.last_deadline_reminder_sent_at = _NOW_DENVER_8AM

        # Second run at 8:04 AM (still in the window, same day).
        run_at = _NOW_DENVER_8AM + timedelta(minutes=2)

        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {list_id: 3}},
            existing_state={(user.id, list_id): existing},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = run_at
            result = task.execute()

        assert result["data"]["pushes_fired"] == 0
        mock_notify.assert_not_called()

    def test_C_all_items_checked_yields_no_push(self):
        user = _make_user(tz="America/Denver")
        # Empty dict → no lists have due-today unchecked items.
        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {}},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result = task.execute()

        assert result["data"]["pushes_fired"] == 0
        mock_notify.assert_not_called()

    def test_D_items_due_tomorrow_yields_no_push(self):
        # Same as C from the task's perspective: the SQL filter strips
        # non-today items so the per-user count dict is empty.
        user = _make_user(tz="America/Denver")
        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {}},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result = task.execute()

        assert result["data"]["pushes_fired"] == 0
        mock_notify.assert_not_called()

    def test_empty_tzs_tick_is_a_no_op(self):
        """Most beat ticks hit no tz's window and must return cleanly."""
        task, _ = _build_task(
            timezones=[],
            users_by_tz={},
            list_due_counts_by_user={},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result = task.execute()

        assert result["data"]["pushes_fired"] == 0
        assert result["data"]["users_processed"] == 0
        assert result["data"]["errors"] == 0
        mock_notify.assert_not_called()

    def test_per_user_exception_does_not_kill_batch(self):
        """One user bombing should increment errors but not stop the loop."""
        good_user = _make_user(tz="America/Denver")
        list_id = uuid.uuid4()

        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [good_user]},
            list_due_counts_by_user={good_user.id: {list_id: 1}},
        )
        task._due_today_counts_for_user = MagicMock(  # noqa: SLF001
            side_effect=RuntimeError("boom")
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result = task.execute()

        assert result["data"]["errors"] == 1
        assert result["data"]["pushes_fired"] == 0
        mock_notify.assert_not_called()

    def test_E_out_of_window_time_yields_no_push(self):
        user = _make_user(tz="America/Denver")
        list_id = uuid.uuid4()
        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {list_id: 3}},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            # 9:00 AM Denver — past the [08:00, 08:05) window.
            mock_dt.now.return_value = _NOW_DENVER_9AM
            result = task.execute()

        assert result["data"]["pushes_fired"] == 0
        mock_notify.assert_not_called()
        # _users_in_timezone shouldn't even have been called — we drop
        # the tz immediately when the window check fails.
        task._users_in_timezone.assert_not_called()  # noqa: SLF001

    def test_F_category_disabled_suppression_is_delegated_to_send_to_user(self):
        """We don't block at the task layer — send_to_user checks prefs.

        The task fires notify_shopping_deadline_reminder unconditionally
        (when the window / due / idempotency gates pass); the push
        service then suppresses via per-category prefs. This test
        asserts the task path and trusts push_notification.py's own
        tests for the suppression logic.
        """
        user = _make_user(tz="America/Denver")
        user.notification_preferences["categories"]["shopping"] = False
        list_id = uuid.uuid4()
        task, _ = _build_task(
            timezones=["America/Denver"],
            users_by_tz={"America/Denver": [user]},
            list_due_counts_by_user={user.id: {list_id: 2}},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            task.execute()

        # We still call notify (the push service suppresses downstream).
        mock_notify.assert_called_once()

    def test_G_shared_list_two_timezones_independent_state(self):
        """Leo (MST) + Sarah (EST) share one list.

        At 14:02 UTC, only Denver is in-window — Leo should fire. At
        12:02 UTC, only New York is in-window — Sarah should fire.
        Each run creates a distinct state row keyed on (user_id, list_id).
        """
        leo = _make_user(tz="America/Denver")
        sarah = _make_user(tz="America/New_York")
        list_id = uuid.uuid4()

        # ---- Run at Sarah's morning (12:02 UTC = 8:02 EDT) ----
        task, _ = _build_task(
            timezones=["America/Denver", "America/New_York"],
            users_by_tz={
                "America/Denver": [leo],
                "America/New_York": [sarah],
            },
            list_due_counts_by_user={
                leo.id: {list_id: 2},
                sarah.id: {list_id: 2},
            },
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify,
        ):
            mock_dt.now.return_value = _NOW_NY_8AM
            result_morning_1 = task.execute()

        assert result_morning_1["data"]["pushes_fired"] == 1
        mock_notify.assert_called_once()
        only_user = mock_notify.call_args.kwargs["user"]
        assert only_user is sarah  # Denver window missed.

        # Sarah's state row should exist now; Leo's should not.
        added_user_ids = [s.user_id for s in task._added]  # noqa: SLF001
        assert added_user_ids == [sarah.id]

        # ---- Run at Leo's morning (14:02 UTC = 8:02 MDT) ----
        # Give the task a fresh state-lookup that includes Sarah's prior row.
        sarah_state = MagicMock()
        sarah_state.last_deadline_reminder_sent_at = _NOW_NY_8AM

        task2, _ = _build_task(
            timezones=["America/Denver", "America/New_York"],
            users_by_tz={
                "America/Denver": [leo],
                "America/New_York": [sarah],
            },
            list_due_counts_by_user={
                leo.id: {list_id: 2},
                sarah.id: {list_id: 2},
            },
            existing_state={(sarah.id, list_id): sarah_state},
        )

        with (
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task.datetime",
            ) as mock_dt,
            patch(
                "utils.tasks.shopping_list_tasks.deadline_reminder_task."
                "notify_shopping_deadline_reminder"
            ) as mock_notify2,
        ):
            mock_dt.now.return_value = _NOW_DENVER_8AM
            result_morning_2 = task2.execute()

        # Exactly one fire (Leo). Sarah is out of window, and her state
        # row from the prior run would suppress a 2nd fire anyway.
        assert result_morning_2["data"]["pushes_fired"] == 1
        mock_notify2.assert_called_once()
        assert mock_notify2.call_args.kwargs["user"] is leo


# ---------------------------------------------------------------------------
# Helper-level unit tests (no DB involvement)
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_tz_in_window_accepts_802(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _tz_is_in_window,
        )

        assert _tz_is_in_window("America/Denver", _NOW_DENVER_8AM) is True

    def test_tz_out_of_window_at_900(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _tz_is_in_window,
        )

        assert _tz_is_in_window("America/Denver", _NOW_DENVER_9AM) is False

    def test_tz_out_of_window_at_805(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _tz_is_in_window,
        )

        # 08:05 local is the start of the NEXT 5-min bucket → out.
        at_805 = _NOW_DENVER_8AM.replace(minute=5)
        assert _tz_is_in_window("America/Denver", at_805) is False

    def test_today_in_tz_respects_date_boundary(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _today_in_tz,
        )

        # April 22 at 08:02 UTC-6 = 14:02 UTC. Local date is April 22.
        assert _today_in_tz("America/Denver", _NOW_DENVER_8AM).isoformat() == "2026-04-22"

    def test_unknown_timezone_returns_false(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _tz_is_in_window,
        )

        assert _tz_is_in_window("Not/A/Real_Zone", _NOW_DENVER_8AM) is False

    def test_extract_user_timezone_reads_prefs(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _extract_user_timezone,
        )

        user = _make_user(tz="Europe/Paris")
        assert _extract_user_timezone(user) == "Europe/Paris"

    def test_extract_user_timezone_returns_none_when_missing(self):
        from utils.tasks.shopping_list_tasks.deadline_reminder_task import (
            _extract_user_timezone,
        )

        user = MagicMock()
        user.notification_preferences = {"push_enabled": True}
        assert _extract_user_timezone(user) is None


# Make zoneinfo import usage explicit for linters.
assert ZoneInfo("UTC") is not None
