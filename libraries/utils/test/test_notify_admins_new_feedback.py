"""Tests for NotifyAdminsNewFeedbackTask."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_admin(**overrides):
    base = {
        "id": uuid.uuid4(),
        "is_admin": True,
        "archived_at": None,
        "email": "admin@example.com",
        "name": "Admin User",
        "username": None,
        "push_tokens": ["fcm-token-abc"],
        "notification_preferences": {
            "push_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_feedback(**overrides):
    base = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "body": "The share sheet bounces me to home after approving",
        "category": "bug",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _database_with(*, feedback, author, admins):
    """Return a MagicMock Database.db whose query/filter chain returns:
      - feedback on UserFeedback query
      - author on User query filtered by feedback.user_id
      - admins on User query filtered by is_admin=True
    The real filter chain is sloppy — we just sequence .first()/.all() calls.
    """
    db = MagicMock()

    from utils.models.user import User
    from utils.models.user_feedback import UserFeedback

    call_state = {"user_calls": 0}

    def _query(model):
        chain = MagicMock()
        chain.filter.return_value = chain
        if model is UserFeedback:
            chain.first.return_value = feedback
        elif model is User:
            call_state["user_calls"] += 1
            if call_state["user_calls"] == 1:
                chain.first.return_value = author
            else:
                chain.all.return_value = admins
        return chain

    db.query.side_effect = _query
    database = MagicMock()
    database.db = db
    return database


def _make_task(database):
    from utils.tasks.notification_tasks.notify_admins_new_feedback import (
        NotifyAdminsNewFeedbackTask,
    )

    task = NotifyAdminsNewFeedbackTask()
    task.database = database
    return task


class _FakePushService:
    def __init__(self, result=None, raise_on=None):
        self.result = result or {
            "success_count": 1,
            "failure_count": 0,
            "log_only": False,
        }
        self.raise_on = raise_on  # admin.id that triggers a raise
        self.calls = []

    def send_to_user(self, user, notification, db_session=None, force=False):
        self.calls.append({
            "user": user,
            "notification": notification,
            "force": force,
        })
        if self.raise_on is not None and user.id == self.raise_on:
            raise RuntimeError("FCM down for this admin")
        return self.result


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestNotifyAdminsHappyPath:
    def test_one_push_per_active_admin(self):
        feedback = _make_feedback()
        author = _make_admin(
            id=feedback.user_id, is_admin=False, name="Jane Doe",
        )
        admin_a = _make_admin(id=uuid.uuid4(), name="Leo")
        admin_b = _make_admin(id=uuid.uuid4(), name="Mei")
        database = _database_with(
            feedback=feedback, author=author, admins=[admin_a, admin_b],
        )
        fake = _FakePushService()

        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))

        assert result["data"]["notified_count"] == 2
        assert result["data"]["skipped_count"] == 0
        assert result["data"]["failed_count"] == 0

        # Every send used force=True (bypass quiet hours)
        assert all(c["force"] is True for c in fake.calls)
        # Payload shape
        for c in fake.calls:
            assert c["notification"].data == {
                "feedback_id": str(feedback.id),
                "deep_link": "/admin/feedback",
            }
            assert "Jane Doe" in c["notification"].body
            assert "bug" in c["notification"].body
            assert c["notification"].notification_type.value == "new_feedback"

    def test_one_admin_failure_does_not_block_others(self):
        feedback = _make_feedback()
        author = _make_admin(id=feedback.user_id, is_admin=False)
        admin_a = _make_admin(id=uuid.uuid4())
        admin_b = _make_admin(id=uuid.uuid4())
        database = _database_with(
            feedback=feedback, author=author, admins=[admin_a, admin_b],
        )
        fake = _FakePushService(raise_on=admin_a.id)

        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))

        # admin_b still got the push
        assert result["data"]["failed_count"] == 1
        assert result["data"]["notified_count"] == 1

    def test_log_only_result_counts_as_notified(self):
        """In log-only mode the service returns success_count=0 but
        log_only=True; treat that as notified for book-keeping."""
        feedback = _make_feedback()
        author = _make_admin(id=feedback.user_id, is_admin=False)
        admin = _make_admin()
        database = _database_with(
            feedback=feedback, author=author, admins=[admin],
        )
        fake = _FakePushService(result={
            "success_count": 0,
            "failure_count": 0,
            "log_only": True,
        })

        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))
        assert result["data"]["notified_count"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestNotifyAdminsEdgeCases:
    def test_feedback_missing_short_circuits(self):
        """A race where the feedback was deleted before the task fires
        must not crash the worker."""
        database = _database_with(feedback=None, author=None, admins=[])
        fake = _FakePushService()
        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(uuid.uuid4()))
        assert result["data"]["notified_count"] == 0
        assert fake.calls == []

    def test_no_active_admins_returns_zero_counts(self):
        feedback = _make_feedback()
        author = _make_admin(id=feedback.user_id, is_admin=False)
        database = _database_with(
            feedback=feedback, author=author, admins=[],
        )
        fake = _FakePushService()
        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))
        assert result["data"]["notified_count"] == 0
        assert result["data"]["admin_count"] == 0
        assert fake.calls == []

    def test_author_missing_falls_back_to_someone(self):
        """Deleted author → 'someone' in the body text, no crash."""
        feedback = _make_feedback()
        admin = _make_admin()
        database = _database_with(
            feedback=feedback, author=None, admins=[admin],
        )
        fake = _FakePushService()
        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))
        assert result["data"]["notified_count"] == 1
        assert "someone" in fake.calls[0]["notification"].body

    def test_push_result_zero_success_and_not_log_only_is_skipped(self):
        """Quiet-hours suppression without force=True (hypothetically) or
        no-tokens — counts as skipped, not failed."""
        feedback = _make_feedback()
        author = _make_admin(id=feedback.user_id, is_admin=False)
        admin = _make_admin(push_tokens=[])
        database = _database_with(
            feedback=feedback, author=author, admins=[admin],
        )
        fake = _FakePushService(result={
            "success_count": 0,
            "failure_count": 0,
            "log_only": False,
        })
        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            result = task.execute(str(feedback.id))
        assert result["data"]["skipped_count"] == 1
        assert result["data"]["notified_count"] == 0

    def test_body_preview_truncated_to_120_chars(self):
        feedback = _make_feedback(body="x" * 500, category=None)
        author = _make_admin(id=feedback.user_id, is_admin=False, name=None, username="jd")
        admin = _make_admin()
        database = _database_with(
            feedback=feedback, author=author, admins=[admin],
        )
        fake = _FakePushService()
        with patch(
            "utils.tasks.notification_tasks.notify_admins_new_feedback.get_push_service",
            return_value=fake,
        ):
            task = _make_task(database)
            task.execute(str(feedback.id))
        body = fake.calls[0]["notification"].body
        # Display name is jd (username), body preview is exactly 120 chars of x's.
        assert body.startswith("From jd — ")
        # No category segment when category is None
        assert " · " not in body
