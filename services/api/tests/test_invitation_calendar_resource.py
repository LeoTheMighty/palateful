"""Tests for invitation + invite-link extension to resource_type='calendar' (cal-share-1)."""

import uuid
from unittest.mock import patch

from conftest import (
    MockCalendar,
    MockCalendarUser,
    MockExecuteResult,
    MockInvitation,
    MockInviteLink,
    MockRecipeBookUser,
    MockUser,
)

CALENDAR_ID = "abc00000-0000-0000-0000-000000000001"
BOOK_ID = "b0000000-0000-0000-0000-000000000001"


# ===========================================================================
# Send invitation — calendar resource_type
# ===========================================================================


class TestSendCalendarInvitation:
    """POST /v1/invitations with resource_type='calendar'."""

    def test_send_to_user_id_success(self, client, mock_db, mock_user):
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep", owner_id=str(mock_user.id))
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),         # check_resource_permission: load calendar
            MockExecuteResult([owner_membership]), # check_resource_permission: load CalendarUser
            MockExecuteResult([target_user]),      # resolve target_user by id
            MockExecuteResult([]),                 # check_existing_membership: target not yet member
            MockExecuteResult([]),                 # duplicate invitation check
            MockExecuteResult([0]),                # rate limit count
            MockExecuteResult(["Meal Prep"]),      # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_user_id": target_user.id,
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "pending"
        assert data["resource_type"] == "calendar"
        assert data["role_offered"] == "editor"

    def test_send_to_username_success(self, client, mock_db, mock_user):
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep", owner_id=str(mock_user.id))
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Meal Prep"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 201

    def test_send_to_email_no_account(self, client, mock_db, mock_user):
        """Email-only invite (no account exists) creates invitation without to_user_id."""
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep", owner_id=str(mock_user.id))
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([]),                 # email lookup: no user matches
            MockExecuteResult([]),                 # duplicate invitation check (email branch)
            MockExecuteResult([0]),                # rate limit count
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_email": "newperson@example.com",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["to_email"] == "newperson@example.com"
        assert data["to_user_id"] is None

    def test_send_invalid_role_returns_400(self, client, mock_db, mock_user):
        """Calendar invitations only accept role 'editor'."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "viewer",  # invalid for calendar
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_send_as_editor_forbidden(self, client, mock_db, mock_user):
        """Editor (non-owner) cannot send calendar invitations."""
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        editor_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="editor"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([editor_membership]),  # only editor — should 403
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 403

    def test_send_calendar_not_found_returns_404(self, client, mock_db, mock_user):
        """Sending an invite for a non-existent calendar returns 404."""
        mock_db.db.execute.side_effect = [
            MockExecuteResult([]),  # check_resource_permission: calendar not found
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 404

    def test_send_self_invite_returns_400(self, client, mock_db, mock_user):
        """Owner inviting themselves returns 400 INVITATION_SELF_INVITE."""
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep", owner_id=str(mock_user.id))
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([mock_user]),  # username lookup → self
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": mock_user.username,
            },
        )
        assert response.status_code == 400

    def test_send_duplicate_invitation_returns_409(self, client, mock_db, mock_user):
        """Duplicate pending invitation returns 409 INVITATION_ALREADY_SENT."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        existing_inv = MockInvitation(status="pending", resource_type="calendar")
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),                # not already a member
            MockExecuteResult([existing_inv]),    # duplicate invitation found
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 409

    def test_send_already_member_returns_409(self, client, mock_db, mock_user):
        """Inviting an existing active member returns 409 INVITATION_ALREADY_MEMBER."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        target_membership = MockCalendarUser(
            user_id=target_user.id, calendar_id=CALENDAR_ID, role="editor"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([target_membership]),  # already an active member
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 409

    def test_send_re_invite_of_archived_member_succeeds(self, client, mock_db, mock_user):
        """A previously-removed (archived) member can be re-invited — archived rows are not membership."""
        from datetime import UTC, datetime
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        # check_existing_membership filters on archived_at IS NULL — an archived
        # row is invisible, so no MockExecuteResult collision: simulated by an
        # empty result for that step.
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),                  # check_existing_membership: archived row filtered
            MockExecuteResult([]),                  # duplicate invitation check
            MockExecuteResult([0]),                 # rate limit count
            MockExecuteResult(["Meal Prep"]),       # get_resource_name
        ]
        # archived_at on a "stored" row would be set, but check_existing_membership
        # is the gate — assert the invite goes through.
        _ = datetime.now(UTC)  # silence import-only lint
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_user_id": target_user.id,
            },
        )
        assert response.status_code == 201

    def test_send_includes_resource_name_in_push_data(self, client, mock_db, mock_user):
        """The INVITATION_RECEIVED push payload's data dict must include resource_name."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Meal Prep"]),
        ]
        with patch("api.v1.invitations.send_invitation.get_push_service") as mock_push:
            response = client.post(
                "/v1/invitations",
                json={
                    "resource_type": "calendar",
                    "resource_id": CALENDAR_ID,
                    "role_offered": "editor",
                    "to_username": "jane",
                },
            )
            assert response.status_code == 201
            mock_push.return_value.send_to_user.assert_called_once()
            push_arg = mock_push.return_value.send_to_user.call_args[0][1]
            assert push_arg.data["resource_name"] == "Meal Prep"
            assert push_arg.data["resource_type"] == "calendar"

    def test_rate_limit_applies_across_resource_types(self, client, mock_db, mock_user):
        """Rate limit is per-user, not per-resource — calendar invites count toward the same cap."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),                 # check_existing_membership
            MockExecuteResult([]),                 # duplicate invitation check
            MockExecuteResult([30]),               # rate limit count == cap
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
                "to_username": "jane",
            },
        )
        assert response.status_code == 429


# ===========================================================================
# Accept invitation — calendar resource_type
# ===========================================================================


class TestAcceptCalendarInvitation:
    """POST /v1/invitations/{id}/accept on a calendar invitation."""

    def test_accept_calendar_invitation_creates_membership(self, client, mock_db, mock_user):
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Leo", username="leo")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),       # fetch invitation (joinedload)
            MockExecuteResult([]),                 # create_membership: no existing CalendarUser → insert
            MockExecuteResult(["Meal Prep"]),      # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["resource_type"] == "calendar"
        assert data["role"] == "editor"

    def test_accept_when_already_active_member_is_idempotent(self, client, mock_db, mock_user):
        """If the row already exists and is active, create_membership is a no-op (idempotent)."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Leo", username="leo")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user
        active_row = MockCalendarUser(
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="editor",
            archived_at=None,
        )
        original_role = active_row.role

        mock_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),    # fetch invitation
            MockExecuteResult([active_row]),    # create_membership: existing active row
            MockExecuteResult(["Meal Prep"]),   # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        # No mutation on the row — already active.
        assert active_row.role == original_role
        assert active_row.archived_at is None

    def test_accept_re_invite_unarchives_existing_row(self, client, mock_db, mock_user):
        """Accepting a re-invite when an archived calendar_users row exists un-archives it."""
        from datetime import UTC, datetime
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Leo", username="leo")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user
        archived_row = MockCalendarUser(
            user_id=str(mock_user.id),
            calendar_id=CALENDAR_ID,
            role="editor",
            archived_at=datetime.now(UTC),
        )

        mock_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),       # fetch invitation
            MockExecuteResult([archived_row]),     # create_membership: existing archived row found
            MockExecuteResult(["Meal Prep"]),      # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        # The helper sets archived_at = None on the existing row.
        assert archived_row.archived_at is None
        assert archived_row.role == "editor"
        assert archived_row.invited_by_id == from_user.id


# ===========================================================================
# Invite-link — calendar resource_type
# ===========================================================================


class TestCalendarInviteLink:
    """Invite-link endpoints with resource_type='calendar'."""

    def test_create_link_for_calendar_success(self, client, mock_db, mock_user):
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep", owner_id=str(mock_user.id))
        owner_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([owner_membership]),
        ]
        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
            },
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["resource_type"] == "calendar"
        assert data["role_offered"] == "editor"
        assert data["deep_link"].startswith("palateful://invite/")
        assert len(data["token"]) > 0

    def test_create_link_as_editor_forbidden(self, client, mock_db, mock_user):
        calendar = MockCalendar(id=CALENDAR_ID, name="Meal Prep")
        editor_membership = MockCalendarUser(
            user_id=str(mock_user.id), calendar_id=CALENDAR_ID, role="editor"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([calendar]),
            MockExecuteResult([editor_membership]),
        ]
        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
            },
        )
        assert response.status_code == 403

    def test_create_link_calendar_not_found(self, client, mock_db, mock_user):
        mock_db.db.execute.side_effect = [
            MockExecuteResult([]),  # check_resource_permission: calendar not found
        ]
        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "calendar",
                "resource_id": CALENDAR_ID,
                "role_offered": "editor",
            },
        )
        assert response.status_code == 404

    def test_preview_calendar_link_returns_name(self, client, mock_db, mock_user):
        token = "cal-token-1234567"
        creator = MockUser(id=str(uuid.uuid4()), name="Leo", username="leo")
        link = MockInviteLink(
            token=token,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            created_by_id=str(creator.id),
            created_by=creator,
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),         # fetch link
            MockExecuteResult([]),             # check_existing_membership → not member
            MockExecuteResult(["Meal Prep"]),  # get_resource_name (calendar branch)
        ]
        response = client.get(f"/v1/invite-links/{token}")
        assert response.status_code == 200
        data = response.json()
        assert data["resource_type"] == "calendar"
        assert data["resource_name"] == "Meal Prep"
        assert data["role_offered"] == "editor"
        assert data["state"] == "active"

    def test_join_calendar_link_creates_editor_membership(self, client, mock_db, mock_user):
        token = "cal-token-7654321"
        creator = MockUser(id=str(uuid.uuid4()), name="Leo", username="leo")
        link = MockInviteLink(
            token=token,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            created_by_id=str(creator.id),
            created_by=creator,
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),         # fetch link
            MockExecuteResult([]),             # check_existing_membership → not member
            MockExecuteResult([]),             # create_membership: no existing CalendarUser
            MockExecuteResult(["Meal Prep"]),  # get_resource_name (post-create)
        ]
        response = client.post(f"/v1/invite-links/{token}/join")
        assert response.status_code == 200
        data = response.json()
        assert data["already_member"] is False
        assert data["role"] == "editor"
        assert data["resource_name"] == "Meal Prep"


# ===========================================================================
# Claim — calendar resource_type
# ===========================================================================


class TestClaimCalendarInvitations:
    """POST /v1/invitations/claim picks up calendar invites by email."""

    def test_claim_picks_up_calendar_invitations(self, client, mock_db, mock_user):
        """Claim is type-agnostic — calendar email-only invites are claimed alongside others."""
        cal_inv = MockInvitation(
            from_user_id=str(uuid.uuid4()),
            to_user_id=None,
            to_email=mock_user.email,
            resource_type="calendar",
            resource_id=CALENDAR_ID,
            role_offered="editor",
            status="pending",
        )
        book_inv = MockInvitation(
            from_user_id=str(uuid.uuid4()),
            to_user_id=None,
            to_email=mock_user.email,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )
        mock_db.db.execute.return_value = MockExecuteResult([cal_inv, book_inv])

        response = client.post("/v1/invitations/claim")
        assert response.status_code == 200
        data = response.json()
        types = sorted(item["resource_type"] for item in data)
        assert types == ["calendar", "recipe_book"]


# ===========================================================================
# Regression — non-calendar push data carries resource_name now too
# ===========================================================================


class TestPushPayloadResourceName:
    """All resource_types now include resource_name in the push data payload."""

    def test_recipe_book_push_includes_resource_name(self, client, mock_db, mock_user):
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["My Book"]),
        ]
        with patch("api.v1.invitations.send_invitation.get_push_service") as mock_push:
            response = client.post(
                "/v1/invitations",
                json={
                    "resource_type": "recipe_book",
                    "resource_id": BOOK_ID,
                    "role_offered": "editor",
                    "to_username": "jane",
                },
            )
            assert response.status_code == 201
            push_arg = mock_push.return_value.send_to_user.call_args[0][1]
            assert push_arg.data["resource_name"] == "My Book"
