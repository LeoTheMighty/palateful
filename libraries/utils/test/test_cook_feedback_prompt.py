"""Unit tests for the 2h post-cook feedback prompt task + helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_task():
    """Instantiate the task with a mocked `database` attribute.

    BaseTask.run() lazily creates a Database on each run; the tests
    exercise `.execute` directly, so we install the mock ourselves.
    """
    from utils.tasks.cook_feedback_tasks.cook_feedback_prompt import (
        CookFeedbackPromptTask,
    )
    task = CookFeedbackPromptTask()
    task.database = MagicMock()
    task.database.db = MagicMock()
    return task


def _install_queries(task, *, cook_log=None, recipe=None, user=None):
    """Wire task.database.db.query().filter().first() to return each model in order."""
    calls = []
    for obj in (cook_log, recipe, user):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = obj
        calls.append(q)
    task.database.db.query.side_effect = calls


class TestCookFeedbackPromptTask:

    def test_log_missing_skips(self):
        task = _make_task()
        _install_queries(task, cook_log=None)

        result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "log_not_found"

    def test_already_rated_skips(self):
        task = _make_task()
        log = MagicMock()
        log.notes = "Was great!"  # non-null → user already recorded feedback
        log.recipe_id = "r-1"
        _install_queries(task, cook_log=log)

        result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "already_rated"

    def test_meal_level_parent_skipped(self):
        task = _make_task()
        log = MagicMock()
        log.notes = None
        log.recipe_id = None  # meal-level parent row
        _install_queries(task, cook_log=log)

        result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "no_recipe"

    def test_recipe_missing_skips(self):
        task = _make_task()
        log = MagicMock()
        log.notes = None
        log.recipe_id = "r-1"
        _install_queries(task, cook_log=log, recipe=None)

        result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "recipe_missing"

    def test_user_missing_skips(self):
        task = _make_task()
        log = MagicMock()
        log.notes = None
        log.recipe_id = "r-1"
        recipe = MagicMock()
        _install_queries(task, cook_log=log, recipe=recipe, user=None)

        result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "user_missing"

    def test_fires_push_when_ready(self):
        task = _make_task()
        log = MagicMock()
        log.notes = None
        log.recipe_id = "r-1"
        recipe = MagicMock()
        recipe.id = "r-1"
        recipe.name = "Sweet Potato Quiche"
        recipe.image_url = "https://cdn/r.jpg"
        user = MagicMock()
        _install_queries(task, cook_log=log, recipe=recipe, user=user)

        with patch(
            "utils.tasks.cook_feedback_tasks.cook_feedback_prompt.notify_cook_feedback_prompt"
        ) as mock_notify:
            mock_notify.return_value = {
                "success_count": 1,
                "suppressed_by_category": False,
                "suppressed_by_quiet_hours": False,
            }

            result = task.execute(cook_log_id="log-1", user_id="u-1")

        mock_notify.assert_called_once_with(
            database=task.database,
            user=user,
            recipe=recipe,
        )
        assert result["data"]["sent"] is True
        assert result["data"]["success_count"] == 1

    def test_send_failure_is_swallowed(self):
        task = _make_task()
        log = MagicMock()
        log.notes = None
        log.recipe_id = "r-1"
        recipe = MagicMock()
        recipe.name = "Quiche"
        user = MagicMock()
        _install_queries(task, cook_log=log, recipe=recipe, user=user)

        with patch(
            "utils.tasks.cook_feedback_tasks.cook_feedback_prompt.notify_cook_feedback_prompt"
        ) as mock_notify:
            mock_notify.side_effect = RuntimeError("FCM down")

            # Must not raise.
            result = task.execute(cook_log_id="log-1", user_id="u-1")

        assert result["data"]["skipped"] == "send_failed"


class TestNotifyCookFeedbackPrompt:

    def test_payload_shape(self):
        from utils.services.cook_feedback_notifications import (
            notify_cook_feedback_prompt,
        )

        database = MagicMock()
        database.db = MagicMock()

        user = MagicMock()
        recipe = MagicMock()
        recipe.id = "r-xyz"
        recipe.name = "Cinnamon Rolls"
        recipe.image_url = "https://cdn/r.jpg"

        with patch(
            "utils.services.cook_feedback_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            notify_cook_feedback_prompt(
                database=database,
                user=user,
                recipe=recipe,
            )

        mock_service.send_to_user.assert_called_once()
        sent_user, notification = mock_service.send_to_user.call_args[0][:2]
        assert sent_user is user
        assert notification.notification_type.value == "cook_feedback_prompt"
        assert notification.title == "How did your Cinnamon Rolls turn out? 🍴"
        assert notification.body == "Tap to add a quick rating + note."
        assert notification.data == {
            "recipe_id": "r-xyz",
            "source": "cook_feedback_prompt",
        }
        assert notification.image_url == "https://cdn/r.jpg"
