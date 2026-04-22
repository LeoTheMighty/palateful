"""Tests for meal event endpoints."""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

from conftest import (
    MockMealEvent,
    MockMealEventParticipant,
    MockQuery,
    MockRecipe,
    MockUser,
    count_queries,
)


class TestListMealEvents:
    """Tests for GET /v1/meal-events."""

    def test_list_meal_events_success(self, client, mock_db, mock_user):
        """Test listing meal events."""
        event = MockMealEvent(
            owner_id=str(mock_user.id),
            participants=[],
            recipe=None,
        )
        # ListMealEvents uses db.query(MealEvent).outerjoin(...).filter(...)
        # Returns MealEvent objects directly
        mock_db.db.query.return_value = MockQuery([event])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_meal_events_empty(self, client, mock_db, mock_user):
        """Test listing when no meal events exist."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_meal_events_eager_loads_participants_as_sibling_option(
        self, client, mock_db, mock_user
    ):
        """pbq-7 — `selectinload(MealEvent.participants)` lands as a
        SIBLING `.options()` entry alongside the existing
        `meal.components.recipe` chain (NOT nested under `.meal`).

        MockDatabase pre-populates `event.participants` so the lazy-
        load can't be reproduced; the test proves the option is wired
        by spying on the handler's `selectinload` import and asserting
        `MealEvent.participants` appears in the wrapped attribute set
        with at least one outer (non-nested) call — a regression that
        moved it under `.meal` or dropped it entirely would trip.
        """
        import api.v1.meal_event.list_meal_events as handler_module
        from utils.models.meal_event import MealEvent

        events = [
            MockMealEvent(owner_id=str(mock_user.id), participants=[], recipe=None)
            for _ in range(10)
        ]
        mock_db.db.query.return_value = MockQuery(events)

        with patch.object(
            handler_module,
            "selectinload",
            wraps=handler_module.selectinload,
        ) as spy:
            with count_queries(mock_db) as qc:
                response = client.get("/v1/meal-events")
        assert response.status_code == 200

        # Outer `selectinload(...)` was called for BOTH `MealEvent.meal`
        # (head of the chain) and `MealEvent.participants` (sibling).
        # Any nested `.selectinload(Meal.components)` call on the Load
        # object does NOT go through this spy, which is fine — we only
        # need to assert the sibling is wired.
        outer_keys = [
            getattr(call.args[0], "key", None) for call in spy.call_args_list
        ]
        assert "participants" in outer_keys
        assert "meal" in outer_keys

        # Query count on MealEvent is bounded — one LIST + one count.
        assert qc.query_count_for(MealEvent) <= 2


class TestCreateMealEvent:
    """Tests for POST /v1/meal-events."""

    def test_create_meal_event_success(self, client, mock_db, mock_user):
        """Test creating a meal event."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Sunday Dinner",
                "meal_type": "dinner",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "calendar_id": str(uuid.uuid4()),
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Sunday Dinner"
        assert data["meal_type"] == "dinner"

    def test_create_meal_event_missing_title(self, client, mock_db):
        """Test creating a meal event without title fails."""
        response = client.post(
            "/v1/meal-events",
            json={
                "meal_type": "dinner",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "calendar_id": str(uuid.uuid4()),
            }
        )
        assert response.status_code == 422

    def test_create_meal_event_missing_calendar_id(self, client, mock_db, mock_user):
        """Missing calendar_id → 400 with MEAL_EVENT_CALENDAR_REQUIRED."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Sunday Dinner",
                "meal_type": "dinner",
                "scheduled_at": datetime.now(UTC).isoformat(),
            }
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == 264

    def test_create_with_meal_reminder_time_persists_value(
        self, client, mock_db, mock_user
    ):
        """meal-1 AC 7 Test A: create with explicit meal_reminder_time →
        value reaches the row + Response, `reminder_time` echoes it."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Saturday Lunch",
                "meal_type": "lunch",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "calendar_id": str(uuid.uuid4()),
                "meal_reminder_time": "11:45",
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Pydantic serializes `time` as "HH:MM:SS".
        assert data["meal_reminder_time"].startswith("11:45")
        assert data["reminder_time"].startswith("11:45")

    def test_create_without_reminder_override_resolves_slot_default(
        self, client, mock_db, mock_user
    ):
        """meal-1 AC 7 Test B: omit meal_reminder_time → DB column stays
        null and `reminder_time` resolves to the lunch slot default."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Regular Lunch",
                "meal_type": "lunch",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "calendar_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["meal_reminder_time"] is None
        # Slot default for lunch is 12:00.
        assert data["reminder_time"].startswith("12:00")

    def test_create_with_invalid_reminder_time_string_is_422(
        self, client, mock_db, mock_user
    ):
        """meal-1 AC 7 Test D: malformed time string → 422 (Pydantic
        catches at parse time before the handler runs)."""
        response = client.post(
            "/v1/meal-events",
            json={
                "title": "Bad Input",
                "meal_type": "lunch",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "calendar_id": str(uuid.uuid4()),
                "meal_reminder_time": "not-a-time",
            },
        )
        assert response.status_code == 422


class TestGetMealEvent:
    """Tests for GET /v1/meal-events/{event_id}."""

    def test_get_meal_event_success(self, client, mock_db, mock_user):
        """Test getting a meal event."""
        event_id = "test-event-id"
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            participants=[],
            recipe=None,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id

    def test_get_meal_event_not_found(self, client, mock_db, mock_user):
        """Test getting a nonexistent meal event."""
        response = client.get("/v1/meal-events/nonexistent")
        assert response.status_code == 404


class TestDeleteMealEvent:
    """Tests for DELETE /v1/meal-events/{event_id}."""

    def test_delete_meal_event_success(self, client, mock_db, mock_user):
        """Test deleting a meal event as owner."""
        event_id = "test-event-id"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.delete(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200

    def test_delete_meal_event_not_calendar_member(self, client, mock_db, mock_user):
        """Non-member of the event's calendar → 404 (no existence leak)."""
        event_id = "test-event-id"
        event = MockMealEvent(id=event_id, owner_id="other-user-id")

        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)
        # Explicitly deny calendar membership — overrides the default
        # auto-grant in MockDatabase.find_by.
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=event.calendar_id,
        )

        response = client.delete(f"/v1/meal-events/{event_id}")
        assert response.status_code == 404


# =========================================================================
# InviteParticipant tests
# =========================================================================


class TestInviteParticipant:
    """Tests for POST /v1/meal-events/{event_id}/invite."""

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_as_owner_by_user_id(self, mock_notify, client, mock_db, mock_user):
        """Test inviting a participant as the event owner via user_id."""
        event_id = "evt-001"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id), is_shared=False)
        invited = MockUser(id="invited-user-id", email="invited@example.com", name="Invited")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        # current_participant lookup for access check (owner, so not needed)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="invited-user-id")
        # No existing participant
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="invited-user-id",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "invited-user-id", "role": "guest"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "invited-user-id"
        assert data["status"] == "invited"
        assert data["role"] == "guest"
        # is_shared should be set to True
        assert event.is_shared is True
        mock_notify.assert_called_once()

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_as_cohost(self, mock_notify, client, mock_db, mock_user):
        """Test inviting as a cohost (not owner)."""
        event_id = "evt-002"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id", is_shared=True)
        cohost_participant = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="cohost",
        )
        invited = MockUser(id="invited-user-2", email="inv2@example.com", name="Inv2")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, cohost_participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="invited-user-2")
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="invited-user-2",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "invited-user-2"},
        )
        assert response.status_code == 201

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_as_host_role(self, mock_notify, client, mock_db, mock_user):
        """Test inviting as a participant with host role (not owner)."""
        event_id = "evt-host"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id", is_shared=True)
        host_participant = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="host",
        )
        invited = MockUser(id="invited-host-user", email="invhost@example.com", name="InvHost")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, host_participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="invited-host-user")
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="invited-host-user",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "invited-host-user"},
        )
        assert response.status_code == 201

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_by_email(self, mock_notify, client, mock_db, mock_user):
        """Test inviting a participant by email instead of user_id."""
        event_id = "evt-003"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id), is_shared=False)
        invited = MockUser(id="email-user-id", email="byemail@example.com", name="EmailUser")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, email="byemail@example.com")
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="email-user-id",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"email": "byemail@example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_email"] == "byemail@example.com"

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_with_custom_message(self, mock_notify, client, mock_db, mock_user):
        """Test inviting with a custom notification message."""
        event_id = "evt-msg"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id), is_shared=False)
        invited = MockUser(id="msg-user-id", email="msg@example.com", name="MsgUser")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="msg-user-id")
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="msg-user-id",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "msg-user-id", "message": "Join us!"},
        )
        assert response.status_code == 201
        # Verify message was passed through to notification
        call_args = mock_notify.call_args
        assert call_args[0][3] == "Join us!"

    def test_invite_event_not_found(self, client, mock_db, mock_user):
        """Test inviting when event doesn't exist."""
        response = client.post(
            "/v1/meal-events/nonexistent/invite",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 404

    def test_invite_access_denied_not_owner_not_cohost(self, client, mock_db, mock_user):
        """Test inviting when user is not owner and not a cohost."""
        event_id = "evt-004"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")
        # User is a guest participant, not cohost
        guest_participant = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="guest",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, guest_participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 403

    def test_invite_access_denied_no_participant_record(self, client, mock_db, mock_user):
        """Test inviting when user is not owner and has no participant record."""
        event_id = "evt-noaccess"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 403

    def test_invite_user_not_found_by_id(self, client, mock_db, mock_user):
        """Test inviting a nonexistent user by user_id."""
        event_id = "evt-005"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        # User not found - no set_find_by for User

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "nonexistent-user"},
        )
        assert response.status_code == 404

    def test_invite_user_not_found_by_email(self, client, mock_db, mock_user):
        """Test inviting a nonexistent user by email."""
        event_id = "evt-006"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"email": "nobody@example.com"},
        )
        assert response.status_code == 404

    def test_invite_user_not_found_no_id_or_email(self, client, mock_db, mock_user):
        """Test inviting with neither user_id nor email returns user not found."""
        event_id = "evt-noid"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={},
        )
        assert response.status_code == 404

    def test_invite_already_participant(self, client, mock_db, mock_user):
        """Test inviting a user who is already a participant."""
        event_id = "evt-007"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))
        invited = MockUser(id="existing-user-id", email="existing@example.com")
        existing_participant = MockMealEventParticipant(
            meal_event_id=event_id, user_id="existing-user-id",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="existing-user-id")
        mock_db.set_find_by(
            MealEventParticipant, existing_participant,
            meal_event_id=event_id, user_id="existing-user-id",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "existing-user-id"},
        )
        assert response.status_code == 400

    @patch("api.v1.meal_event.invite_participant.notify_meal_event_invite")
    def test_invite_already_shared_event(self, mock_notify, client, mock_db, mock_user):
        """Test inviting to an already-shared event doesn't toggle is_shared again."""
        event_id = "evt-shared"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id), is_shared=True)
        invited = MockUser(id="new-inv-id", email="newinv@example.com", name="NewInv")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.user import User

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited, id="new-inv-id")
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id="new-inv-id",
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/invite",
            json={"user_id": "new-inv-id"},
        )
        assert response.status_code == 201
        # is_shared was already True, should remain True
        assert event.is_shared is True


# =========================================================================
# RespondToInvite tests
# =========================================================================


class TestRespondToInvite:
    """Tests for POST /v1/meal-events/{event_id}/respond."""

    def test_respond_accepted(self, client, mock_db, mock_user):
        """Test accepting a meal event invitation."""
        event_id = "evt-resp-1"
        event = MockMealEvent(id=event_id, owner_id="some-owner")
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id=str(mock_user.id),
            status="invited",
            role="guest",
            assigned_tasks=["bring dessert"],
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "accepted"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["user_id"] == str(mock_user.id)
        assert data["assigned_tasks"] == ["bring dessert"]

    def test_respond_declined(self, client, mock_db, mock_user):
        """Test declining a meal event invitation."""
        event_id = "evt-resp-2"
        event = MockMealEvent(id=event_id, owner_id="some-owner")
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id=str(mock_user.id),
            status="invited",
            role="guest",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "declined"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "declined"

    def test_respond_maybe(self, client, mock_db, mock_user):
        """Test responding 'maybe' to a meal event invitation."""
        event_id = "evt-resp-3"
        event = MockMealEvent(id=event_id, owner_id="some-owner")
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id=str(mock_user.id),
            status="invited",
            role="guest",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "maybe"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "maybe"

    def test_respond_invalid_status(self, client, mock_db, mock_user):
        """Test responding with an invalid status."""
        event_id = "evt-resp-4"

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 400

    def test_respond_event_not_found(self, client, mock_db, mock_user):
        """Test responding to a nonexistent event."""
        response = client.post(
            "/v1/meal-events/nonexistent/respond",
            json={"status": "accepted"},
        )
        assert response.status_code == 404

    def test_respond_not_participant(self, client, mock_db, mock_user):
        """Test responding when user is not a participant."""
        event_id = "evt-resp-5"
        event = MockMealEvent(id=event_id, owner_id="some-owner")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        # No participant record found
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "accepted"},
        )
        assert response.status_code == 404

    def test_respond_with_null_assigned_tasks(self, client, mock_db, mock_user):
        """Test responding when assigned_tasks is None (covers `or []` branch)."""
        event_id = "evt-resp-null"
        event = MockMealEvent(id=event_id, owner_id="some-owner")
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id=str(mock_user.id),
            status="invited",
            role="guest",
            assigned_tasks=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, participant,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/meal-events/{event_id}/respond",
            json={"status": "accepted"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_tasks"] == []


# =========================================================================
# SkipMealEvent tests
# =========================================================================


class TestSkipMealEvent:
    """Tests for POST /v1/meal-events/{event_id}/skip."""

    def test_skip_as_owner(self, client, mock_db, mock_user):
        """Test skipping a meal event as owner."""
        event_id = "evt-skip-1"
        event = MockMealEvent(id=event_id, owner_id=str(mock_user.id))

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(f"/v1/meal-events/{event_id}/skip")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "skipped"
        assert data["id"] == event_id

    def test_skip_as_cohost(self, client, mock_db, mock_user):
        """Test skipping as a cohost."""
        event_id = "evt-skip-2"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")
        cohost = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="cohost",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, cohost,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(f"/v1/meal-events/{event_id}/skip")
        assert response.status_code == 200
        assert event.status == "skipped"

    def test_skip_as_host_role(self, client, mock_db, mock_user):
        """Test skipping as a participant with host role."""
        event_id = "evt-skip-host"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")
        host = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="host",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, host,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(f"/v1/meal-events/{event_id}/skip")
        assert response.status_code == 200

    def test_skip_event_not_found(self, client, mock_db, mock_user):
        """Test skipping a nonexistent event."""
        response = client.post("/v1/meal-events/nonexistent/skip")
        assert response.status_code == 404

    def test_skip_access_denied_guest(self, client, mock_db, mock_user):
        """Test skipping when user is a guest (not owner/cohost)."""
        event_id = "evt-skip-3"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")
        guest = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="guest",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, guest,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(f"/v1/meal-events/{event_id}/skip")
        assert response.status_code == 403

    def test_skip_access_denied_no_participant(self, client, mock_db, mock_user):
        """Test skipping when user has no participant record and is not owner."""
        event_id = "evt-skip-4"
        event = MockMealEvent(id=event_id, owner_id="other-owner-id")

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.post(f"/v1/meal-events/{event_id}/skip")
        assert response.status_code == 403


# =========================================================================
# UpdateMealEvent tests
# =========================================================================


class TestUpdateMealEvent:
    """Tests for PUT /v1/meal-events/{event_id}."""

    def test_update_title_as_owner(self, client, mock_db, mock_user):
        """Test updating the title as the event owner."""
        event_id = "evt-upd-1"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "Updated Dinner"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Dinner"

    def test_update_meal_reminder_time_persists(
        self, client, mock_db, mock_user
    ):
        """meal-1 AC 7 Test C: update with a new reminder_time → the
        column is set and `last_reminder_sent_at` is untouched."""
        from datetime import datetime as _dt

        event_id = "evt-upd-rem-1"
        prior_sent = _dt(2026, 4, 1, 12, 0, tzinfo=UTC)
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
            meal_reminder_time=None,
            last_reminder_sent_at=prior_sent,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"meal_reminder_time": "11:45"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meal_reminder_time"].startswith("11:45")
        assert data["reminder_time"].startswith("11:45")
        # last_reminder_sent_at is internal state, not shaped into the
        # response; verify the model field wasn't reset by the handler.
        assert event.last_reminder_sent_at == prior_sent

    def test_update_meal_reminder_time_clear_via_explicit_null(
        self, client, mock_db, mock_user
    ):
        """Reset-to-default: sending `null` explicitly clears the
        override back to the slot default. (`None`-means-skip pattern
        can't do this — the endpoint uses model_fields_set to detect
        the explicit-null case.)"""
        from datetime import time as _time

        event_id = "evt-upd-rem-2"
        event = MockMealEvent(
            id=event_id,
            owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
            meal_type="lunch",
            meal_reminder_time=_time(11, 45),
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"meal_reminder_time": None},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meal_reminder_time"] is None
        assert data["reminder_time"].startswith("12:00")

    def test_update_as_cohost(self, client, mock_db, mock_user):
        """Test updating as a cohost."""
        event_id = "evt-upd-2"
        event = MockMealEvent(
            id=event_id, owner_id="other-owner",
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )
        cohost = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="cohost",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, cohost,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200

    def test_update_event_not_found(self, client, mock_db, mock_user):
        """Test updating a nonexistent event."""
        response = client.put(
            "/v1/meal-events/nonexistent",
            json={"title": "Something"},
        )
        assert response.status_code == 404

    def test_update_access_denied_guest_not_calendar_member(
        self, client, mock_db, mock_user
    ):
        """Guest-participant who is NOT a calendar member → 403. Host/cohost/guest
        no longer grants edit authorization; calendar membership does. This is the
        semantic-narrowing regression test."""
        event_id = "evt-upd-3"
        event = MockMealEvent(id=event_id, owner_id="other-owner")

        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=event.calendar_id,
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "No Permission"},
        )
        assert response.status_code == 403

    def test_update_access_denied_no_calendar_membership(
        self, client, mock_db, mock_user
    ):
        """No calendar membership → 403 on PATCH."""
        event_id = "evt-upd-noacc"
        event = MockMealEvent(id=event_id, owner_id="other-owner")

        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=event.calendar_id,
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "Nope"},
        )
        assert response.status_code == 403

    def test_update_invalid_status(self, client, mock_db, mock_user):
        """Test updating with an invalid status."""
        event_id = "evt-upd-4"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 400

    def test_update_valid_status(self, client, mock_db, mock_user):
        """Test updating with each valid status."""
        event_id = "evt-upd-status"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        for status in ["planned", "shopping", "prepping", "cooking", "completed", "skipped"]:
            response = client.put(
                f"/v1/meal-events/{event_id}",
                json={"status": status},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == status

    def test_update_invalid_meal_type(self, client, mock_db, mock_user):
        """Test updating with an invalid meal type."""
        event_id = "evt-upd-5"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"meal_type": "brunch"},
        )
        assert response.status_code == 400

    def test_update_valid_meal_types(self, client, mock_db, mock_user):
        """Test updating with each valid meal type."""
        event_id = "evt-upd-mtype"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
            response = client.put(
                f"/v1/meal-events/{event_id}",
                json={"meal_type": meal_type},
            )
            assert response.status_code == 200

    def test_update_recipe_id_valid(self, client, mock_db, mock_user):
        """Test updating with a valid recipe_id."""
        event_id = "evt-upd-6"
        recipe_id = "recipe-valid-id"
        recipe = MockRecipe(id=recipe_id, name="Pasta", description="Yummy")
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.recipe import Recipe

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"recipe_id": recipe_id},
        )
        assert response.status_code == 200
        assert event.recipe_id == recipe_id

    def test_update_recipe_id_not_found(self, client, mock_db, mock_user):
        """Test updating with a nonexistent recipe_id."""
        event_id = "evt-upd-7"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        # Recipe not found - no set_find_by for Recipe

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"recipe_id": "nonexistent-recipe"},
        )
        assert response.status_code == 404

    def test_update_all_fields(self, client, mock_db, mock_user):
        """Test updating all optional fields."""
        event_id = "evt-upd-all"
        recipe_id = "recipe-all-id"
        recipe = MockRecipe(id=recipe_id)
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant
        from utils.models.recipe import Recipe

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        scheduled_time = datetime.now(UTC).isoformat()
        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={
                "title": "Full Update",
                "description": "All fields updated",
                "scheduled_at": scheduled_time,
                "meal_type": "lunch",
                "status": "cooking",
                "recipe_id": recipe_id,
                "pantry_id": "pantry-123",
                "notify_prep_start": False,
                "prep_start_offset_minutes": 45,
                "notify_cook_start": False,
                "cook_start_offset_minutes": 15,
                "is_shared": True,
                "is_recurring": True,
                "recurrence_rule": "FREQ=WEEKLY",
                "recurrence_end_date": "2026-12-31",
            },
        )
        assert response.status_code == 200
        assert event.title == "Full Update"
        assert event.description == "All fields updated"
        assert event.meal_type == "lunch"
        assert event.status == "cooking"
        assert event.recipe_id == recipe_id
        assert event.pantry_id == "pantry-123"
        assert event.notify_prep_start is False
        assert event.prep_start_offset_minutes == 45
        assert event.notify_cook_start is False
        assert event.cook_start_offset_minutes == 15
        assert event.is_shared is True
        assert event.is_recurring is True
        assert event.recurrence_rule == "FREQ=WEEKLY"

    def test_update_with_recipe_present_in_response(self, client, mock_db, mock_user):
        """Test response includes recipe summary when recipe is attached."""
        event_id = "evt-upd-recipe-resp"
        recipe = MockRecipe(
            id="recipe-present", name="Spaghetti",
            description="Classic", prep_time=10, cook_time=20,
            image_url="https://example.com/img.jpg",
        )
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=recipe, parent_event_id=None,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "With Recipe"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recipe"] is not None
        assert data["recipe"]["name"] == "Spaghetti"
        assert data["recipe"]["prep_time"] == 10
        assert data["recipe"]["cook_time"] == 20

    def test_update_with_participants_in_response(self, client, mock_db, mock_user):
        """Test response includes participants list."""
        event_id = "evt-upd-parts"
        p_user = MockUser(id="part-user-id", email="part@example.com", name="Participant")
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id="part-user-id",
            role="guest",
            status="accepted",
            assigned_tasks=["bring salad"],
            user=p_user,
        )
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[participant], recipe=None,
            parent_event_id=None, pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "With Participants"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["participants"]) == 1
        assert data["participants"][0]["user_email"] == "part@example.com"
        assert data["participants"][0]["user_name"] == "Participant"

    def test_update_participant_with_no_user(self, client, mock_db, mock_user):
        """Test participant response when p.user is None (covers None branches)."""
        event_id = "evt-upd-nouser"
        participant = MockMealEventParticipant(
            meal_event_id=event_id,
            user_id="orphan-user-id",
            role="guest",
            status="invited",
            assigned_tasks=None,
            user=None,
        )
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[participant], recipe=None,
            parent_event_id=None, pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "No User Participant"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["participants"][0]["user_email"] is None
        assert data["participants"][0]["user_name"] is None
        assert data["participants"][0]["assigned_tasks"] == []

    def test_update_with_parent_event_id(self, client, mock_db, mock_user):
        """Test response includes parent_event_id when present."""
        event_id = "evt-upd-parent"
        parent_id = "parent-evt-id"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=parent_id,
            pantry_id=None,
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "Child Event"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parent_event_id"] == parent_id

    def test_update_with_pantry_id(self, client, mock_db, mock_user):
        """Test response includes pantry_id when present."""
        event_id = "evt-upd-pantry"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id="pantry-abc",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "Pantry Event"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pantry_id"] == "pantry-abc"

    def test_update_no_fields_changed(self, client, mock_db, mock_user):
        """Test updating with empty params (no fields changed)."""
        event_id = "evt-upd-empty"
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None, title="Original Title",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, None,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Original Title"

    def test_update_as_host_role(self, client, mock_db, mock_user):
        """Test updating as a participant with host role."""
        event_id = "evt-upd-host"
        event = MockMealEvent(
            id=event_id, owner_id="other-owner",
            participants=[], recipe=None, parent_event_id=None,
            pantry_id=None,
        )
        host = MockMealEventParticipant(
            meal_event_id=event_id, user_id=str(mock_user.id), role="host",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            MealEventParticipant, host,
            meal_event_id=event_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/meal-events/{event_id}",
            json={"title": "Host Update"},
        )
        assert response.status_code == 200


# =========================================================================
# Notification utility tests
# =========================================================================


class TestNotifyMealEventInvite:
    """Tests for notify_meal_event_invite."""

    def test_sends_notification_successfully(self):
        """Test sending invite notification when push service is available."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_invite

        meal_event = MockMealEvent(id="evt-n1", title="Pizza Night")
        invited_user = MockUser(id="inv-u1", name="Alice")
        invited_by = MockUser(id="inv-by1", name="Bob")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1, "failure_count": 0}
            mock_get.return_value = mock_service

            result = notify_meal_event_invite(meal_event, invited_user, invited_by)

        mock_service.send_to_user.assert_called_once()
        notification = mock_service.send_to_user.call_args[0][1]
        assert "Bob" in notification.body
        assert "Pizza Night" in notification.body
        assert notification.data["meal_event_id"] == str(meal_event.id)
        assert notification.data["invited_by_name"] == "Bob"

    def test_sends_with_custom_message(self):
        """Test notification body includes custom message."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_invite

        meal_event = MockMealEvent(id="evt-n2", title="Taco Tuesday")
        invited_user = MockUser(id="inv-u2")
        invited_by = MockUser(id="inv-by2", name="Chef")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_invite(
                meal_event, invited_user, invited_by, message="Bring chips!"
            )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Bring chips!" in notification.body

    def test_skips_when_not_available(self):
        """Test returns skipped result when push service is not available."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_invite

        meal_event = MockMealEvent(id="evt-n3")
        invited_user = MockUser(id="inv-u3")
        invited_by = MockUser(id="inv-by3")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_get.return_value = mock_service

            result = notify_meal_event_invite(meal_event, invited_user, invited_by)

        assert result["skipped"] == "not_configured"
        mock_service.send_to_user.assert_not_called()

    def test_invited_by_no_name(self):
        """Test notification body when invited_by has no name."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_invite

        meal_event = MockMealEvent(id="evt-n4", title="Dinner")
        invited_user = MockUser(id="inv-u4")
        invited_by = MockUser(id="inv-by4", name=None)

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_invite(meal_event, invited_user, invited_by)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Someone" in notification.body

    def test_event_no_title(self):
        """Test notification body when meal event has no title."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_invite

        meal_event = MockMealEvent(id="evt-n5", title=None)
        invited_user = MockUser(id="inv-u5")
        invited_by = MockUser(id="inv-by5", name="Chef")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_invite(meal_event, invited_user, invited_by)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "a meal event" in notification.body
        assert notification.data["meal_event_title"] == ""


class TestNotifyMealEventReminder:
    """Tests for notify_meal_event_reminder."""

    def test_sends_reminder_minutes(self):
        """Test reminder with less than 60 minutes shows minutes format."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem1", title="Lunch")
        user = MockUser(id="rem-u1")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            result = notify_meal_event_reminder(meal_event, user, 30)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "30 minutes" in notification.title
        assert notification.body == "Lunch"

    def test_sends_reminder_1_hour(self):
        """Test reminder with exactly 60 minutes shows singular hour format."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem2", title="Dinner")
        user = MockUser(id="rem-u2")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_reminder(meal_event, user, 60)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "1 hour" in notification.title
        # Should NOT have "hours" (singular)
        assert "hours" not in notification.title

    def test_sends_reminder_2_hours(self):
        """Test reminder with 120+ minutes shows plural hours format."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem3", title="Brunch")
        user = MockUser(id="rem-u3")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_reminder(meal_event, user, 120)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "2 hours" in notification.title

    def test_sends_reminder_90_minutes_as_hour(self):
        """Test reminder with 90 minutes (>= 60 but < 120) shows singular hour."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem4", title="Snack")
        user = MockUser(id="rem-u4")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_reminder(meal_event, user, 90)

        notification = mock_service.send_to_user.call_args[0][1]
        # 90 // 60 = 1, and 90 < 120, so singular
        assert "1 hour" in notification.title
        assert "hours" not in notification.title

    def test_skips_when_not_available(self):
        """Test returns skipped when push service is not available."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem5")
        user = MockUser(id="rem-u5")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_get.return_value = mock_service

            result = notify_meal_event_reminder(meal_event, user, 30)

        assert result["skipped"] == "not_configured"

    def test_event_no_title_uses_fallback(self):
        """Test reminder body fallback when event has no title."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem6", title=None)
        user = MockUser(id="rem-u6")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_reminder(meal_event, user, 15)

        notification = mock_service.send_to_user.call_args[0][1]
        assert notification.body == "Your meal event is starting soon"
        assert notification.data["meal_event_title"] == ""

    def test_reminder_data_payload(self):
        """Test reminder includes correct data payload."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_reminder

        meal_event = MockMealEvent(id="evt-rem7", title="Test Event")
        user = MockUser(id="rem-u7")

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_reminder(meal_event, user, 45)

        notification = mock_service.send_to_user.call_args[0][1]
        assert notification.data["meal_event_id"] == str(meal_event.id)
        assert notification.data["minutes_until"] == "45"
        assert notification.notification_type.value == "meal_event_reminder"


class TestNotifyMealEventUpdated:
    """Tests for notify_meal_event_updated."""

    def test_sends_to_users_excluding_updater(self):
        """Test notification is sent to users excluding the one who updated."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup1", title="Group Dinner")
        updated_by = MockUser(id="updater-id", name="Updater")
        user_a = MockUser(id="user-a-id", name="Alice")
        user_b = MockUser(id="user-b-id", name="Bob")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_users.return_value = {"success_count": 2}
            mock_get.return_value = mock_service

            result = notify_meal_event_updated(
                meal_event, updated_by, [updated_by, user_a, user_b], db_session,
            )

        mock_service.send_to_users.assert_called_once()
        recipients = mock_service.send_to_users.call_args[0][0]
        assert len(recipients) == 2
        recipient_ids = [str(u.id) for u in recipients]
        assert "updater-id" not in recipient_ids
        assert "user-a-id" in recipient_ids
        assert "user-b-id" in recipient_ids

    def test_skips_when_not_available(self):
        """Test returns skipped when push service is not available."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup2")
        updated_by = MockUser(id="updater-id")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_get.return_value = mock_service

            result = notify_meal_event_updated(
                meal_event, updated_by, [updated_by], db_session,
            )

        assert result["skipped"] == "not_configured"

    def test_no_recipients_after_filtering(self):
        """Test returns skipped when only the updater is in the user list."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup3", title="Solo Event")
        updated_by = MockUser(id="solo-updater", name="Solo")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            result = notify_meal_event_updated(
                meal_event, updated_by, [updated_by], db_session,
            )

        assert result["skipped"] == "no_recipients"
        mock_service.send_to_users.assert_not_called()

    def test_empty_users_list(self):
        """Test returns skipped when users list is empty."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup4")
        updated_by = MockUser(id="updater-empty")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            result = notify_meal_event_updated(
                meal_event, updated_by, [], db_session,
            )

        assert result["skipped"] == "no_recipients"

    def test_notification_content(self):
        """Test notification title and body content."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup5", title="Fancy Dinner")
        updated_by = MockUser(id="updater-content", name="Chef")
        other_user = MockUser(id="other-content", name="Guest")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_users.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_updated(
                meal_event, updated_by, [updated_by, other_user], db_session,
            )

        notification = mock_service.send_to_users.call_args[0][1]
        assert "Fancy Dinner" in notification.title
        assert "Chef" in notification.body
        assert notification.data["meal_event_id"] == str(meal_event.id)
        assert notification.notification_type.value == "meal_event_updated"

    def test_updated_by_no_name(self):
        """Test notification body when updater has no name."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup6", title="Event")
        updated_by = MockUser(id="updater-noname", name=None)
        other_user = MockUser(id="other-noname")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_users.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_updated(
                meal_event, updated_by, [other_user], db_session,
            )

        notification = mock_service.send_to_users.call_args[0][1]
        assert "Someone" in notification.body

    def test_event_no_title(self):
        """Test notification title fallback when event has no title."""
        from api.v1.meal_event.utils.notifications import notify_meal_event_updated

        meal_event = MockMealEvent(id="evt-nup7", title=None)
        updated_by = MockUser(id="updater-notitle", name="Chef")
        other_user = MockUser(id="other-notitle")
        db_session = MagicMock()

        with patch("api.v1.meal_event.utils.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_service.send_to_users.return_value = {"success_count": 1}
            mock_get.return_value = mock_service

            notify_meal_event_updated(
                meal_event, updated_by, [other_user], db_session,
            )

        notification = mock_service.send_to_users.call_args[0][1]
        assert "Meal event" in notification.title
        assert notification.data["meal_event_title"] == ""
