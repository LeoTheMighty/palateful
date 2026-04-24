"""Tests for parser batch endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import MockExecuteResult, MockModel, MockQuery


class MockParserBatch(MockModel):
    """Mock ParserBatch model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "recipe_book_id": None,
            "status": "pending",
            "group_count": 1,
            "error_message": None,
            "completed_at": None,
            "parser_jobs": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockBatchParserJob(MockModel):
    """Mock ParserJob with batch fields."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "input_s3_key": "uploads/test.jpg",
            "output_s3_key": "results/test.json",
            "status": "submitted",
            "batch_job_id": None,
            "extracted_text": None,
            "error_message": None,
            "completed_at": None,
            "parser_batch_id": None,
            "group_index": 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockBatchImportJob(MockModel):
    """Mock ImportJob with parser_batch_id."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "recipe_book_id": str(uuid.uuid4()),
            "status": "pending",
            "source_type": "photo",
            "parser_batch_id": None,
            "total_items": 1,
            "dismissed_at": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestCreateParserBatch:
    """POST /v1/parser/batches."""

    @patch(
        "utils.tasks.import_tasks.watch_parser_batch_task.watch_parser_batch_task"
    )
    @patch("api.v1.parser.create_parser_batch.AWSService")
    def test_create_batch_with_two_groups(
        self, mock_aws_cls, _mock_watch_task, client, mock_async_db, mock_user
    ):
        """3 items split as 2+1 → group_count=2, all jobs share batch_job_id."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job_async = AsyncMock(
            return_value="aws-batch-xyz"
        )

        response = client.post(
            "/v1/parser/batches",
            json={
                "recipe_book_id": str(uuid.uuid4()),
                "items": [
                    {"s3_key": "uploads/a.jpg", "group_index": 0},
                    {"s3_key": "uploads/b.jpg", "group_index": 0},
                    {"s3_key": "uploads/c.jpg", "group_index": 1},
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "submitted"
        assert len(data["jobs"]) == 3
        group_indices = sorted(j["group_index"] for j in data["jobs"])
        assert group_indices == [0, 0, 1]
        assert all(j["input_s3_key"] for j in data["jobs"])

        # AWS Batch was submitted with the manifest exactly once
        mock_aws.submit_batch_manifest_job_async.assert_awaited_once()
        call_kwargs = mock_aws.submit_batch_manifest_job_async.call_args.kwargs
        assert len(call_kwargs["items"]) == 3

    @patch(
        "utils.tasks.import_tasks.watch_parser_batch_task.watch_parser_batch_task"
    )
    @patch("api.v1.parser.create_parser_batch.AWSService")
    def test_create_batch_single_recipe(
        self, mock_aws_cls, _mock_watch_task, client, mock_async_db, mock_user
    ):
        """All items with group_index=0 → group_count=1."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job_async = AsyncMock(
            return_value="aws-single"
        )

        response = client.post(
            "/v1/parser/batches",
            json={
                "recipe_book_id": str(uuid.uuid4()),
                "items": [
                    {"s3_key": "uploads/a.jpg", "group_index": 0},
                    {"s3_key": "uploads/b.jpg", "group_index": 0},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["jobs"]) == 2
        assert {j["group_index"] for j in data["jobs"]} == {0}

    def test_create_batch_empty_items_rejected(
        self, client, mock_async_db, mock_user
    ):
        """Empty items list returns 400."""
        response = client.post(
            "/v1/parser/batches",
            json={"recipe_book_id": str(uuid.uuid4()), "items": []},
        )
        assert response.status_code == 400


class TestGetParserBatch:
    """GET /v1/parser/batches/{id}."""

    def test_get_batch_returns_nested_state(
        self, client, mock_async_db, mock_user
    ):
        batch_id = str(uuid.uuid4())
        rb_id = str(uuid.uuid4())
        job_a = MockBatchParserJob(
            user_id=str(mock_user.id),
            status="succeeded",
            input_s3_key="uploads/a.jpg",
            extracted_text="page 1 text",
            group_index=0,
        )
        job_b = MockBatchParserJob(
            user_id=str(mock_user.id),
            status="succeeded",
            input_s3_key="uploads/b.jpg",
            extracted_text="page 2 text",
            group_index=0,
        )
        batch = MockParserBatch(
            id=batch_id,
            user_id=str(mock_user.id),
            recipe_book_id=rb_id,
            status="succeeded",
            group_count=1,
            completed_at=datetime.now(UTC),
            parser_jobs=[job_a, job_b],
        )
        import_job = MockBatchImportJob(
            user_id=str(mock_user.id),
            recipe_book_id=rb_id,
            parser_batch_id=batch_id,
            status="awaiting_review",
        )

        # GetParserBatch issues two awaited db.execute calls:
        # 1. select(ParserBatch) with selectinload → scalars().first()
        # 2. select(ImportJob) where parser_batch_id == ... → scalars().all()
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([batch]),
            MockExecuteResult([import_job]),
        ]

        response = client.get(f"/v1/parser/batches/{batch_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == batch_id
        assert data["status"] == "succeeded"
        assert data["group_count"] == 1
        assert data["recipe_book_id"] == rb_id
        assert len(data["jobs"]) == 2
        assert data["jobs"][0]["extracted_text"] == "page 1 text"
        assert len(data["import_jobs"]) == 1
        assert data["import_jobs"][0]["status"] == "awaiting_review"

    def test_get_batch_not_found(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get(f"/v1/parser/batches/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_batch_wrong_user_forbidden(
        self, client, mock_async_db, mock_user
    ):
        batch_id = str(uuid.uuid4())
        batch = MockParserBatch(
            id=batch_id, user_id=str(uuid.uuid4()), parser_jobs=[]
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([batch])

        response = client.get(f"/v1/parser/batches/{batch_id}")
        assert response.status_code == 403


class TestListParserBatches:
    """GET /v1/parser/batches."""

    def test_list_batches_returns_user_batches(
        self, client, mock_async_db, mock_user
    ):
        batch = MockParserBatch(
            user_id=str(mock_user.id),
            status="running",
            parser_jobs=[],
        )
        related_job = MockBatchImportJob(parser_batch_id=batch.id)

        # ListParserBatches issues two awaited db.execute calls:
        # 1. select(ParserBatch) ... → scalars().all()
        # 2. select(ImportJob) ... → scalars().all()
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([batch]),
            MockExecuteResult([related_job]),
        ]

        response = client.get("/v1/parser/batches")
        assert response.status_code == 200
        data = response.json()
        assert "batches" in data
        assert len(data["batches"]) == 1
        assert data["batches"][0]["status"] == "running"

    def test_list_batches_active_filter(
        self, client, mock_async_db, mock_user
    ):
        """active=true filters at the query level — endpoint still returns whatever
        the mock provides; we assert the request is accepted with the flag."""
        # No batches returned → second query is skipped (batch_ids empty).
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/parser/batches?active=true&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["batches"] == []

    def test_list_batches_hides_batches_with_all_jobs_dismissed(
        self, client, mock_async_db, mock_user
    ):
        """A batch whose only ImportJob has dismissed_at set should not
        appear in the list."""
        visible_batch = MockParserBatch(
            user_id=str(mock_user.id), status="running", parser_jobs=[]
        )
        hidden_batch = MockParserBatch(
            user_id=str(mock_user.id), status="succeeded", parser_jobs=[]
        )

        visible_job = MockBatchImportJob(
            parser_batch_id=visible_batch.id, dismissed_at=None
        )
        dismissed_job = MockBatchImportJob(
            parser_batch_id=hidden_batch.id,
            dismissed_at="2026-04-15T12:00:00Z",
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([visible_batch, hidden_batch]),
            MockExecuteResult([visible_job, dismissed_job]),
        ]

        response = client.get("/v1/parser/batches")
        assert response.status_code == 200
        batches = response.json()["batches"]
        assert len(batches) == 1
        assert batches[0]["status"] == "running"

    def test_list_batches_shows_pre_fanout_batch_with_no_jobs(
        self, client, mock_async_db, mock_user
    ):
        """A running batch that has no linked ImportJob rows yet (parser
        hasn't fanned out) still shows on the strip."""
        pre_fanout = MockParserBatch(
            user_id=str(mock_user.id), status="running", parser_jobs=[]
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([pre_fanout]),
            MockExecuteResult([]),  # no jobs yet
        ]

        response = client.get("/v1/parser/batches")
        assert response.status_code == 200
        data = response.json()
        assert len(data["batches"]) == 1


class TestCompleteParserBatch:
    """POST /v1/parser/batches/{batch_id}/complete.

    The handler dispatches a sync helper via `run_in_threadpool` on a
    fresh `Database(db=SessionLocal())`. Tests patch `SessionLocal` at
    the endpoint module so the helper sees a mock session with the
    expected `.query(ParserBatch)...` behavior.
    """

    @patch("api.v1.parser.complete_parser_batch.complete_parser_batch")
    @patch("api.v1.parser.complete_parser_batch.AWSService")
    @patch("api.v1.parser.complete_parser_batch.SessionLocal")
    def test_complete_batch_happy_path(
        self,
        mock_session_local,
        mock_aws_cls,
        mock_complete,
        client,
        mock_async_db,
        mock_user,
    ):
        """Existing batch → delegates to complete_parser_batch, returns status."""
        batch_id = "batch-1"
        batch = MockParserBatch(id=batch_id, status="running")
        mock_session = MagicMock()
        mock_session.query.return_value = MockQuery([batch])
        mock_session_local.return_value = mock_session
        mock_complete.return_value = "succeeded"

        response = client.post(
            f"/v1/parser/batches/{batch_id}/complete",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == batch_id
        assert data["status"] == "succeeded"
        mock_complete.assert_called_once()

    @patch("api.v1.parser.complete_parser_batch.SessionLocal")
    def test_complete_batch_not_found(
        self, mock_session_local, client, mock_async_db, mock_user
    ):
        """Unknown batch_id → 404."""
        mock_session = MagicMock()
        mock_session.query.return_value = MockQuery([])
        mock_session_local.return_value = mock_session

        response = client.post(
            "/v1/parser/batches/nonexistent/complete",
            json={},
        )
        assert response.status_code == 404


class TestCreateParserBatchCallbackUrl:
    """Verify the callback-URL branch in CreateParserBatch."""

    @patch("utils.tasks.import_tasks.watch_parser_batch_task.watch_parser_batch_task")
    @patch("api.v1.parser.create_parser_batch.AWSService")
    @patch("api.v1.parser.create_parser_batch.settings")
    def test_callback_url_set_when_api_base_url_configured(
        self,
        mock_settings,
        mock_aws_cls,
        _mock_watch,
        client,
        mock_async_db,
        mock_user,
    ):
        """When settings.api_base_url is set, the callback URL is passed in
        extra_environment to the Batch job."""
        mock_settings.api_base_url = "https://api.palateful.app/v1"
        mock_settings.aws_region = "us-east-1"
        mock_settings.parser_inputs_bucket = "inputs"
        mock_settings.parser_outputs_bucket = "outputs"
        mock_settings.batch_job_queue = "q"
        mock_settings.batch_job_definition = "def"

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job_async = AsyncMock(
            return_value="aws-batch-123"
        )

        response = client.post(
            "/v1/parser/batches",
            json={
                "recipe_book_id": str(uuid.uuid4()),
                "items": [{"s3_key": "uploads/a.jpg"}],
            },
        )
        assert response.status_code == 201

        call_kwargs = mock_aws.submit_batch_manifest_job_async.call_args
        extra_env = call_kwargs.kwargs.get("extra_environment", {})
        assert "API_CALLBACK_URL" in extra_env
        assert "complete" in extra_env["API_CALLBACK_URL"]
