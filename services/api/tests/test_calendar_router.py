"""Tests for calendar endpoints.

Covers: CRUD happy paths, delete-last-calendar guard, non-owner rejection,
non-member 404, idempotent archive, user-provisioning hook idempotence.
"""

from datetime import UTC, datetime

from conftest import (
    MockCalendar,
    MockCalendarUser,
    MockQuery,
    MockUser,
    count_queries,
)


class TestListCalendars:
    """GET /v1/calendars."""

    def test_list_empty(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/calendars")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert "total" not in data

    def test_list_one_default(self, client, mock_db, mock_user):
        cal = MockCalendar(owner_id=str(mock_user.id), name="My Calendar", is_default=True)
        # Join result shape: (Calendar, user_role, member_count)
        mock_db.db.query.return_value = MockQuery([(cal, "owner", 1)])

        response = client.get("/v1/calendars")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "My Calendar"
        assert data["items"][0]["is_default"] is True
        assert data["items"][0]["user_role"] == "owner"
        assert data["items"][0]["member_count"] == 1

    def test_list_multiple(self, client, mock_db, mock_user):
        default_cal = MockCalendar(owner_id=str(mock_user.id), name="My Calendar", is_default=True)
        prep_cal = MockCalendar(owner_id=str(mock_user.id), name="Meal Prep", is_default=False)
        mock_db.db.query.return_value = MockQuery(
            [(default_cal, "owner", 1), (prep_cal, "owner", 1)]
        )

        response = client.get("/v1/calendars")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_list_calendars_member_count_subq_scoped_to_user(
        self, client, mock_db, mock_user
    ):
        """pbq-6 — the member-count aggregate only scans the user's
        calendar set.

        Pre-fix, the subquery aggregated every row in `calendar_users`.
        Post-fix, a leading `IN (user's calendars)` clause lets Postgres
        hit the `ix_calendar_users_calendar_id` index and aggregate a
        small per-request slice. We verify behaviourally by patching
        `Column.in_` and asserting it's invoked during request
        execution with the pre-computed list — a regression that
        dropped the scoping would skip the `.in_(...)` call entirely.
        """
        from sqlalchemy.sql.elements import ColumnClause, ColumnElement
        from utils.models.calendar_user import CalendarUser

        mock_db.db.query.return_value = MockQuery([])

        calls: list = []
        original_in_ = CalendarUser.calendar_id.__class__.in_

        def spy_in(self_col, other):
            calls.append(other)
            return original_in_(self_col, other)

        CalendarUser.calendar_id.__class__.in_ = spy_in
        try:
            with count_queries(mock_db) as qc:
                response = client.get("/v1/calendars")
        finally:
            CalendarUser.calendar_id.__class__.in_ = original_in_

        assert response.status_code == 200
        # `Column.in_(...)` fired at least once with a Python list
        # (materialized `user_calendar_ids`). Pre-fix had no such call.
        assert any(isinstance(arg, list) for arg in calls)

        # Two `db.query(CalendarUser)`-shaped calls max: one to fetch
        # the user's calendar IDs, one for the member-count subquery.
        # Main Calendar join doesn't query `CalendarUser` directly.
        assert qc.query_count_for(CalendarUser) <= 3


class TestCreateCalendar:
    """POST /v1/calendars."""

    def test_create_success(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/calendars",
            json={"name": "Meal Prep", "description": "For weekly cooking"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Meal Prep"
        assert data["description"] == "For weekly cooking"
        assert data["user_role"] == "owner"
        assert data["member_count"] == 1
        assert data["is_default"] is False
        assert data["owner_id"] == str(mock_user.id)

    def test_create_without_description(self, client, mock_db, mock_user):
        response = client.post("/v1/calendars", json={"name": "Minimal"})
        assert response.status_code == 201
        data = response.json()
        assert data["description"] is None

    def test_create_missing_name(self, client, mock_db, mock_user):
        response = client.post("/v1/calendars", json={"description": "no name"})
        assert response.status_code == 422


class TestGetCalendar:
    """GET /v1/calendars/{id}."""

    def test_get_success(self, client, mock_db, mock_user):
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        cal = MockCalendar(id=cal_id, owner_id=str(mock_user.id))
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        # The members query: (CalendarUser, User) tuples
        mock_db.db.query.return_value = MockQuery(
            [(membership, MockUser(id=mock_user.id, name="Leo"))]
        )

        response = client.get(f"/v1/calendars/{cal_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cal_id
        assert data["user_role"] == "owner"
        assert len(data["members"]) == 1
        assert data["members"][0]["role"] == "owner"

    def test_get_non_member_404(self, client, mock_db, mock_user):
        # No CalendarUser configured → find_by returns None → 404.
        response = client.get("/v1/calendars/someone-elses-id")
        assert response.status_code == 404

    def test_get_archived_membership_404(self, client, mock_db, mock_user):
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        membership = MockCalendarUser(
            user_id=str(mock_user.id),
            calendar_id=cal_id,
            archived_at=datetime.now(UTC),
        )
        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )

        response = client.get(f"/v1/calendars/{cal_id}")
        assert response.status_code == 404

    def test_get_calendar_not_found_in_db_404(self, client, mock_db, mock_user):
        """Membership exists but calendar row does not (inconsistent DB)."""
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )
        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        # Calendar NOT set → find_by returns None → 404.

        response = client.get(f"/v1/calendars/{cal_id}")
        assert response.status_code == 404


class TestUpdateCalendar:
    """PATCH /v1/calendars/{id}."""

    def test_update_owner_name(self, client, mock_db, mock_user):
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        cal = MockCalendar(id=cal_id, owner_id=str(mock_user.id), name="Original")
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        mock_db.db.query.return_value = MockQuery([1])  # member_count

        response = client.patch(
            f"/v1/calendars/{cal_id}", json={"name": "Renamed"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed"

    def test_update_owner_description(self, client, mock_db, mock_user):
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        cal = MockCalendar(id=cal_id, owner_id=str(mock_user.id))
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        mock_db.db.query.return_value = MockQuery([1])

        response = client.patch(
            f"/v1/calendars/{cal_id}", json={"description": "Weekly prep"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Weekly prep"

    def test_update_non_owner_403(self, client, mock_db, mock_user):
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="editor"
        )
        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )

        response = client.patch(
            f"/v1/calendars/{cal_id}", json={"name": "Shouldn't work"}
        )
        assert response.status_code == 403

    def test_update_non_member_404(self, client, mock_db, mock_user):
        response = client.patch(
            "/v1/calendars/not-mine", json={"name": "x"}
        )
        assert response.status_code == 404


class TestDeleteCalendar:
    """DELETE /v1/calendars/{id}."""

    def test_delete_owner_success(self, client, mock_db, mock_user):
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        cal = MockCalendar(
            id=cal_id, owner_id=str(mock_user.id), name="Meal Prep", is_default=False
        )
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        # other_active_owned_count = 1 (one other calendar exists) → allowed.
        mock_db.db.query.return_value = MockQuery([1])

        response = client.delete(f"/v1/calendars/{cal_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["already_archived"] is False
        assert cal.archived_at is not None

    def test_delete_last_calendar_forbidden(self, client, mock_db, mock_user):
        """Last calendar guard: 400 with CALENDAR_CANNOT_DELETE_LAST."""
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        cal = MockCalendar(id=cal_id, owner_id=str(mock_user.id))
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        # other_active_owned_count = 0 (no other calendars) → forbidden.
        mock_db.db.query.return_value = MockQuery([0])

        response = client.delete(f"/v1/calendars/{cal_id}")
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == 261  # CALENDAR_CANNOT_DELETE_LAST

    def test_delete_non_owner_403(self, client, mock_db, mock_user):
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-123"
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="editor"
        )
        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )

        response = client.delete(f"/v1/calendars/{cal_id}")
        assert response.status_code == 403

    def test_delete_non_member_404(self, client, mock_db, mock_user):
        response = client.delete("/v1/calendars/not-mine")
        assert response.status_code == 404

    def test_delete_already_archived_noop(self, client, mock_db, mock_user):
        """Already-archived: 200 + already_archived=True AND no duplicate audit row."""
        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser
        from utils.models.error_log import ErrorLog

        cal_id = "cal-123"
        cal = MockCalendar(
            id=cal_id,
            owner_id=str(mock_user.id),
            archived_at=datetime.now(UTC),
        )
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)

        created_objects = []
        original_create = mock_db.create

        def tracking_create(obj):
            created_objects.append(obj)
            return original_create(obj)

        mock_db.create = tracking_create

        response = client.delete(f"/v1/calendars/{cal_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["already_archived"] is True
        # No ErrorLog (audit row) should have been written on the no-op path.
        assert not any(isinstance(o, ErrorLog) for o in created_objects)

    def test_delete_default_calendar_promotes_another(self, client, mock_db, mock_user):
        """Deleting the default calendar flips is_default to another owned active calendar."""
        import uuid

        from utils.models.calendar import Calendar
        from utils.models.calendar_user import CalendarUser

        cal_id = "cal-default"
        cal = MockCalendar(
            id=cal_id, owner_id=str(mock_user.id), is_default=True, name="My Calendar"
        )
        promotion_target = MockCalendar(
            id=str(uuid.uuid4()),
            owner_id=str(mock_user.id),
            is_default=False,
            name="Meal Prep",
        )
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=cal_id, role="owner"
        )

        mock_db.set_find_by(
            CalendarUser, membership, user_id=str(mock_user.id), calendar_id=cal_id
        )
        mock_db.set_find_by(Calendar, cal, id=cal_id)
        # Query sequence:
        # 1. active_owned_count → MockQuery([1])  (one other calendar)
        # 2. meal_events bulk update  → MockQuery noop
        # 3. meal_recurrence_rules bulk update → MockQuery noop
        # 4. calendar_users bulk update → MockQuery noop
        # 5. promotion_target lookup → MockQuery([promotion_target])
        mock_db.db.query.side_effect = [
            MockQuery([1]),
            MockQuery([]),
            MockQuery([]),
            MockQuery([]),
            MockQuery([promotion_target]),
        ]

        response = client.delete(f"/v1/calendars/{cal_id}")
        assert response.status_code == 200
        # Old calendar: archived + is_default flipped off.
        assert cal.archived_at is not None
        assert cal.is_default is False
        # Promotion target: now default.
        assert promotion_target.is_default is True


class TestEnsureDefaultCalendarHook:
    """Tests for the user-provisioning hook in dependencies.py."""

    def test_ensure_default_calendar_existing_returns_same(self, mock_db, mock_user):
        """When an active default calendar exists, hook returns it (no insert)."""
        from dependencies import _ensure_default_calendar

        existing = MockCalendar(owner_id=str(mock_user.id), is_default=True)
        mock_db.db.query.return_value = MockQuery([existing])

        result = _ensure_default_calendar(mock_db, mock_user)
        assert result is existing

    def test_ensure_default_calendar_creates_when_missing(self, mock_db, mock_user):
        """No default calendar → hook creates one via SAVEPOINT."""
        from unittest.mock import MagicMock

        from dependencies import _ensure_default_calendar

        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.begin_nested = MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=None),
                __exit__=MagicMock(return_value=False),
            )
        )

        result = _ensure_default_calendar(mock_db, mock_user)
        assert result is not None
        assert result.name == "My Calendar"
        assert result.is_default is True
        assert result.owner_id == mock_user.id

    def test_ensure_default_calendar_integrity_error_retries(self, mock_db, mock_user):
        """Concurrent provisioning race: SAVEPOINT rolls back, hook re-reads."""
        from unittest.mock import MagicMock

        from sqlalchemy.exc import IntegrityError

        from dependencies import _ensure_default_calendar

        # First query (initial lookup): no default yet.
        # Second query (retry after IntegrityError): returns the row the
        # concurrent request just inserted.
        race_winner = MockCalendar(owner_id=str(mock_user.id), is_default=True)
        mock_db.db.query.side_effect = [
            MockQuery([]),        # initial lookup — empty
            MockQuery([race_winner]),  # retry lookup — finds race winner
        ]

        # SAVEPOINT context manager that raises IntegrityError on commit
        # (ON CONFLICT against the partial unique index).
        savepoint_cm = MagicMock()
        savepoint_cm.__enter__ = MagicMock(return_value=None)
        savepoint_cm.__exit__ = MagicMock(
            side_effect=IntegrityError("stmt", {}, Exception("duplicate"))
        )
        mock_db.db.begin_nested = MagicMock(return_value=savepoint_cm)

        result = _ensure_default_calendar(mock_db, mock_user)
        assert result is race_winner

    def test_ensure_default_calendar_ignores_archived_default(self, mock_db, mock_user):
        """An archived default must NOT satisfy the idempotency check — filter
        uses archived_at IS NULL, matching the partial unique index scope."""
        from unittest.mock import MagicMock

        from dependencies import _ensure_default_calendar

        # The filter excludes archived rows, so the query returns [].
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.begin_nested = MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=None),
                __exit__=MagicMock(return_value=False),
            )
        )

        result = _ensure_default_calendar(mock_db, mock_user)
        # New calendar is created rather than returning the archived one.
        assert result is not None
        assert result.archived_at is None
