"""Tests for meal-event push fan-out (meal-3 / meal-4)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils.services.meal_event_notifications import (
    notify_meal_event_reminder,
    notify_meal_event_updated,
)


def _make_user(user_id="u1", name="Alex", push_tokens=None):
    return SimpleNamespace(
        id=user_id,
        name=name,
        email=f"{user_id}@example.com",
        push_tokens=push_tokens if push_tokens is not None else ["tok"],
        notification_preferences={"push_enabled": True},
    )


def _make_participant(user, status="accepted", role="guest"):
    return SimpleNamespace(user_id=user.id, user=user, status=status, role=role)


def _make_event(
    *,
    meal_type="lunch",
    is_shared=False,
    recipe=None,
    participants=None,
    scheduled_at=None,
    title="Sat Lunch",
    owner=None,
):
    return SimpleNamespace(
        id="evt-1",
        title=title,
        meal_type=meal_type,
        is_shared=is_shared,
        recipe=recipe,
        scheduled_at=scheduled_at or datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        participants=participants or [],
        owner=owner,
        status="planned",
        meal_reminder_time=None,
        last_reminder_sent_at=None,
    )


class TestNotifyMealEventReminder:
    def test_solo_meal_one_push(self):
        """Single accepted participant → one push, no partner-body."""
        user = _make_user(user_id="u1", name="Alex")
        event = _make_event(
            is_shared=False,
            participants=[_make_participant(user)],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            result = notify_meal_event_reminder(event)

        assert result == {"sent": 1, "suppressed": 0, "attempted": 1}
        svc.send_to_user.assert_called_once()
        notification = svc.send_to_user.call_args[0][1]
        # Solo-no-recipe fallback body.
        assert "Tap to open the meal you planned." == notification.body

    def test_shared_meal_body_names_partner(self):
        """Shared meal + 2 accepted → each recipient's body names the
        OTHER participant's first name."""
        alice = _make_user("u-a", name="Alice")
        bob = _make_user("u-b", name="Bob")
        event = _make_event(
            is_shared=True,
            participants=[
                _make_participant(alice),
                _make_participant(bob),
            ],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            notify_meal_event_reminder(event)

        assert svc.send_to_user.call_count == 2
        call_args = svc.send_to_user.call_args_list
        bodies = {call[0][1].body for call in call_args}
        # Each recipient sees the OTHER's first name — exactly 2 bodies.
        assert any("Alice" in b for b in bodies)
        assert any("Bob" in b for b in bodies)

    def test_declined_participants_skipped(self):
        """Declined / invited / maybe RSVPs don't get the push."""
        accepted = _make_user("u-y", name="Yes")
        declined = _make_user("u-n", name="No")
        event = _make_event(
            is_shared=True,
            participants=[
                _make_participant(accepted, status="accepted"),
                _make_participant(declined, status="declined"),
            ],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            result = notify_meal_event_reminder(event)

        assert result["attempted"] == 1
        svc.send_to_user.assert_called_once()

    def test_owner_fallback_when_not_in_participants(self):
        """Legacy events with no participant row for the owner still get
        pushed via the owner fallback path."""
        owner = _make_user("u-owner", name="Owen")
        event = _make_event(participants=[], owner=owner)

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            notify_meal_event_reminder(event)

        svc.send_to_user.assert_called_once()

    def test_category_suppression_counted(self):
        """A recipient with meals category disabled → `suppressed`
        counter increments, not `sent`."""
        user = _make_user("u-opt-out")
        event = _make_event(participants=[_make_participant(user)])

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {
                "success_count": 0,
                "suppressed_by_category": True,
            }
            mock_get.return_value = svc

            result = notify_meal_event_reminder(event)

        assert result == {"sent": 0, "suppressed": 1, "attempted": 1}

    def test_one_exception_does_not_kill_batch(self):
        """A raise from send_to_user for one recipient shouldn't block
        the others — covered via `success_count > 0` counting logic."""
        u1 = _make_user("u1")
        u2 = _make_user("u2")
        event = _make_event(
            is_shared=True,
            participants=[_make_participant(u1), _make_participant(u2)],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()

            def _send(user, *args, **kwargs):
                if user.id == "u1":
                    raise RuntimeError("boom")
                return {"success_count": 1}

            svc.send_to_user.side_effect = _send
            mock_get.return_value = svc

            result = notify_meal_event_reminder(event)

        # One push succeeded; the exception was swallowed.
        assert result["sent"] == 1
        assert svc.send_to_user.call_count == 2

    def test_minutes_until_formatted_in_title_when_positive(self):
        """Scheduled 10 min after `now` → title reads 'Lunch in 10 — ...'."""
        recipe = SimpleNamespace(name="Carbonara", image_url="https://img/x.jpg")
        user = _make_user("u1", name="Alex")
        now = datetime(2026, 5, 1, 11, 50, tzinfo=timezone.utc)
        scheduled = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        event = _make_event(
            meal_type="lunch",
            recipe=recipe,
            scheduled_at=scheduled,
            participants=[_make_participant(user)],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            notify_meal_event_reminder(event, now=now)

        notification = svc.send_to_user.call_args[0][1]
        assert "in 10" in notification.title
        assert "Carbonara" in notification.title
        assert notification.image_url == "https://img/x.jpg"


class TestNotifyMealEventUpdated:
    def test_actor_excluded_from_fanout(self):
        """Editor doesn't notify themselves."""
        actor = _make_user("u-editor", name="Sarah")
        partner = _make_user("u-partner", name="Leo")
        event = _make_event(
            is_shared=True,
            participants=[
                _make_participant(actor),
                _make_participant(partner),
            ],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            result = notify_meal_event_updated(event, actor)

        # Only the partner gets the push.
        assert result["attempted"] == 1
        svc.send_to_user.assert_called_once()
        # Confirm we called send_to_user with the partner, not the actor.
        call_user = svc.send_to_user.call_args[0][0]
        assert call_user.id == "u-partner"

    def test_only_time_changed_uses_time_specific_copy(self):
        actor = _make_user("u-editor", name="Sarah")
        partner = _make_user("u-partner", name="Leo")
        event = _make_event(
            title="Saturday brunch",
            is_shared=True,
            participants=[
                _make_participant(actor),
                _make_participant(partner),
            ],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            notify_meal_event_updated(
                event,
                actor,
                changed_fields=["scheduled_at"],
                new_time="12:30 PM",
            )

        notification = svc.send_to_user.call_args[0][1]
        assert "moved to 12:30 PM" in notification.title
        assert "Sarah updated" in notification.body

    def test_multiple_fields_use_generic_copy(self):
        actor = _make_user("u-editor", name="Sarah")
        partner = _make_user("u-partner", name="Leo")
        event = _make_event(
            title="Brunch",
            is_shared=True,
            participants=[
                _make_participant(actor),
                _make_participant(partner),
            ],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            svc.send_to_user.return_value = {"success_count": 1}
            mock_get.return_value = svc

            notify_meal_event_updated(
                event,
                actor,
                changed_fields=["title", "scheduled_at"],
            )

        notification = svc.send_to_user.call_args[0][1]
        assert "Brunch updated" == notification.title
        assert "Sarah made changes" in notification.body

    def test_no_recipients_short_circuits(self):
        actor = _make_user("u-solo", name="Solo")
        # Only actor is in participants — fan-out is a no-op.
        event = _make_event(
            is_shared=True,
            participants=[_make_participant(actor)],
        )

        with patch(
            "utils.services.meal_event_notifications.get_push_service"
        ) as mock_get:
            svc = MagicMock()
            mock_get.return_value = svc

            result = notify_meal_event_updated(event, actor)

        assert result == {"sent": 0, "suppressed": 0, "attempted": 0}
        svc.send_to_user.assert_not_called()
