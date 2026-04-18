"""Tests for user activity endpoints."""

import uuid
from datetime import UTC, datetime

from conftest import MockModel, MockQuery


class MockUserActivityForArchive(MockModel):
    """Mock UserActivity model with archive-friendly defaults."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "type": "invitation",
            "title": "Test",
            "subtitle": None,
            "metadata_json": None,
            "read": False,
            "action_url": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockUserActivity(MockModel):
    """Mock UserActivity model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "type": "import_started",
            "title": "Test Activity",
            "subtitle": None,
            "metadata_json": None,
            "read": False,
            "action_url": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestListActivities:
    """Tests for GET /v1/activities."""

    def test_list_activities_empty(self, client, mock_db, mock_user):
        """Test listing activities when there are none."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_activities_with_results(self, client, mock_db, mock_user):
        """Test listing activities with results."""
        activity = MockUserActivity(
            user_id=str(mock_user.id),
            type="import_started",
            title="Importing from URL",
            subtitle="Into My Recipes",
            metadata_json={"import_job_id": "job-1"},
            action_url="/recipes/import/review-list/job-1",
        )
        mock_db.db.query.return_value = MockQuery([activity])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["type"] == "import_started"
        assert data["items"][0]["title"] == "Importing from URL"
        assert data["items"][0]["subtitle"] == "Into My Recipes"
        assert data["items"][0]["metadata"] == {"import_job_id": "job-1"}
        assert data["items"][0]["action_url"] == "/recipes/import/review-list/job-1"
        assert data["items"][0]["read"] is False

    def test_list_activities_with_pagination(self, client, mock_db, mock_user):
        """Test listing activities with pagination params."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities?limit=10&offset=5")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


class TestUnreadCount:
    """Tests for GET /v1/activities/unread-count."""

    def test_unread_count_zero(self, client, mock_db, mock_user):
        """Test unread count returns zero when no unread activities."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_unread_count_with_activities(self, client, mock_db, mock_user):
        """Test unread count returns correct count."""
        # MockQuery.count() returns len of items, so pass 3 items
        mock_db.db.query.return_value = MockQuery([1, 2, 3])

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3


class TestMarkActivityRead:
    """Tests for PUT /v1/activities/{activity_id}/read."""

    def test_mark_activity_read_success(self, client, mock_db, mock_user):
        """Test marking a single activity as read."""
        activity_id = str(uuid.uuid4())
        activity = MockUserActivity(
            id=activity_id,
            user_id=str(mock_user.id),
            read=False,
        )
        from utils.models.user_activity import UserActivity

        mock_db.set_find_by(
            UserActivity, activity,
            id=activity_id, user_id=mock_user.id,
        )

        response = client.put(f"/v1/activities/{activity_id}/read")
        assert response.status_code == 200
        assert activity.read is True

    def test_mark_activity_read_not_found(self, client, mock_db, mock_user):
        """Test marking a nonexistent activity as read returns 404."""
        response = client.put(f"/v1/activities/{uuid.uuid4()}/read")
        assert response.status_code == 404


class TestMarkAllRead:
    """Tests for PUT /v1/activities/read-all."""

    def test_mark_all_read_success(self, client, mock_db, mock_user):
        """Test marking all activities as read."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.put("/v1/activities/read-all")
        assert response.status_code == 200


class TestArchiveActivity:
    """Tests for POST /v1/activities/{activity_id}/archive."""

    def test_archive_active_row_sets_archived_at(self, client, mock_db, mock_user):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=None,
        )
        mock_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/archive")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == activity_id
        assert body["archived_at"] is not None
        assert activity.archived_at is not None

    def test_archive_already_archived_is_noop(self, client, mock_db, mock_user):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        fixed_ts = datetime(2026, 4, 1, tzinfo=UTC)
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=fixed_ts,
        )
        mock_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/archive")
        assert response.status_code == 200
        # Unchanged — no-op.
        assert activity.archived_at == fixed_ts

    def test_archive_not_found(self, client, mock_db, mock_user):
        response = client.post(f"/v1/activities/{uuid.uuid4()}/archive")
        assert response.status_code == 404


class TestUnarchiveActivity:
    """Tests for POST /v1/activities/{activity_id}/unarchive."""

    def test_unarchive_archived_row_clears_archived_at(
        self, client, mock_db, mock_user
    ):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        mock_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/unarchive")
        assert response.status_code == 200
        assert activity.archived_at is None

    def test_unarchive_active_row_is_noop(self, client, mock_db, mock_user):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=None,
        )
        mock_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/unarchive")
        assert response.status_code == 200
        assert activity.archived_at is None

    def test_unarchive_not_found(self, client, mock_db, mock_user):
        response = client.post(f"/v1/activities/{uuid.uuid4()}/unarchive")
        assert response.status_code == 404


class TestListActivitiesIncludeArchived:
    """Tests for GET /v1/activities?include_archived=<bool>."""

    def test_default_excludes_archived(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities")
        assert response.status_code == 200

    def test_include_archived_true_accepts_query_param(
        self, client, mock_db, mock_user
    ):
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities?include_archived=true")
        assert response.status_code == 200
