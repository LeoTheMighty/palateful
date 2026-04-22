"""Tests for import-pipeline push-notification helpers (sched-2)."""

import uuid
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.name = "Sarah"
    user.push_tokens = ["token-sarah"]
    user.notification_preferences = {
        "push_enabled": True,
        "categories": {"imports": True},
    }
    return user


def _make_job(
    *,
    source_type="url_list",
    source_url=None,
    source_filename=None,
    total_items=3,
    user=None,
):
    job = MagicMock()
    job.id = uuid.uuid4()
    job.source_type = source_type
    job.source_url = source_url
    job.source_filename = source_filename
    job.total_items = total_items
    job.user_id = (user.id if user else uuid.uuid4())
    return job


def _make_database(user=None):
    database = MagicMock()
    db = MagicMock()
    database.db = db
    database.find_by.return_value = user
    return database


# ---------------------------------------------------------------------------
# _source_label_for_job
# ---------------------------------------------------------------------------

class TestSourceLabelResolution:

    def test_url_parses_hostname(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(
            source_type="url",
            source_url="https://epicurious.com/recipes/pasta",
            total_items=1,
        )
        assert _source_label_for_job(job) == "epicurious.com"

    def test_url_strips_www_prefix(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(
            source_type="url",
            source_url="https://www.nytimes.com/cooking/recipes/foo",
            total_items=1,
        )
        assert _source_label_for_job(job) == "nytimes.com"

    def test_url_strips_port(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(
            source_type="url",
            source_url="https://example.com:8080/recipes/soup",
            total_items=1,
        )
        assert _source_label_for_job(job) == "example.com"

    def test_url_empty_falls_back_to_generic(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(source_type="url", source_url="", total_items=1)
        assert _source_label_for_job(job) == "your import"

    def test_url_list_uses_bulk_label(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(source_type="url_list", total_items=5)
        assert _source_label_for_job(job) == "your bulk import"

    def test_spreadsheet_uses_filename(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(
            source_type="spreadsheet",
            source_filename="my-recipes.xlsx",
        )
        assert _source_label_for_job(job) == "my-recipes.xlsx"

    def test_spreadsheet_without_filename_falls_back(self):
        from utils.services.import_notifications import _source_label_for_job

        job = _make_job(source_type="spreadsheet", source_filename=None)
        assert _source_label_for_job(job) == "your spreadsheet"

    def test_unknown_source_type_falls_back(self):
        from utils.services.import_notifications import _source_label_for_job

        for st in ("pdf", "photo", "text", None, ""):
            job = _make_job(source_type=st)
            assert _source_label_for_job(job) == "your import"


# ---------------------------------------------------------------------------
# notify_import_failed
# ---------------------------------------------------------------------------

class TestNotifyImportFailed:

    def test_single_url_uses_hostname_title(self):
        from utils.services.import_notifications import notify_import_failed

        user = _make_user()
        job = _make_job(
            source_type="url",
            source_url="https://epicurious.com/recipe/x",
            total_items=1,
            user=user,
        )
        database = _make_database(user=user)

        with patch(
            "utils.services.import_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_import_failed(database, job)

        notification = mock_service.send_to_user.call_args[0][1]
        assert notification.notification_type.value == "import_failed"
        assert "epicurious.com" in notification.title
        assert notification.data["import_job_id"] == str(job.id)

    def test_bulk_url_list_uses_count_copy(self):
        from utils.services.import_notifications import notify_import_failed

        user = _make_user()
        job = _make_job(source_type="url_list", total_items=5, user=user)
        database = _make_database(user=user)

        with patch(
            "utils.services.import_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_import_failed(database, job)

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Bulk import failed" in notification.title
        assert "5 recipes" in notification.body

    def test_skips_when_push_service_unavailable(self):
        from utils.services.import_notifications import notify_import_failed

        user = _make_user()
        job = _make_job(user=user)
        database = _make_database(user=user)

        with patch(
            "utils.services.import_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = False
            mock_get.return_value = mock_service

            notify_import_failed(database, job)

        mock_service.send_to_user.assert_not_called()

    def test_skips_when_user_missing(self):
        from utils.services.import_notifications import notify_import_failed

        job = _make_job()
        database = _make_database(user=None)

        with patch(
            "utils.services.import_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_import_failed(database, job)

        mock_service.send_to_user.assert_not_called()

    def test_swallows_unexpected_exceptions(self):
        from utils.services.import_notifications import notify_import_failed

        user = _make_user()
        job = _make_job(user=user)
        database = _make_database(user=user)

        with patch(
            "utils.services.import_notifications.get_push_service",
            side_effect=RuntimeError("boom"),
        ):
            # Must not raise.
            notify_import_failed(database, job)

    def test_zero_total_items_floored_to_one(self):
        """Defensive: an empty job wouldn't normally be failed, but if
        called with `total_items=0` we still pass `count=1` so the copy
        function gets a valid singular/bulk branch."""
        from utils.services.import_notifications import notify_import_failed

        user = _make_user()
        job = _make_job(total_items=0, user=user)
        database = _make_database(user=user)

        with patch(
            "utils.services.import_notifications.get_push_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.is_available = True
            mock_get.return_value = mock_service

            notify_import_failed(database, job)

        mock_service.send_to_user.assert_called_once()
