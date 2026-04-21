"""Tests for user activity endpoints."""

import uuid
from datetime import UTC, datetime

from conftest import MockModel, MockQuery, count_queries


class FilterSpyQuery(MockQuery):
    """MockQuery that records every `.filter()` call so tests can assert
    specific filter expressions were applied.

    The base `MockQuery.filter` swallows its args, so tests that rely on
    a filter predicate being present (e.g. user_id isolation or the
    NOTIFICATION_TAB_TYPES allow-list) silently pass when the predicate
    is deleted. `FilterSpyQuery` exposes the raw args so behavioural
    assertions become load-bearing.
    """

    def __init__(self, items=None):
        super().__init__(items)
        self.filter_args: list[tuple] = []

    def filter(self, *args, **kwargs):
        self.filter_args.append(args)
        return self

    def join(self, *args, **kwargs):
        # Record joins as well so the imports_actionable join-to-jobs can
        # be asserted.
        self.filter_args.append(("__join__", args))
        return self


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


def _dual_query_side_effect(notif_items, import_items):
    """Dispatch db.query(Model) to the right MockQuery by class name.

    abi-1 `unread_count` makes two queries on one session — one against
    UserActivity, one against ImportItem. Tests that exercise the
    endpoint set both lists and this helper routes each call to the
    matching MockQuery so argument order is irrelevant.
    """

    def _side_effect(model):
        if getattr(model, "__name__", None) == "UserActivity":
            return MockQuery(notif_items)
        if getattr(model, "__name__", None) == "ImportItem":
            return MockQuery(import_items)
        return MockQuery([])

    return _side_effect


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
            type="partner_action",
            title="Alice edited your shopping list",
            subtitle="Groceries",
            metadata_json={"actor_user_id": "alice"},
            action_url="/shopping-lists/abc",
        )
        mock_db.db.query.return_value = MockQuery([activity])

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

    def test_list_activities_with_pagination(self, client, mock_db, mock_user):
        """Test listing activities with pagination params."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities?limit=10&offset=5")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    def test_list_activities_skips_count_query_on_cursor_less_path(
        self, client, mock_db, mock_user
    ):
        """pbq-5 — the initial (cursor-less) render no longer fires the
        heavy `COUNT(*)` on `user_activities`.

        Pre-fix: cursor-less requests ran a separate `total_query` with
        `.count()` — on a 10k-row seed this was the dominant cost.
        Post-fix: `total=0` is returned unconditionally; the main query
        fires once to fetch `limit + 1` rows for the next-page flag.
        """
        from utils.models.user_activity import UserActivity

        activities = [
            MockUserActivity(type="partner_action", title=f"r{i}")
            for i in range(3)
        ]
        mock_db.db.query.return_value = MockQuery(activities)

        with count_queries(mock_db) as qc:
            response = client.get("/v1/activities")
        assert response.status_code == 200
        assert response.json()["total"] == 0

        # Only one `db.query(UserActivity)`: the main LIST query. The
        # COUNT-shaped follow-up (a second `db.query(UserActivity)` with
        # `.count()`) is gone.
        assert qc.query_count_for(UserActivity) == 1


class TestListActivitiesAllowList:
    """Tests for abi-1 NOTIFICATION_TAB_TYPES allow-list on GET /v1/activities."""

    def test_default_returns_only_allow_listed_types(
        self, client, mock_db, mock_user
    ):
        """Default call returns rows (filter enforced server-side).

        MockQuery doesn't actually evaluate the type filter — we assert
        the endpoint returns 200 and the items it was given. Server-side
        filter construction is the real surface; combined with the
        include-system-types branch below, this covers both paths.
        """
        allowed = MockUserActivity(type="partner_action", title="OK")
        mock_db.db.query.return_value = MockQuery([allowed])

        response = client.get("/v1/activities")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed.
        assert body["total"] == 0
        assert body["items"][0]["type"] == "partner_action"

    def test_include_system_types_requires_admin(
        self, client, mock_db, mock_user
    ):
        """Non-admin passing ?include_system_types=true gets 403."""
        mock_user.is_admin = False

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 403
        assert response.json()["error_message"] == "Admin access required"

    def test_include_system_types_admin_succeeds(
        self, client, mock_db, mock_user
    ):
        """Admin passing the flag gets the unfiltered list back."""
        mock_user.is_admin = True
        import_started = MockUserActivity(type="import_started", title="Importing")
        mock_db.db.query.return_value = MockQuery([import_started])

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed.
        assert body["total"] == 0
        assert body["items"][0]["type"] == "import_started"

    def test_default_without_flag_does_not_require_admin(
        self, client, mock_db, mock_user
    ):
        """Non-admin can still hit the default (allow-listed) path."""
        mock_user.is_admin = False
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/activities")
        assert response.status_code == 200

    def test_default_applies_allow_list_filter_behaviourally(
        self, client, mock_db, mock_user
    ):
        """Filter spy verifies the UserActivity.type IN (...) filter lands.

        MockQuery.filter is a no-op, so a regression that dropped the
        allow-list branch in `list_activities.py` would silently keep
        tests green. This spy asserts the type-column filter is in the
        chain on the default path AND is absent when admin passes
        ?include_system_types=true.
        """
        from utils.models.user_activity import UserActivity

        spy = FilterSpyQuery([])
        mock_db.db.query.return_value = spy
        mock_user.is_admin = False

        response = client.get("/v1/activities")
        assert response.status_code == 200

        exprs = []
        for args in spy.filter_args:
            if args and args[0] == "__join__":
                continue
            exprs.extend(args)

        def expr_uses_type(e) -> bool:
            return f"{UserActivity.__tablename__}.type" in str(e)

        assert any(
            expr_uses_type(e) for e in exprs
        ), "default list_activities must filter UserActivity.type to the allow-list"

    def test_admin_with_include_system_types_skips_allow_list(
        self, client, mock_db, mock_user
    ):
        """Admin escape hatch: the type allow-list filter is NOT applied."""
        from utils.models.user_activity import UserActivity

        spy = FilterSpyQuery([])
        mock_db.db.query.return_value = spy
        mock_user.is_admin = True

        response = client.get("/v1/activities?include_system_types=true")
        assert response.status_code == 200

        exprs = []
        for args in spy.filter_args:
            if args and args[0] == "__join__":
                continue
            exprs.extend(args)

        def expr_uses_type(e) -> bool:
            return f"{UserActivity.__tablename__}.type" in str(e)

        assert not any(
            expr_uses_type(e) for e in exprs
        ), (
            "admin include_system_types path must NOT apply the type "
            "allow-list filter"
        )


class TestUnreadCount:
    """Tests for GET /v1/activities/unread-count — abi-1 structured payload."""

    def test_unread_count_zero(self, client, mock_db, mock_user):
        """Test unread count returns zero when nothing is pending."""
        mock_db.db.query.side_effect = _dual_query_side_effect([], [])

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 0,
            "imports_actionable": 0,
            "count": 0,
        }

    def test_unread_count_sums_notifications_and_imports(
        self, client, mock_db, mock_user
    ):
        """Combined payload: 3 partner_action + 2 actionable imports = 5."""
        notifications = [
            MockUserActivity(type="partner_action") for _ in range(3)
        ]
        imports_actionable = [object(), object()]  # MockQuery.count = len
        mock_db.db.query.side_effect = _dual_query_side_effect(
            notifications, imports_actionable
        )

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 3,
            "imports_actionable": 2,
            "count": 5,
        }

    def test_unread_count_backward_compat_wrapper(
        self, client, mock_db, mock_user
    ):
        """count = notifications + imports_actionable, always."""
        mock_db.db.query.side_effect = _dual_query_side_effect(
            [MockUserActivity()] * 4, [object()]
        )

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == data["notifications"] + data["imports_actionable"]
        assert data["count"] == 5

    def test_unread_count_imports_only(self, client, mock_db, mock_user):
        """Notifications empty; imports_actionable populated."""
        mock_db.db.query.side_effect = _dual_query_side_effect(
            [], [object(), object(), object()]
        )

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "notifications": 0,
            "imports_actionable": 3,
            "count": 3,
        }

    def test_unread_count_applies_tenant_and_window_filters(
        self, client, mock_db, mock_user
    ):
        """Every critical filter (user_id, allow-list, 30d, join) lands.

        MockQuery.filter is a no-op, so coverage-only tests would pass
        even if a tenant-isolation filter were deleted. This test uses
        FilterSpyQuery to capture .filter() / .join() args and asserts:
          1. UserActivity query filters by user_id, read, archived_at,
             type (allow-list), created_at (30d window).
          2. ImportItem query joins to ImportJob and filters by
             ImportJob.user_id (NOT import_items.user_id — the item
             table has no such column), plus archived_at, dismissed_at,
             status.
        Any regression that removes a clause here fails loudly.
        """
        from sqlalchemy.sql.elements import BinaryExpression

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.user_activity import UserActivity

        notif_spy = FilterSpyQuery([])
        imports_spy = FilterSpyQuery([])

        def dispatch(model):
            if getattr(model, "__name__", None) == "UserActivity":
                return notif_spy
            if getattr(model, "__name__", None) == "ImportItem":
                return imports_spy
            return MockQuery([])

        mock_db.db.query.side_effect = dispatch

        response = client.get("/v1/activities/unread-count")
        assert response.status_code == 200

        # Flatten captured filter expressions (skip the "__join__" tuples).
        notif_exprs = []
        for args in notif_spy.filter_args:
            if args and args[0] == "__join__":
                continue
            notif_exprs.extend(args)

        imports_exprs = []
        imports_joins = []
        for args in imports_spy.filter_args:
            if args and args[0] == "__join__":
                imports_joins.append(args[1])
                continue
            imports_exprs.extend(args)

        def expr_uses(expr, column_attr) -> bool:
            # SQLAlchemy `str()` renders the compiled SQL including
            # `tablename.columnname` for the involved columns. `repr()`
            # is a memory-address string, so don't use it. Matching by
            # string fragment is brittler than `.compare()` but
            # sufficient for "did the filter reference this column at
            # all."
            rendered = str(expr)
            table = column_attr.class_.__tablename__
            key = column_attr.key
            return f"{table}.{key}" in rendered

        # UserActivity filters — all five AC predicates present.
        assert any(
            expr_uses(e, UserActivity.user_id) for e in notif_exprs
        ), "notifications query must filter by UserActivity.user_id"
        assert any(
            expr_uses(e, UserActivity.read) for e in notif_exprs
        ), "notifications query must filter by UserActivity.read"
        assert any(
            expr_uses(e, UserActivity.archived_at) for e in notif_exprs
        ), "notifications query must filter by UserActivity.archived_at"
        assert any(
            expr_uses(e, UserActivity.type) for e in notif_exprs
        ), "notifications query must filter by UserActivity.type (allow-list)"
        assert any(
            expr_uses(e, UserActivity.created_at) for e in notif_exprs
        ), "notifications query must apply the 30-day created_at cutoff"

        # ImportItem filters — user_id lives on ImportJob, join must happen.
        assert imports_joins, (
            "imports_actionable query MUST join ImportJob (import_items "
            "has no user_id column)"
        )
        assert any(
            expr_uses(e, ImportJob.user_id) for e in imports_exprs
        ), "imports query must filter by ImportJob.user_id (tenant isolation)"
        assert any(
            expr_uses(e, ImportItem.archived_at) for e in imports_exprs
        ), "imports query must filter by ImportItem.archived_at"
        assert any(
            expr_uses(e, ImportItem.dismissed_at) for e in imports_exprs
        ), "imports query must filter by ImportItem.dismissed_at"
        assert any(
            expr_uses(e, ImportItem.status) for e in imports_exprs
        ), "imports query must filter by ImportItem.status (actionable set)"

        # Sanity: the test harness asserts BinaryExpression came through
        # at all — otherwise the `expr_uses` matcher would silently
        # return False for every predicate.
        assert any(
            isinstance(e, BinaryExpression)
            for e in notif_exprs + imports_exprs
        ), "spy captured no BinaryExpression — filter() argument capture is broken"


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


class TestListActivitiesCursor:
    """afh-1a: cursor pagination + include_read + since_days See-all mode."""

    def test_cursor_and_offset_both_present_returns_400(
        self, client, mock_db, mock_user
    ):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?cursor=abc&offset=5")
        assert response.status_code == 400
        assert (
            response.json()["error_message"]
            == "cursor_and_offset_mutually_exclusive"
        )

    def test_invalid_cursor_returns_400(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?cursor=%21%21%21%21%21%21")
        assert response.status_code == 400
        assert response.json()["error_message"] == "invalid_cursor"

    def test_cursor_default_mode_decodes_and_returns_items(
        self, client, mock_db, mock_user
    ):
        """A valid cursor in default (non-See-all) mode builds the
        two-key ``(created_at, id) < (cursor_ts, cursor_id)`` WHERE
        clause and returns items.
        """
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, str(uuid.uuid4()))
        activity = MockUserActivity(type="partner_action", title="X")
        mock_db.db.query.return_value = MockQuery([activity])

        response = client.get(f"/v1/activities?cursor={cursor}")
        assert response.status_code == 200
        body = response.json()
        # Cursor path skips the COUNT — total stays 0.
        assert body["total"] == 0
        assert len(body["items"]) == 1

    def test_cursor_see_all_mode_decodes_with_archived_at_value(
        self, client, mock_db, mock_user
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
        mock_db.db.query.return_value = MockQuery([activity])

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            f"&since_days=&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_cursor_see_all_mode_with_null_archived_at_cursor(
        self, client, mock_db, mock_user
    ):
        """See-all mode with ``archived_at_ms=None`` in the cursor
        builds the row-value comparison with the ``'-infinity'`` sentinel.
        """
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_699_000_000_000, str(uuid.uuid4()))
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            f"&since_days=&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_response_includes_next_cursor_when_more_results(
        self, client, mock_db, mock_user
    ):
        """MockQuery ignores the LIMIT, so seeding > limit items surfaces
        the has_more → next_cursor path and the Link header.
        """
        items = [
            MockUserActivity(type="partner_action", title=f"row{i}")
            for i in range(60)
        ]
        mock_db.db.query.return_value = MockQuery(items)

        response = client.get("/v1/activities?limit=50")
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None
        link = response.headers.get("link") or response.headers.get("Link")
        assert link is not None
        assert 'rel="next"' in link

    def test_see_all_mode_next_cursor_encodes_archived_at(
        self, client, mock_db, mock_user
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
        mock_db.db.query.return_value = MockQuery(items)

        response = client.get(
            "/v1/activities?include_archived=true&include_read=true"
            "&since_days=&limit=50"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None

    def test_legacy_offset_path_still_returns_items(
        self, client, mock_db, mock_user
    ):
        """AC9: ``offset=`` still works for one release alongside cursor."""
        items = [
            MockUserActivity(type="partner_action", title=f"r{i}")
            for i in range(20)
        ]
        mock_db.db.query.return_value = MockQuery(items)
        response = client.get("/v1/activities?limit=5&offset=5")
        assert response.status_code == 200
        body = response.json()
        # pbq-5: total is always 0 — COUNT removed, even on legacy
        # offset path.
        assert body["total"] == 0
        # Legacy path slices rows[5:10]; MockQuery returns all rows.
        assert len(body["items"]) == 5

    def test_limit_is_clamped_to_100(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?limit=9999")
        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 100

    def test_since_days_null_sentinel_empty_value(
        self, client, mock_db, mock_user
    ):
        """``?since_days=`` with no value opts out of the retention window."""
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?since_days=")
        assert response.status_code == 200

    def test_since_days_non_numeric_returns_400(
        self, client, mock_db, mock_user
    ):
        """Non-empty non-integer ``since_days`` is a client error."""
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?since_days=yesterday")
        assert response.status_code == 400

    def test_since_days_numeric_overrides_default(
        self, client, mock_db, mock_user
    ):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities?since_days=7")
        assert response.status_code == 200


class TestSeeAllCount:
    """afh-2: GET /v1/activities/see-all-count."""

    def test_zero_when_no_rows(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/activities/see-all-count")
        assert response.status_code == 200
        assert response.json() == {
            "archived": 0,
            "read_and_older": 0,
            "total": 0,
        }

    def test_sums_archived_and_read_and_older(
        self, client, mock_db, mock_user
    ):
        """MockQuery.count = len(items). First call returns archived
        rows, second returns read-and-older rows, and ``total`` is
        their sum.
        """
        # Both .count() calls hit the same MockQuery; in MockQuery,
        # .filter chains return self and .count returns len(items).
        # So if we seed 5 items, both counts read 5 → total = 10.
        mock_db.db.query.return_value = MockQuery(
            [MockUserActivity() for _ in range(5)]
        )
        response = client.get("/v1/activities/see-all-count")
        assert response.status_code == 200
        body = response.json()
        assert body["archived"] == 5
        assert body["read_and_older"] == 5
        assert body["total"] == 10
