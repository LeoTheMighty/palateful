"""Tests for calendar member management endpoints (cal-share-2)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from conftest import (
    MockCalendarUser,
    MockExecuteResult,
    MockInvitation,
    MockUser,
)
from sqlalchemy.exc import IntegrityError

CALENDAR_ID = "abc00000-0000-0000-0000-000000000001"


def _set_caller_owner(mock_async_db, mock_user):
    mock_async_db.set_find_by(
        MockCalendarUser.__bases__[0],
        MockCalendarUser(
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="owner",
            archived_at=None,
        ),
        user_id=str(mock_user.id),
        calendar_id=CALENDAR_ID,
    )


# Override the conftest default-allow CalendarUser find_by, which returns a
# membership for ANY (user_id, calendar_id) pair. We want to assert
# "membership exists" / "membership absent" precisely per test.
@pytest.fixture(autouse=True)
def _scoped_calendar_user(mock_async_db):
    from utils.models.calendar_user import CalendarUser as RealCalendarUser
    mock_async_db.set_find_by(
        RealCalendarUser,
        None,
    )
    yield


def _set_membership(mock_async_db, *, user_id, calendar_id, role="editor", archived_at=None):
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


# ===========================================================================
# GET /v1/calendars/{id}/members
# ===========================================================================


class TestListCalendarMembers:
    def test_non_member_returns_404(self, client, mock_async_db, mock_user):
        # No membership configured → find_by returns None
        response = client.get(f"/v1/calendars/{CALENDAR_ID}/members")
        assert response.status_code == 404

    def test_returns_active_and_pending(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")

        peer = MockUser(id=str(uuid.uuid4()), name="Jane", email="jane@example.com")
        peer_membership = MockCalendarUser(
            user_id=peer.id, calendar_id=CALENDAR_ID, role="editor"
        )
        caller_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        pending = MockInvitation(
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            to_email="newperson@example.com",
            from_user_id=str(mock_user.id),
            role_offered="editor",
            status="pending",
        )
        # Two execute() calls: (1) active (CU, User) tuples, (2) pending invites
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[
                (caller_membership, mock_user),
                (peer_membership, peer),
            ]),
            MockExecuteResult(items=[pending]),
        ]

        response = client.get(f"/v1/calendars/{CALENDAR_ID}/members")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "members" in data
        active = [m for m in data["members"] if m["status"] == "active"]
        pending_rows = [m for m in data["members"] if m["status"] == "pending"]
        assert len(active) == 2
        assert len(pending_rows) == 1
        assert pending_rows[0]["email"] == "newperson@example.com"


# ===========================================================================
# PATCH /v1/calendars/{id}/members/{user_id} — promote / role change
# ===========================================================================


class TestUpdateCalendarMember:
    def test_invalid_role_returns_400(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        target_id = str(uuid.uuid4())
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "viewer"},
        )
        assert response.status_code == 400

    def test_caller_not_member_returns_404(self, client, mock_async_db, mock_user):
        target_id = str(uuid.uuid4())
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 404

    def test_caller_is_editor_returns_403(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="editor")
        target_id = str(uuid.uuid4())
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 403

    def test_self_demote_returns_owner_transfer_required(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{mock_user.id}",
            json={"role": "editor"},
        )
        assert response.status_code == 400

    def test_target_not_a_member_returns_404(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        # target's find_by stays None (default) → 404
        target_id = str(uuid.uuid4())
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 404

    def test_promote_no_op_when_target_already_owner(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        target_id = str(uuid.uuid4())
        _set_membership(mock_async_db, user_id=target_id, calendar_id=CALENDAR_ID, role="owner")

        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "owner"

    def test_demote_target_directly_returns_owner_transfer_required(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        target_id = str(uuid.uuid4())
        _set_membership(mock_async_db, user_id=target_id, calendar_id=CALENDAR_ID, role="owner")
        # target is currently owner; changing role to "editor" is direct demote — rejected
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "editor"},
        )
        assert response.status_code == 400

    def test_promote_to_owner_transfers_atomically(self, client, mock_async_db, mock_user):
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        target_id = str(uuid.uuid4())
        caller_row = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        target_row = MockCalendarUser(
            user_id=target_id, calendar_id=CALENDAR_ID, role="editor"
        )
        mock_async_db.set_find_by(
            RealCalendarUser, caller_row,
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID,
        )
        mock_async_db.set_find_by(
            RealCalendarUser, target_row,
            user_id=target_id, calendar_id=CALENDAR_ID,
        )
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 200, response.text
        # caller demoted, target promoted
        assert caller_row.role == "editor"
        assert target_row.role == "owner"

    def test_promote_concurrent_transfer_conflict(self, client, mock_async_db, mock_user):
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        target_id = str(uuid.uuid4())
        caller_row = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        target_row = MockCalendarUser(
            user_id=target_id, calendar_id=CALENDAR_ID, role="editor"
        )
        mock_async_db.set_find_by(
            RealCalendarUser, caller_row,
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID,
        )
        mock_async_db.set_find_by(
            RealCalendarUser, target_row,
            user_id=target_id, calendar_id=CALENDAR_ID,
        )
        # Force the partial unique index to raise on flush.
        mock_async_db.db.flush.side_effect = IntegrityError("dup", {}, MagicMock())
        response = client.patch(
            f"/v1/calendars/{CALENDAR_ID}/members/{target_id}",
            json={"role": "owner"},
        )
        assert response.status_code == 409


# ===========================================================================
# DELETE /v1/calendars/{id}/members/{user_id}
# ===========================================================================


class TestRemoveCalendarMember:
    def test_caller_not_member_returns_404(self, client, mock_async_db, mock_user):
        target_id = str(uuid.uuid4())
        response = client.delete(f"/v1/calendars/{CALENDAR_ID}/members/{target_id}")
        assert response.status_code == 404

    def test_editor_cannot_remove_returns_403(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="editor")
        target_id = str(uuid.uuid4())
        response = client.delete(f"/v1/calendars/{CALENDAR_ID}/members/{target_id}")
        assert response.status_code == 403

    def test_owner_remove_self_returns_409(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        response = client.delete(
            f"/v1/calendars/{CALENDAR_ID}/members/{mock_user.id}"
        )
        assert response.status_code == 409

    def test_target_not_member_returns_404(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        # caller membership only — target's find_by stays None
        target_id = str(uuid.uuid4())
        # But our default-shared find_by returns the caller for both lookups since
        # the key is just (model.__name__,). To distinguish, set explicit per-key.
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        mock_async_db.set_find_by(
            RealCalendarUser,
            MockCalendarUser(
                user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
            ),
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID,
        )
        # Explicitly set target absent
        mock_async_db.set_find_by(
            RealCalendarUser, None,
            user_id=target_id, calendar_id=CALENDAR_ID,
        )
        response = client.delete(f"/v1/calendars/{CALENDAR_ID}/members/{target_id}")
        assert response.status_code == 404

    def test_remove_happy_path_archives_target(self, client, mock_async_db, mock_user):
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        target_id = str(uuid.uuid4())
        caller_row = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        target_row = MockCalendarUser(
            user_id=target_id, calendar_id=CALENDAR_ID, role="editor",
            last_opened_at=datetime.now(UTC),
        )
        mock_async_db.set_find_by(
            RealCalendarUser, caller_row,
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID,
        )
        mock_async_db.set_find_by(
            RealCalendarUser, target_row,
            user_id=target_id, calendar_id=CALENDAR_ID,
        )
        response = client.delete(f"/v1/calendars/{CALENDAR_ID}/members/{target_id}")
        assert response.status_code == 200
        assert target_row.archived_at is not None
        # last_opened_at is preserved on the archived row
        assert target_row.last_opened_at is not None


# ===========================================================================
# POST /v1/calendars/{id}/leave
# ===========================================================================


class TestLeaveCalendar:
    def test_not_member_returns_404(self, client, mock_async_db, mock_user):
        response = client.post(f"/v1/calendars/{CALENDAR_ID}/leave")
        assert response.status_code == 404

    def test_owner_cannot_leave_returns_409(self, client, mock_async_db, mock_user):
        _set_membership(mock_async_db, user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner")
        response = client.post(f"/v1/calendars/{CALENDAR_ID}/leave")
        assert response.status_code == 409

    def test_editor_leaves_happy_path(self, client, mock_async_db, mock_user):
        from utils.models.calendar_user import CalendarUser as RealCalendarUser
        membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="editor"
        )
        mock_async_db.set_find_by(
            RealCalendarUser, membership,
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID,
        )
        response = client.post(f"/v1/calendars/{CALENDAR_ID}/leave")
        assert response.status_code == 200
        assert membership.archived_at is not None
