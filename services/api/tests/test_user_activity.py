"""Tests for user activity endpoints.

aam-16: handlers are `AsyncEndpoint`; tests drive the router via the
sync `client` fixture (async deps already overridden in conftest) and
set up `mock_async_db.db.execute.side_effect` lists instead of the
legacy `mock_db.db.query`. Count-based handlers seed
`MockExecuteResult(items=[N])` — `MockExecuteResult.scalar_one()`
returns `items[0]`, so a seed of `[5]` reads as "count = 5".

The behavioural-filter assertions that were previously implemented via
`FilterSpyQuery` now inspect the compiled `select(...)` statement that
was the first positional arg to the captured `execute` call. Same
invariant (tenant isolation, allow-list, retention window), new
capture surface.
"""

import uuid
from datetime import UTC, datetime

from conftest import MockExecuteResult, MockModel


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
            "type": "partner_action",
            "title": "Test Activity",
            "subtitle": None,
            "metadata_json": None,
            "read": False,
            "action_url": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _list_side_effect(list_items, unread_count=0):
    """Side-effect list for GET /v1/activities.

    Two `execute` calls in order:
      1. Main list query — returns rows via `result.scalars().all()`.
      2. ffm-4 unread_count snapshot — returns int via `.scalar_one()`.
    """
    return [
        MockExecuteResult(items=list_items),
        MockExecuteResult(items=[unread_count]),
    ]


class TestListActivities:
    """Tests for GET /v1/activities."""

    def test_list_activities_empty(self, client, mock_async_db, mock_user):
        """Test listing activities when there are none."""
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_activities_with_results(
        self, client, mock_async_db, mock_user
    ):
        """Test listing activities with results."""
        activity = MockUserActivity(
            user_id=str(mock_user.id),
            type="partner_action",
            title="Alice edited your shopping list",
            subtitle="Groceries",
            metadata_json={"actor_user_id": "alice"},
            action_url="/shopping-lists/abc",
        )
        mock_async_db.db.execute.side_effect = _list_side_effect([activity])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        # pbq-5: total is always 0 — COUNT removed.
        assert data["total"] == 0
        assert data["items"][0]["type"] == "partner_action"
        assert data["items"][0]["title"] == "Alice edited your shopping list"
        assert data["items"][0]["subtitle"] == "Groceries"
        assert data["items"][0]["metadata"] == {"actor_user_id": "alice"}
        assert data["items"][0]["action_url"] == "/shopping-lists/abc"
        assert data["items"][0]["read"] is False

    def test_list_activities_with_pagination(
        self, client, mock_async_db, mock_user
    ):
        """Test listing activities with pagination params."""
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities?limit=10&offset=5")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    def test_list_activities_skips_count_query_on_cursor_less_path(
        self, client, mock_async_db, mock_user
    ):
        """pbq-5 — the initial (cursor-less) render no longer fires the
        heavy `COUNT(*)` on `user_activities` for pagination.

        Pre-pbq-5: cursor-less requests ran a separate `total_query`
        with `.count()` — on a 10k-row seed this was the dominant cost.
        Post-pbq-5: `total=0` is returned unconditionally; the main
        query fires once to fetch `limit + 1` rows for the next-page
        flag.

        ffm-4 adds a second query (the `unread_count` snapshot) that is
        deliberately NOT a full-table COUNT. It's one indexed filter
        (`type IN (...) AND read=false AND archived_at IS NULL`) so it
        stays cheap — the pbq-5 invariant is about avoiding the full-
        table COUNT, not about keeping the query count at 1.
        """
        activities = [
            MockUserActivity(type="partner_action", title=f"r{i}")
            for i in range(3)
        ]
        mock_async_db.db.execute.side_effect = _list_side_effect(activities, 0)

        response = client.get("/v1/activities")
        assert response.status_code == 200
        assert response.json()["total"] == 0

        # Two `execute` calls total: (1) main LIST select,
        # (2) ffm-4 unread_count snapshot. Both hit UserActivity; the
        # pbq-5 full-table COUNT(*) is still gone.
        assert mock_async_db.db.execute.call_count == 2
        list_stmt = mock_async_db.db.execute.call_args_list[0].args[0]
        assert "user_activities" in str(list_stmt).lower()


class TestListActivitiesUnreadCount:
    """ffm-4: `unread_count` snapshot on GET /v1/activities."""

    def test_unread_count_present_in_response(
        self, client, mock_async_db, mock_user
    ):
        """Response ALWAYS populates `unread_count` on new backends.

        The existence of the field (not null) is what gates the
        Flutter client's "skip the follow-up /unread-count call"
        optimization."""
        mock_async_db.db.execute.side_effect = _list_side_effect([], 0)
        response = client.get("/v1/activities")
        assert response.status_code == 200
        body = response.json()
        assert "unread_count" in body
        assert body["unread_count"] == 0

    def test_unread_count_matches_snapshot_query(
        self, client, mock_async_db, mock_user
    ):
        """List query returns items; unread-count query returns a
        different count whose value is the expected count. Verifies
        the unread snapshot is distinct from the list result rather
        than being `len(items)`."""
        # 3 items on the LIST page; 7 unread-count rows.
        list_items = [MockUserActivity() for _ in range(3)]
        mock_async_db.db.execute.side_effect = _list_side_effect(list_items, 7)
        response = client.get("/v1/activities")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 3
        assert body["unread_count"] == 7

    def test_unread_count_is_zero_when_no_unread(
        self, client, mock_async_db, mock_user
    ):
        """Empty unread-count snapshot → 0 (not null, not missing)."""
        list_items = [MockUserActivity() for _ in range(2)]
        mock_async_db.db.execute.side_effect = _list_side_effect(list_items, 0)
        response = client.get("/v1/activities")
        assert response.status_code == 200
        assert response.json()["unread_count"] == 0

    def test_unread_count_populated_with_cursor_pagination(
        self, client, mock_async_db, mock_user
    ):
        """Cursor-less vs cursor-paginated paths both populate the
        field — it's a snapshot, not per-page."""
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, str(uuid.uuid4()))
        list_items = [MockUserActivity()]
        mock_async_db.db.execute.side_effect = _list_side_effect(list_items, 4)
        response = client.get(f"/v1/activities?cursor={cursor}")
        assert response.status_code == 200
        assert response.json()["unread_count"] == 4


class TestListActivitiesAllowList:
    """Tests for abi-1 NOTIFICATION_TAB_TYPES allow-list on GET /v1/activities."""

    def test_default_returns_only_allow_listed_types(
        self, client, mock_async_db, mock_user
    ):
        """Default call returns rows (filter enforced server-side).

        `MockExecuteResult` doesn't evaluate the type filter — we assert
        the endpoint returns 200 and the items it was given. Server-side
        filter construction is the real surface; combined with the
        stmt-inspection behavioural check below, this covers both paths.
        """
        allowed = MockUserActivity(type="partner_action", title="OK")
        mock_async_db.db.execute.side_effect = _list_side_effect([allowed])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed.
        assert body["total"] == 0
        assert body["items"][0]["type"] == "partner_action"

    def test_include_system_types_requires_admin(
        self, client, mock_async_db, mock_user
    ):
        """Non-admin passing ?include_system_types=true gets 403."""
        mock_user.is_admin = False

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 403
        assert response.json()["error_message"] == "Admin access required"

    def test_include_system_types_admin_succeeds(
        self, client, mock_async_db, mock_user
    ):
        """Admin passing the flag gets the unfiltered list back."""
        mock_user.is_admin = True
        import_started = MockUserActivity(
            type="import_started", title="Importing"
        )
        mock_async_db.db.execute.side_effect = _list_side_effect(
            [import_started]
        )

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed.
        assert body["total"] == 0
        assert body["items"][0]["type"] == "import_started"

    def test_default_without_flag_does_not_require_admin(
        self, client, mock_async_db, mock_user
    ):
        """Non-admin can still hit the default (allow-listed) path."""
        mock_user.is_admin = False
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities")
        assert response.status_code == 200

    def test_default_applies_allow_list_filter_behaviourally(
        self, client, mock_async_db, mock_user
    ):
        """Compiled-stmt spy verifies the UserActivity.type IN (...)
        filter lands on the default path.

        A regression that dropped the allow-list branch in
        `list_activities.py` would silently keep tests green if we
        only checked mock results. This assertion inspects the select
        statement's compiled SQL and asserts the type column is
        referenced.
        """
        mock_user.is_admin = False
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities")
        assert response.status_code == 200

        # First execute = main LIST query. Compiled SQL includes
        # `user_activities.type IN (...)` on the default path. Check
        # for the IN predicate rather than the bare column name — the
        # column appears in the SELECT projection too, so a bare-name
        # check would silently pass even if the WHERE clause branch
        # were deleted.
        list_stmt = mock_async_db.db.execute.call_args_list[0].args[0]
        rendered = str(list_stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "user_activities.type IN" in rendered, (
            "default list_activities must filter UserActivity.type to the "
            f"allow-list (compiled SQL: {rendered})"
        )

    def test_admin_with_include_system_types_skips_allow_list(
        self, client, mock_async_db, mock_user
    ):
        """Admin escape hatch: the type allow-list filter is NOT applied
        on the LIST query. The ffm-4 unread_count snapshot query that
        runs in the same request DOES apply the allow-list — that's
        correct (the bell count is always over the user-facing types)
        — so the assertion below is scoped to the first (list) query
        only."""
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 200

        list_stmt = mock_async_db.db.execute.call_args_list[0].args[0]
        rendered = str(list_stmt.compile(compile_kwargs={"literal_binds": False}))
        # Bare `user_activities.type` appears in the SELECT projection,
        # so check specifically for the IN predicate instead.
        assert "user_activities.type IN" not in rendered, (
            "admin include_system_types path must NOT apply the type "
            f"allow-list filter on the LIST query (compiled SQL: {rendered})"
        )
        # Sanity: the unread snapshot (second execute) still applies it.
        unread_stmt = mock_async_db.db.execute.call_args_list[1].args[0]
        assert "user_activities.type IN" in str(
            unread_stmt.compile(compile_kwargs={"literal_binds": False})
        )


class TestUnreadCount:
    """Tests for GET /v1/activities/unread-count — abi-1 structured payload."""

    def test_unread_count_zero(self, client, mock_async_db, mock_user):
        """Test unread count returns zero when nothing is pending."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[0]),
        ]

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 0,
            "imports_actionable": 0,
            "count": 0,
        }

    def test_unread_count_sums_notifications_and_imports(
        self, client, mock_async_db, mock_user
    ):
        """Combined payload: 3 partner_action + 2 actionable imports = 5."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[3]),
            MockExecuteResult(items=[2]),
        ]

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 3,
            "imports_actionable": 2,
            "count": 5,
        }

    def test_unread_count_backward_compat_wrapper(
        self, client, mock_async_db, mock_user
    ):
        """count = notifications + imports_actionable, always."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[4]),
            MockExecuteResult(items=[1]),
        ]

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == data["notifications"] + data["imports_actionable"]
        assert data["count"] == 5

    def test_unread_count_imports_only(
        self, client, mock_async_db, mock_user
    ):
        """Notifications empty; imports_actionable populated."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[3]),
        ]

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 0,
            "imports_actionable": 3,
            "count": 3,
        }

    def test_unread_count_applies_tenant_and_window_filters(
        self, client, mock_async_db, mock_user
    ):
        """Every critical filter (user_id, allow-list, 30d, join) lands.

        Inspects the compiled `select` statements for each of the two
        counts:
          1. Notifications `select(func.count()).select_from(UserActivity)`
             filters by user_id, read, archived_at, type (allow-list),
             created_at (30d window).
          2. Imports `select(func.count()).select_from(ImportItem)` joins
             to ImportJob and filters by ImportJob.user_id (NOT
             import_items.user_id — no such column), plus archived_at,
             dismissed_at, status.
        Any regression that removes a clause here fails loudly.
        """
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[0]),
        ]

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200

        notif_stmt = mock_async_db.db.execute.call_args_list[0].args[0]
        imports_stmt = mock_async_db.db.execute.call_args_list[1].args[0]

        notif_sql = str(
            notif_stmt.compile(compile_kwargs={"literal_binds": False})
        )
        imports_sql = str(
            imports_stmt.compile(compile_kwargs={"literal_binds": False})
        )

        # Notifications filters — all five AC predicates present.
        assert "user_activities.user_id" in notif_sql, (
            "notifications query must filter by UserActivity.user_id"
        )
        assert "user_activities.read" in notif_sql, (
            "notifications query must filter by UserActivity.read"
        )
        assert "user_activities.archived_at" in notif_sql, (
            "notifications query must filter by UserActivity.archived_at"
        )
        assert "user_activities.type IN" in notif_sql, (
            "notifications query must filter by UserActivity.type "
            "(allow-list)"
        )
        assert "user_activities.created_at" in notif_sql, (
            "notifications query must apply the 30-day created_at cutoff"
        )

        # ImportItem filters — user_id lives on ImportJob, join must happen.
        assert "import_jobs" in imports_sql, (
            "imports_actionable query MUST join ImportJob (import_items "
            "has no user_id column)"
        )
        assert "import_jobs.user_id" in imports_sql, (
            "imports query must filter by ImportJob.user_id "
            "(tenant isolation)"
        )
        assert "import_items.archived_at" in imports_sql, (
            "imports query must filter by ImportItem.archived_at"
        )
        assert "import_items.dismissed_at" in imports_sql, (
            "imports query must filter by ImportItem.dismissed_at"
        )
        assert "import_items.status" in imports_sql, (
            "imports query must filter by ImportItem.status "
            "(actionable set)"
        )


class TestMarkActivityRead:
    """Tests for PUT /v1/activities/{activity_id}/read."""

    def test_mark_activity_read_success(
        self, client, mock_async_db, mock_user
    ):
        """Test marking a single activity as read."""
        activity_id = str(uuid.uuid4())
        activity = MockUserActivity(
            id=activity_id,
            user_id=str(mock_user.id),
            read=False,
        )
        from utils.models.user_activity import UserActivity

        mock_async_db.set_find_by(
            UserActivity, activity,
            id=activity_id, user_id=mock_user.id,
        )

        response = client.put(f"/v1/activities/{activity_id}/read")
        assert response.status_code == 200
        assert activity.read is True

    def test_mark_activity_read_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test marking a nonexistent activity as read returns 404."""
        response = client.put(f"/v1/activities/{uuid.uuid4()}/read")
        assert response.status_code == 404


class TestMarkAllRead:
    """Tests for PUT /v1/activities/read-all."""

    def test_mark_all_read_success(self, client, mock_async_db, mock_user):
        """Test marking all activities as read."""
        response = client.put("/v1/activities/read-all")
        assert response.status_code == 200
        # One UPDATE statement was dispatched.
        assert mock_async_db.db.execute.call_count == 1
        stmt = mock_async_db.db.execute.call_args_list[0].args[0]
        rendered = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        # Verify it's an UPDATE targeting the allow-list + archive-free
        # + unread predicate (tenant isolation, soft-archive ignore).
        assert "UPDATE user_activities" in rendered
        assert "user_activities.user_id" in rendered
        assert "user_activities.read" in rendered
        assert "user_activities.archived_at" in rendered


class TestArchiveActivity:
    """Tests for POST /v1/activities/{activity_id}/archive."""

    def test_archive_active_row_sets_archived_at(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=None,
        )
        mock_async_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/archive")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == activity_id
        assert body["archived_at"] is not None
        assert activity.archived_at is not None

    def test_archive_already_archived_is_noop(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        fixed_ts = datetime(2026, 4, 1, tzinfo=UTC)
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=fixed_ts,
        )
        mock_async_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/archive")
        assert response.status_code == 200
        # Unchanged — no-op.
        assert activity.archived_at == fixed_ts

    def test_archive_not_found(self, client, mock_async_db, mock_user):
        response = client.post(f"/v1/activities/{uuid.uuid4()}/archive")
        assert response.status_code == 404


class TestUnarchiveActivity:
    """Tests for POST /v1/activities/{activity_id}/unarchive."""

    def test_unarchive_archived_row_clears_archived_at(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        mock_async_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/unarchive")
        assert response.status_code == 200
        assert activity.archived_at is None

    def test_unarchive_active_row_is_noop(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.user_activity import UserActivity

        activity_id = str(uuid.uuid4())
        activity = MockUserActivityForArchive(
            id=activity_id,
            user_id=str(mock_user.id),
            archived_at=None,
        )
        mock_async_db.set_find_by(
            UserActivity, activity, id=activity_id, user_id=mock_user.id
        )

        response = client.post(f"/v1/activities/{activity_id}/unarchive")
        assert response.status_code == 200
        assert activity.archived_at is None

    def test_unarchive_not_found(self, client, mock_async_db, mock_user):
        response = client.post(f"/v1/activities/{uuid.uuid4()}/unarchive")
        assert response.status_code == 404


class TestListActivitiesIncludeArchived:
    """Tests for GET /v1/activities?include_archived=<bool>."""

    def test_default_excludes_archived(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities")
        assert response.status_code == 200

    def test_include_archived_true_accepts_query_param(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get("/v1/activities?include_archived=true")
        assert response.status_code == 200


class TestListActivitiesCursor:
    """afh-1a: cursor pagination + include_read + since_days See-all mode."""

    def test_cursor_and_offset_both_present_returns_400(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?cursor=abc&offset=5")
        assert response.status_code == 400
        assert (
            response.json()["error_message"]
            == "cursor_and_offset_mutually_exclusive"
        )

    def test_invalid_cursor_returns_400(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?cursor=%21%21%21%21%21%21")
        assert response.status_code == 400
        assert response.json()["error_message"] == "invalid_cursor"

    def test_cursor_default_mode_decodes_and_returns_items(
        self, client, mock_async_db, mock_user
    ):
        """A valid cursor in default (non-See-all) mode builds the
        two-key ``(created_at, id) < (cursor_ts, cursor_id)`` WHERE
        clause and returns items.
        """
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, str(uuid.uuid4()))
        activity = MockUserActivity(type="partner_action", title="X")
        mock_async_db.db.execute.side_effect = _list_side_effect([activity])

        response = client.get(f"/v1/activities?cursor={cursor}")
        assert response.status_code == 200
        body = response.json()
        # Cursor path skips the COUNT — total stays 0.
        assert body["total"] == 0
        assert len(body["items"]) == 1

    def test_cursor_see_all_mode_decodes_with_archived_at_value(
        self, client, mock_async_db, mock_user
    ):
        """See-all mode with an archived_at value exercises the
        three-key row-value WHERE clause and ordering.
        """
        from pagination import encode_cursor

        cursor = encode_cursor(
            1_700_000_000_000, 1_699_000_000_000, str(uuid.uuid4())
        )
        activity = MockUserActivity(
            type="partner_action",
            title="X",
            archived_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        mock_async_db.db.execute.side_effect = _list_side_effect([activity])

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            f"&since_days=&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_cursor_see_all_mode_with_null_archived_at_cursor(
        self, client, mock_async_db, mock_user
    ):
        """See-all mode with ``archived_at_ms=None`` in the cursor
        builds the row-value comparison with the ``'-infinity'`` sentinel.
        """
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_699_000_000_000, str(uuid.uuid4()))
        mock_async_db.db.execute.side_effect = _list_side_effect([])

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            f"&since_days=&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_response_includes_next_cursor_when_more_results(
        self, client, mock_async_db, mock_user
    ):
        """Seeding > limit items surfaces the has_more → next_cursor path
        and the Link header. `MockExecuteResult` returns all rows; the
        handler slices to `limit + 1` / `limit`.
        """
        items = [
            MockUserActivity(type="partner_action", title=f"row{i}")
            for i in range(60)
        ]
        mock_async_db.db.execute.side_effect = _list_side_effect(items)

        response = client.get("/v1/activities?limit=50")
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None
        link = response.headers.get("link") or response.headers.get("Link")
        assert link is not None
        assert 'rel="next"' in link

    def test_see_all_mode_next_cursor_encodes_archived_at(
        self, client, mock_async_db, mock_user
    ):
        """See-all mode encodes ``archived_at`` in the cursor so the
        client can resume at the archived/non-archived boundary.
        """
        items = [
            MockUserActivity(
                type="partner_action",
                title=f"r{i}",
                archived_at=datetime(2025, 6, (i % 28) + 1, tzinfo=UTC),
            )
            for i in range(60)
        ]
        mock_async_db.db.execute.side_effect = _list_side_effect(items)

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            "&since_days=&limit=50"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None

    def test_legacy_offset_path_still_returns_items(
        self, client, mock_async_db, mock_user
    ):
        """AC9: ``offset=`` still works for one release alongside cursor."""
        items = [
            MockUserActivity(type="partner_action", title=f"r{i}")
            for i in range(20)
        ]
        mock_async_db.db.execute.side_effect = _list_side_effect(items)
        response = client.get("/v1/activities?limit=5&offset=5")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed, even on legacy
        # offset path.
        assert body["total"] == 0
        # Legacy path slices rows[5:10]; the seed returns all rows so
        # the slice contains 5 items.
        assert len(body["items"]) == 5

    def test_limit_is_clamped_to_100(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?limit=9999")
        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 100

    def test_since_days_null_sentinel_empty_value(
        self, client, mock_async_db, mock_user
    ):
        """``?since_days=`` with no value opts out of the retention window."""
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?since_days=")
        assert response.status_code == 200

    def test_since_days_non_numeric_returns_400(
        self, client, mock_async_db, mock_user
    ):
        """Non-empty non-integer ``since_days`` is a client error."""
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?since_days=yesterday")
        assert response.status_code == 400

    def test_since_days_numeric_overrides_default(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_side_effect([])
        response = client.get("/v1/activities?since_days=7")
        assert response.status_code == 200


class TestSeeAllCount:
    """afh-2: GET /v1/activities/see-all-count."""

    def test_zero_when_no_rows(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[0]),
        ]
        response = client.get("/v1/activities/see-all-count")
        assert response.status_code == 200
        assert response.json() == {
            "archived": 0,
            "read_and_older": 0,
            "total": 0,
        }

    def test_sums_archived_and_read_and_older(
        self, client, mock_async_db, mock_user
    ):
        """First execute = archived count; second = read-and-older count.
        Response ``total`` is their sum."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[5]),
            MockExecuteResult(items=[3]),
        ]
        response = client.get("/v1/activities/see-all-count")
        assert response.status_code == 200
        body = response.json()
        assert body["archived"] == 5
        assert body["read_and_older"] == 3
        assert body["total"] == 8
