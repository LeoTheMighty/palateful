"""Tests for recipe book push notification helpers."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(push_tokens=None, prefs=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.name = "Alice"
    user.push_tokens = push_tokens if push_tokens is not None else ["token-alice"]
    user.notification_preferences = prefs if prefs is not None else {
        "push_enabled": True,
        "partner_activity": True,
    }
    return user


def _make_membership(user_id, recipe_book_id):
    m = MagicMock()
    m.user_id = user_id
    m.recipe_book_id = recipe_book_id
    m.archived_at = None
    return m


def _make_database(members=None, users=None):
    """Return a mock Database with a mock db session."""
    database = MagicMock()
    db = MagicMock()
    database.db = db

    # Default chained query for RecipeBookUser members
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = members or []
    db.query.return_value = q

    return database


# ---------------------------------------------------------------------------
# Test notify_book_shared
# ---------------------------------------------------------------------------

class TestNotifyBookShared:

    def test_sends_notification_to_invited_user(self):
        from api.v1.recipe_book.notifications import notify_book_shared

        invited_user = _make_user()
        inviter = _make_user()
        database = _make_database()

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_book_shared(
                recipe_book_id="b-001",
                recipe_book_name="Family Recipes",
                invited_user=invited_user,
                invited_by=inviter,
                database=database,
            )

        mock_service.send_to_user.assert_called_once()
        notification = mock_service.send_to_user.call_args[0][1]
        assert notification.notification_type.value == "recipe_book_shared"
        assert "Family Recipes" in notification.body or "Family Recipes" in notification.title
        assert notification.data["recipe_book_id"] == "b-001"

    def test_skips_when_partner_activity_disabled(self):
        from api.v1.recipe_book.notifications import notify_book_shared

        invited_user = _make_user(prefs={
            "push_enabled": True,
            "partner_activity": False,
        })
        inviter = _make_user()
        database = _make_database()

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            result = notify_book_shared(
                recipe_book_id="b-002",
                recipe_book_name="My Book",
                invited_user=invited_user,
                invited_by=inviter,
                database=database,
            )

        mock_service.send_to_user.assert_not_called()
        assert result.get("skipped") == "category_disabled"

    def test_skips_when_no_push_service(self):
        from api.v1.recipe_book.notifications import notify_book_shared

        invited_user = _make_user()
        inviter = _make_user()
        database = _make_database()

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_service.send_to_user.return_value = {"success_count": 0, "failure_count": 0, "cleaned_tokens": 0}
            mock_get.return_value = mock_service

            # Should not raise
            notify_book_shared(
                recipe_book_id="b-003",
                recipe_book_name="My Book",
                invited_user=invited_user,
                invited_by=inviter,
                database=database,
            )

    def test_invited_by_name_in_notification_body(self):
        from api.v1.recipe_book.notifications import notify_book_shared

        invited_user = _make_user()
        inviter = _make_user()
        inviter.name = "Bob"
        database = _make_database()

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_book_shared(
                recipe_book_id="b-004",
                recipe_book_name="Shared Recipes",
                invited_user=invited_user,
                invited_by=inviter,
                database=database,
            )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Bob" in notification.body


# ---------------------------------------------------------------------------
# Test notify_recipe_added
# ---------------------------------------------------------------------------

class TestNotifyRecipeAdded:

    def test_sends_to_members_excluding_actor(self):
        from api.v1.recipe_book.notifications import notify_recipe_added

        actor = _make_user()
        member_a = _make_user()
        member_b = _make_user()
        book_id = str(uuid.uuid4())

        membership_actor = _make_membership(actor.id, book_id)
        membership_a = _make_membership(member_a.id, book_id)
        membership_b = _make_membership(member_b.id, book_id)

        database = MagicMock()
        db = MagicMock()
        database.db = db

        # First query: RecipeBookUser members
        member_query = MagicMock()
        member_query.filter.return_value = member_query
        member_query.all.return_value = [membership_actor, membership_a, membership_b]

        # Second query: User objects
        user_query = MagicMock()
        user_query.filter.return_value = user_query
        user_query.all.return_value = [member_a, member_b]

        db.query.side_effect = [member_query, user_query]

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_recipe_added(
                recipe_book_id=book_id,
                recipe_book_name="Our Recipes",
                recipe_name="Pasta Carbonara",
                added_by_user=actor,
                database=database,
            )

        mock_service.send_to_users.assert_called_once()
        recipients = mock_service.send_to_users.call_args[0][0]
        assert actor not in recipients
        assert member_a in recipients
        assert member_b in recipients

    def test_recipe_name_in_notification(self):
        from api.v1.recipe_book.notifications import notify_recipe_added

        actor = _make_user()
        member = _make_user()
        book_id = str(uuid.uuid4())

        membership_a = _make_membership(actor.id, book_id)
        membership_m = _make_membership(member.id, book_id)

        database = MagicMock()
        db = MagicMock()
        database.db = db

        member_query = MagicMock()
        member_query.filter.return_value = member_query
        member_query.all.return_value = [membership_a, membership_m]

        user_query = MagicMock()
        user_query.filter.return_value = user_query
        user_query.all.return_value = [member]

        db.query.side_effect = [member_query, user_query]

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_recipe_added(
                recipe_book_id=book_id,
                recipe_book_name="Family Recipes",
                recipe_name="Tiramisu",
                added_by_user=actor,
                database=database,
            )

        notification = mock_service.send_to_users.call_args[0][1]
        assert "Tiramisu" in notification.body or "Tiramisu" in notification.title
        assert notification.notification_type.value == "recipe_added"

    def test_skips_members_with_partner_activity_disabled(self):
        from api.v1.recipe_book.notifications import notify_recipe_added

        actor = _make_user()
        opted_out = _make_user(prefs={"push_enabled": True, "partner_activity": False})
        opted_in = _make_user(prefs={"push_enabled": True, "partner_activity": True})
        book_id = str(uuid.uuid4())

        membership_a = _make_membership(actor.id, book_id)
        membership_o = _make_membership(opted_out.id, book_id)
        membership_i = _make_membership(opted_in.id, book_id)

        database = MagicMock()
        db = MagicMock()
        database.db = db

        member_query = MagicMock()
        member_query.filter.return_value = member_query
        member_query.all.return_value = [membership_a, membership_o, membership_i]

        user_query = MagicMock()
        user_query.filter.return_value = user_query
        user_query.all.return_value = [opted_out, opted_in]

        db.query.side_effect = [member_query, user_query]

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_recipe_added(
                recipe_book_id=book_id,
                recipe_book_name="Test Book",
                recipe_name="Pizza",
                added_by_user=actor,
                database=database,
            )

        recipients = mock_service.send_to_users.call_args[0][0]
        assert opted_out not in recipients
        assert opted_in in recipients

    def test_no_recipients_returns_gracefully(self):
        from api.v1.recipe_book.notifications import notify_recipe_added

        actor = _make_user()
        book_id = str(uuid.uuid4())
        membership_actor = _make_membership(actor.id, book_id)

        database = MagicMock()
        db = MagicMock()
        database.db = db

        member_query = MagicMock()
        member_query.filter.return_value = member_query
        member_query.all.return_value = [membership_actor]

        db.query.return_value = member_query

        with patch("api.v1.recipe_book.notifications.get_push_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            result = notify_recipe_added(
                recipe_book_id=book_id,
                recipe_book_name="Solo Book",
                recipe_name="Soup",
                added_by_user=actor,
                database=database,
            )

        mock_service.send_to_users.assert_not_called()
        assert result.get("skipped") == "no_recipients"


# ---------------------------------------------------------------------------
# Test partner_activity preference in UpdateNotificationPreferences
# ---------------------------------------------------------------------------

class TestPartnerActivityPreference:

    def test_update_partner_activity_false(self):
        from api.v1.user.push_tokens import UpdateNotificationPreferences

        user = MagicMock()
        user.notification_preferences = {"push_enabled": True, "partner_activity": True}

        db = MagicMock()
        database = MagicMock()
        database.db = db

        endpoint = UpdateNotificationPreferences(user=user, database=database)
        params = UpdateNotificationPreferences.Params(partner_activity=False)
        result = endpoint.execute(params=params)

        assert user.notification_preferences["partner_activity"] is False
        db.commit.assert_called_once()

    def test_update_partner_activity_true(self):
        from api.v1.user.push_tokens import UpdateNotificationPreferences

        user = MagicMock()
        user.notification_preferences = {"push_enabled": True, "partner_activity": False}

        db = MagicMock()
        database = MagicMock()
        database.db = db

        endpoint = UpdateNotificationPreferences(user=user, database=database)
        params = UpdateNotificationPreferences.Params(partner_activity=True)
        result = endpoint.execute(params=params)

        assert user.notification_preferences["partner_activity"] is True

    def test_get_partner_activity_defaults_true_when_missing(self):
        from api.v1.user.push_tokens import GetNotificationPreferences

        user = MagicMock()
        user.notification_preferences = {}
        user.push_tokens = []

        endpoint = GetNotificationPreferences(user=user, database=MagicMock())
        result = endpoint.execute()
        # success() returns a dict directly
        assert result["data"].partner_activity is True

    def test_get_partner_activity_respects_stored_value(self):
        from api.v1.user.push_tokens import GetNotificationPreferences

        user = MagicMock()
        user.notification_preferences = {"partner_activity": False}
        user.push_tokens = []

        endpoint = GetNotificationPreferences(user=user, database=MagicMock())
        result = endpoint.execute()
        assert result["data"].partner_activity is False
