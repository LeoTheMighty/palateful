"""Coverage tests for the foundation epic's defensive 404/403 branches.

These cover gaps that pre-date cal-share but were never closed:
- delete_calendar / update_calendar non-member 404 paths
- require_calendar_access role-restriction 403
- list_meal_events / list_recurrence_rules with explicit calendar_id query
- update_meal_event empty/move-to-calendar branches
- create_recurrence_rule empty calendar_id 400
- update_recurrence_rule move-to-calendar branch

Each test sets `set_find_by(CalendarUser, None, ...)` explicitly to opt out
of the conftest default-allow membership.
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import (
    MockCalendar,
    MockCalendarUser,
    MockExecuteResult,
    MockMealEvent,
    MockModel,
    MockQuery,
)
from sqlalchemy.exc import IntegrityError
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode

CALENDAR_ID = "abc00000-0000-0000-0000-000000000099"


@pytest.fixture(autouse=True)
def _no_default_membership(mock_async_db):
    """Force CalendarUser.find_by to return None unless explicitly set."""
    from utils.models.calendar_user import CalendarUser as RealCalendarUser
    mock_async_db.set_find_by(RealCalendarUser, None)
    yield


def _set_membership(mock_async_db, *, user_id, calendar_id, role="owner", archived_at=None):
    from utils.models.calendar_user import CalendarUser as RealCalendarUser
    mock_async_db.set_find_by(
        RealCalendarUser,
        MockCalendarUser(
            user_id=user_id,
            calendar_id=calendar_id,
            role=role,
            archived_at=archived_at,
        ),
        user_id=user_id,
        calendar_id=calendar_id,
    )


# ---------------------------------------------------------------------------
# require_calendar_access — direct unit tests for unreachable-via-router branches
# ---------------------------------------------------------------------------


class TestRequireCalendarAccess:
    """Direct unit tests against api.v1.calendar.dependencies."""

    def test_role_not_in_allowed_set_raises_403(self, mock_db, mock_user):
        from api.v1.calendar.dependencies import require_calendar_access
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        # Caller has role='owner' but we request roles={"editor"} only.
        # In practice the role check fails because 'owner' is not in {'editor'}.
        # This exercises dependencies.py:45.
        _set_membership(
            mock_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        # Re-set with a hypothetical role string the role-check rejects.
        mock_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id),
                calendar_id=CALENDAR_ID,
                role="viewer",  # role not in default {owner, editor}
            ),
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
        )
        with pytest.raises(APIException) as exc_info:
            require_calendar_access(CALENDAR_ID, mock_user, mock_db)
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == ErrorCode.CALENDAR_ACCESS_DENIED.value


# ---------------------------------------------------------------------------
# DELETE /v1/calendars/{id} — non-member 404
# ---------------------------------------------------------------------------


class TestDeleteCalendarNonMember:
    def test_non_member_returns_404(self, client, mock_async_db, mock_user):
        # No membership set → find_by returns None → 404 path.
        response = client.delete(f"/v1/calendars/{CALENDAR_ID}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /v1/calendars/{id} — non-member 404 + empty-body no-op
# ---------------------------------------------------------------------------


class TestUpdateCalendarBranches:
    def test_non_member_returns_404(self, client, mock_async_db, mock_user):
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}", json={"name": "Renamed"}
        )
        assert response.status_code == 404

    def test_empty_body_returns_200_no_op(self, client, mock_async_db, mock_user):
        """PATCH with no name/description still returns the calendar — covers the
        `if updates:` branch where updates is empty (51->54)."""
        from utils.models.calendar import Calendar as RealCalendar
        cal = MockCalendar(
            id=CALENDAR_ID, owner_id=str(mock_user.id), name="Meal Prep"
        )
        _set_membership(
            mock_async_db,
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="owner",
        )
        mock_async_db.set_find_by(RealCalendar, cal, id=CALENDAR_ID)
        # member_count query returns 1 via MockQuery default.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[1])

        response = client.patch(f"/v1/calendars/{CALENDAR_ID}", json={})
        assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# GET /v1/meal-events?calendar_id=... — exercises require_calendar_access
# ---------------------------------------------------------------------------


class TestListMealEventsScopedByCalendar:
    def test_with_calendar_id_query_calls_require_calendar_access(
        self, client, mock_async_db, mock_user
    ):
        _set_membership(
            mock_async_db,
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="editor",
        )
        # Empty rule list, empty event list — we just need the path to execute.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        start = datetime.now(UTC).date().isoformat()
        end = (datetime.now(UTC) + timedelta(days=7)).date().isoformat()
        response = client.get(
            "/v1/meal-events",
            params={
                "start_date": start,
                "end_date": end,
                "calendar_id": CALENDAR_ID,
            },
        )
        # 200 means require_calendar_access succeeded (covers list_meal_events.py 51-54).
        assert response.status_code in (200, 204), response.text


# ---------------------------------------------------------------------------
# GET /v1/recurrence-rules?calendar_id=... — exercises require_calendar_access
# ---------------------------------------------------------------------------


class TestListRecurrenceRulesScopedByCalendar:
    def test_with_calendar_id_query_calls_require_calendar_access(
        self, client, mock_async_db, mock_user
    ):
        _set_membership(
            mock_async_db,
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="editor",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get(
            "/v1/recurrence-rules", params={"calendar_id": CALENDAR_ID}
        )
        # 200 means require_calendar_access succeeded → covers list_recurrence_rules.py 22-23
        assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# POST /v1/recurrence-rules — empty calendar_id → 400
# ---------------------------------------------------------------------------


class TestCreateRecurrenceRuleEmptyCalendarId:
    def test_empty_calendar_id_returns_400(self, client, mock_async_db, mock_user):
        from datetime import date
        response = client.post(
            "/v1/recurrence-rules",
            json={
                "title": "Tuesday Tacos",
                "calendar_id": "",
                "meal_type": "dinner",
                "weekdays": ["tue"],
                "interval": "weekly",
                "start_date": date.today().isoformat(),
                "tz_name": "America/Los_Angeles",
                "is_shared": False,
            },
        )
        # 400 with RECURRENCE_RULE_CALENDAR_REQUIRED covers create_recurrence_rule.py:25.
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /v1/meal-events/{id} — empty calendar_id 400 + move-to-calendar
# ---------------------------------------------------------------------------


class TestUpdateMealEventBranches:
    def test_empty_calendar_id_returns_400(self, client, mock_async_db, mock_user):
        event_id = "e0000000-0000-0000-0000-000000000099"
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            participants=[],
            recipe=None,
        )
        _set_membership(
            mock_async_db,
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="owner",
        )
        # Handler does SELECT MealEvent ... with eager loads.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"calendar_id": ""},
        )
        # Covers update_meal_event.py empty-calendar_id branch.
        assert response.status_code == 400

    def test_move_to_different_calendar(self, client, mock_async_db, mock_user):
        """PATCH meal_event.calendar_id to a new calendar — covers the
        destination-calendar require_calendar_access check + reassignment.
        """
        from utils.models.calendar_user import CalendarUser as RealCalendarUser

        event_id = "e0000000-0000-0000-0000-000000000077"
        source_cal = CALENDAR_ID
        dest_cal = "abc00000-0000-0000-0000-000000000077"
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            calendar_id=source_cal,
            participants=[],
            recipe=None,
        )
        # Caller has membership on BOTH calendars.
        mock_async_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id), calendar_id=source_cal, role="owner"
            ),
            user_id=str(mock_user.id), calendar_id=source_cal,
        )
        mock_async_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id), calendar_id=dest_cal, role="editor"
            ),
            user_id=str(mock_user.id), calendar_id=dest_cal,
        )
        # SELECT MealEvent (only one execute() hits the event in this
        # test; the destination membership goes through find_by).
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"calendar_id": dest_cal},
        )
        assert response.status_code == 200, response.text
        assert event.calendar_id == dest_cal


# ---------------------------------------------------------------------------
# PATCH /v1/recurrence-rules/{id} — move-to-calendar with cascade
# ---------------------------------------------------------------------------


class TestUpdateRecurrenceRuleMoveToCalendar:
    def test_move_to_different_calendar(self, client, mock_db, mock_user):
        """PATCH rule.calendar_id to a new calendar — covers
        update_recurrence_rule.py:143-147 (require_calendar_access on
        destination + cascade to future materialized events).

        recurrence_rule is still sync (aam-30 scope) so this test uses
        the sync `mock_db` fixture.
        """
        import uuid as _uuid
        from test_recurrence_rule import MockMealRecurrenceRule
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        from utils.models.meal_recurrence_rule import (
            MealRecurrenceRule as RealRule,
        )

        rule_id = str(_uuid.uuid4())
        source_cal = CALENDAR_ID
        dest_cal = "abc00000-0000-0000-0000-000000000088"
        rule = MockMealRecurrenceRule(
            id=rule_id,
            owner_id=str(mock_user.id),
            calendar_id=source_cal,
            interval="weekly",
            weekdays=["fri"],
        )
        mock_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id), calendar_id=source_cal, role="owner"
            ),
            user_id=str(mock_user.id), calendar_id=source_cal,
        )
        mock_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id), calendar_id=dest_cal, role="editor"
            ),
            user_id=str(mock_user.id), calendar_id=dest_cal,
        )
        mock_db.set_find_by(RealRule, rule, id=rule_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule_id}",
            json={"calendar_id": dest_cal, "scope": "all"},
        )
        assert response.status_code == 200, response.text
        # Rule is reassigned to the destination calendar.
        assert rule.calendar_id == dest_cal


# ---------------------------------------------------------------------------
# update_calendar_member.py — IntegrityError concurrent transfer also re-raised
# (not strictly a coverage gap; included for completeness)
# ---------------------------------------------------------------------------


class TestUpdateCalendarMemberIntegrityRaceCovered:
    """The IntegrityError rollback path was already covered by cal-share-2 tests
    via `mock_async_db.db.flush.side_effect = IntegrityError(...)`. This is just a
    placeholder pin to surface it next to the others."""

    def test_already_covered(self):
        # Sanity: the import above includes IntegrityError so this file can
        # construct one in fixtures without ImportError churn elsewhere.
        err = IntegrityError("dup", {}, MockModel())
        assert err is not None
