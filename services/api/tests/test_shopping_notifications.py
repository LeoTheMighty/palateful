"""Tests for shopping-deadline push notification helpers + copy."""

import uuid
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(push_tokens=None, prefs=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.name = "Leo"
    user.push_tokens = push_tokens if push_tokens is not None else ["token-leo"]
    user.notification_preferences = prefs if prefs is not None else {
        "push_enabled": True,
        "timezone": "America/Denver",
        "categories": {"shopping": True, "imports": True},
    }
    return user


def _make_list(name="Weekend BBQ"):
    shopping_list = MagicMock()
    shopping_list.id = uuid.uuid4()
    shopping_list.name = name
    return shopping_list


def _make_database():
    database = MagicMock()
    database.db = MagicMock()
    return database


# ---------------------------------------------------------------------------
# notification_copy.shopping_deadline_reminder
# ---------------------------------------------------------------------------

class TestShoppingDeadlineReminderCopy:

    def test_single_item_uses_singular_noun(self):
        from utils.services.notification_copy import shopping_deadline_reminder

        title, body = shopping_deadline_reminder(
            list_name="Weekend BBQ", item_count=1
        )
        assert "1 item on Weekend BBQ is due today" in title
        assert body == "Tap to see what's left."

    def test_multiple_items_uses_plural_count(self):
        from utils.services.notification_copy import shopping_deadline_reminder

        title, body = shopping_deadline_reminder(
            list_name="Sunday Prep", item_count=5
        )
        assert "5 items on Sunday Prep are due today" in title
        assert body == "Tap to see what's left."

    def test_includes_cart_emoji(self):
        from utils.services.notification_copy import shopping_deadline_reminder

        title, _ = shopping_deadline_reminder(
            list_name="Groceries", item_count=3
        )
        assert "🛒" in title


# ---------------------------------------------------------------------------
# notification_copy.import_failed (sched-2 pre-wiring; exercises here
# because the copy lives in the same module and these are cheap tests)
# ---------------------------------------------------------------------------

class TestImportFailedCopy:

    def test_single_names_source(self):
        from utils.services.notification_copy import import_failed

        title, body = import_failed(
            source_label="epicurious.com", count=1
        )
        assert "Couldn't import from epicurious.com" in title
        assert "Tap to retry" in body
        assert "extract" in body.lower()

    def test_bulk_uses_count_not_source(self):
        from utils.services.notification_copy import import_failed

        title, body = import_failed(source_label="", count=5)
        assert "Bulk import failed" in title
        assert "5 recipes" in body
        assert "Tap to retry" in body

    def test_long_source_label_truncated(self):
        from utils.services.notification_copy import import_failed

        title, _ = import_failed(
            source_label="very-long-hostname-that-exceeds-the-limit-and-then-some.example.com",
            count=1,
        )
        assert "…" in title
        # title should be manageable length — not expecting exact count
        # but ensuring we didn't dump the entire raw hostname in.
        assert len(title) < 80


# ---------------------------------------------------------------------------
# notify_shopping_deadline_reminder
# ---------------------------------------------------------------------------

class TestNotifyShoppingDeadlineReminder:

    def test_sends_notification_with_expected_shape(self):
        from utils.services.shopping_notifications import (
            notify_shopping_deadline_reminder,
        )

        user = _make_user()
        shopping_list = _make_list(name="Weekend BBQ")
        database = _make_database()

        with patch(
            "utils.services.shopping_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_shopping_deadline_reminder(
                database, user=user, shopping_list=shopping_list, item_count=3
            )

        mock_service.send_to_user.assert_called_once()
        notification = mock_service.send_to_user.call_args[0][1]
        assert (
            notification.notification_type.value == "shopping_deadline_reminder"
        )
        assert "Weekend BBQ" in notification.title
        assert notification.data["shopping_list_id"] == str(shopping_list.id)
        assert notification.data["item_count"] == "3"

    def test_skips_when_push_service_unavailable(self):
        from utils.services.shopping_notifications import (
            notify_shopping_deadline_reminder,
        )

        user = _make_user()
        shopping_list = _make_list()
        database = _make_database()

        with patch(
            "utils.services.shopping_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_get.return_value = mock_service

            notify_shopping_deadline_reminder(
                database,
                user=user,
                shopping_list=shopping_list,
                item_count=2,
            )

        mock_service.send_to_user.assert_not_called()

    def test_swallows_unexpected_exceptions(self):
        from utils.services.shopping_notifications import (
            notify_shopping_deadline_reminder,
        )

        user = _make_user()
        shopping_list = _make_list()
        database = _make_database()

        with patch(
            "utils.services.shopping_notifications.get_push_service",
            side_effect=RuntimeError("boom"),
        ):
            # Must not raise.
            notify_shopping_deadline_reminder(
                database,
                user=user,
                shopping_list=shopping_list,
                item_count=1,
            )

    def test_uses_fallback_name_when_list_name_is_null(self):
        from utils.services.shopping_notifications import (
            notify_shopping_deadline_reminder,
        )

        user = _make_user()
        shopping_list = _make_list(name=None)
        database = _make_database()

        with patch(
            "utils.services.shopping_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_shopping_deadline_reminder(
                database,
                user=user,
                shopping_list=shopping_list,
                item_count=2,
            )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "your shopping list" in notification.title
