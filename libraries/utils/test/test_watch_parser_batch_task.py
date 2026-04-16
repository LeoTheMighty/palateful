"""Tests for parser batch completion logic.

The fan-out logic (group-by-group_index → ImportJob + ImportItem) lives in
`complete_parser_batch` inside `utils.services.parser_batch_completion`. The
`WatchParserBatchTask` is a thin polling wrapper that calls it repeatedly;
these tests exercise the core function directly.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch


def _make_db_with_jobs(parser_jobs, existing_import_job=None):
    """Build a fake database whose queries return the pre-built fixtures."""
    db = MagicMock()

    # query(ParserJob).filter(...).all() → parser_jobs
    # query(ImportJob).filter(...).first() → existing_import_job (dedup guard)
    def query_dispatch(model):
        from utils.models.import_job import ImportJob
        from utils.models.parser_job import ParserJob as _PJ
        chain = MagicMock()
        if model is _PJ:
            chain.filter.return_value.all.return_value = parser_jobs
        elif model is ImportJob:
            chain.filter.return_value.first.return_value = existing_import_job
        return chain

    db.query.side_effect = query_dispatch
    db.commit = MagicMock()
    return db


def _make_database(parser_jobs, existing_import_job=None):
    database = MagicMock()
    database.db = _make_db_with_jobs(parser_jobs, existing_import_job)

    def create(model):
        if not getattr(model, "id", None):
            model.id = uuid.uuid4()
        if not getattr(model, "created_at", None):
            model.created_at = datetime.now(UTC)
        return model

    database.create.side_effect = create
    return database


def _make_parser_job(group_index=0, status="submitted", input_s3_key="uploads/x.jpg"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        batch_job_id="aws-batch-1",
        status=status,
        input_s3_key=input_s3_key,
        output_s3_key=f"results/{uuid.uuid4().hex[:8]}.json",
        extracted_text=None,
        error_message=None,
        completed_at=None,
        group_index=group_index,
        recipe_book_id=None,
        import_job_id=None,
        parser_batch_id=None,
        created_at=datetime.now(UTC),
    )


def _make_parser_batch(recipe_book_id=None, group_count=1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        recipe_book_id=recipe_book_id or uuid.uuid4(),
        status="submitted",
        group_count=group_count,
        error_message=None,
        completed_at=None,
        created_at=datetime.now(UTC),
    )


def test_happy_path_single_group_creates_one_import_job():
    """3 jobs / 1 group → 1 ImportJob with concatenated OCR text."""
    from utils.services.parser_batch_completion import complete_parser_batch

    batch = _make_parser_batch(group_count=1)
    jobs = [
        _make_parser_job(group_index=0, input_s3_key="uploads/p1.jpg"),
        _make_parser_job(group_index=0, input_s3_key="uploads/p2.jpg"),
        _make_parser_job(group_index=0, input_s3_key="uploads/p3.jpg"),
    ]
    for j in jobs:
        j.parser_batch_id = batch.id

    database = _make_database(jobs)

    aws_mock = MagicMock()
    aws_mock.describe_batch_job.return_value = {"status": "SUCCEEDED"}
    aws_mock.map_batch_status_to_parser_status.return_value = "succeeded"
    aws_mock.get_s3_object.side_effect = [
        {"extracted_markdown": "page 1"},
        {"extracted_markdown": "page 2"},
        {"extracted_markdown": "page 3"},
    ]

    created_objects: list = []
    original_create = database.create.side_effect

    def tracking_create(obj):
        created_objects.append(obj)
        return original_create(obj)

    database.create.side_effect = tracking_create

    with patch(
        "utils.tasks.import_tasks.parse_source_task.parse_source_task"
    ) as mock_dispatch:
        complete_parser_batch(database, aws_mock, batch)

    from utils.models.import_item import ImportItem
    from utils.models.import_job import ImportJob

    import_jobs = [o for o in created_objects if isinstance(o, ImportJob)]
    import_items = [o for o in created_objects if isinstance(o, ImportItem)]

    assert len(import_jobs) == 1
    assert len(import_items) == 1
    assert mock_dispatch.delay.call_count == 1
    assert "page 1" in import_items[0].raw_data["text"]
    assert "page 2" in import_items[0].raw_data["text"]
    assert "page 3" in import_items[0].raw_data["text"]
    assert "--- page break ---" in import_items[0].raw_data["text"]
    assert import_items[0].raw_data["s3_keys"] == [
        "uploads/p1.jpg",
        "uploads/p2.jpg",
        "uploads/p3.jpg",
    ]
    assert batch.status == "succeeded"


def test_happy_path_two_groups_creates_two_import_jobs():
    """3 jobs / 2 groups → 2 ImportJobs."""
    from utils.services.parser_batch_completion import complete_parser_batch

    batch = _make_parser_batch(group_count=2)
    jobs = [
        _make_parser_job(group_index=0, input_s3_key="uploads/r1p1.jpg"),
        _make_parser_job(group_index=0, input_s3_key="uploads/r1p2.jpg"),
        _make_parser_job(group_index=1, input_s3_key="uploads/r2p1.jpg"),
    ]
    for j in jobs:
        j.parser_batch_id = batch.id

    database = _make_database(jobs)

    aws_mock = MagicMock()
    aws_mock.describe_batch_job.return_value = {"status": "SUCCEEDED"}
    aws_mock.map_batch_status_to_parser_status.return_value = "succeeded"
    aws_mock.get_s3_object.side_effect = [
        {"extracted_markdown": "r1 p1"},
        {"extracted_markdown": "r1 p2"},
        {"extracted_markdown": "r2 p1"},
    ]

    created_objects: list = []
    original_create = database.create.side_effect

    def tracking_create(obj):
        created_objects.append(obj)
        return original_create(obj)

    database.create.side_effect = tracking_create

    with patch(
        "utils.tasks.import_tasks.parse_source_task.parse_source_task"
    ) as mock_dispatch:
        complete_parser_batch(database, aws_mock, batch)

    from utils.models.import_item import ImportItem
    from utils.models.import_job import ImportJob

    import_jobs = [o for o in created_objects if isinstance(o, ImportJob)]
    import_items = [o for o in created_objects if isinstance(o, ImportItem)]

    assert len(import_jobs) == 2
    assert len(import_items) == 2
    assert mock_dispatch.delay.call_count == 2
    texts = [it.raw_data["text"] for it in import_items]
    assert any("r1 p1" in t and "r1 p2" in t for t in texts)
    assert any("r2 p1" in t for t in texts)
    assert batch.status == "succeeded"


def test_partial_failure_marks_batch_partial():
    """1 of 3 jobs fails to fetch S3 → batch.status = partial, only successful group imported."""
    from utils.services.parser_batch_completion import complete_parser_batch

    batch = _make_parser_batch(group_count=2)
    jobs = [
        _make_parser_job(group_index=0, input_s3_key="uploads/g0a.jpg"),
        _make_parser_job(group_index=0, input_s3_key="uploads/g0b.jpg"),
        _make_parser_job(group_index=1, input_s3_key="uploads/g1.jpg"),
    ]
    for j in jobs:
        j.parser_batch_id = batch.id

    database = _make_database(jobs)

    aws_mock = MagicMock()
    aws_mock.describe_batch_job.return_value = {"status": "SUCCEEDED"}
    aws_mock.map_batch_status_to_parser_status.return_value = "succeeded"
    aws_mock.get_s3_object.side_effect = [
        {"extracted_markdown": "g0 page a"},
        {"extracted_markdown": "g0 page b"},
        Exception("S3 read failed"),
    ]

    created_objects: list = []
    original_create = database.create.side_effect

    def tracking_create(obj):
        created_objects.append(obj)
        return original_create(obj)

    database.create.side_effect = tracking_create

    with patch(
        "utils.tasks.import_tasks.parse_source_task.parse_source_task"
    ) as mock_dispatch:
        complete_parser_batch(database, aws_mock, batch)

    from utils.models.import_job import ImportJob

    import_jobs = [o for o in created_objects if isinstance(o, ImportJob)]
    assert len(import_jobs) == 1  # only group 0 succeeded
    assert mock_dispatch.delay.call_count == 1
    assert batch.status == "partial"


def test_total_failure_creates_no_import_jobs():
    """All jobs fail S3 fetch → batch.status = failed, no import jobs."""
    from utils.services.parser_batch_completion import complete_parser_batch

    batch = _make_parser_batch(group_count=1)
    jobs = [
        _make_parser_job(group_index=0),
        _make_parser_job(group_index=0),
    ]
    for j in jobs:
        j.parser_batch_id = batch.id

    database = _make_database(jobs)

    aws_mock = MagicMock()
    aws_mock.describe_batch_job.return_value = {"status": "SUCCEEDED"}
    aws_mock.map_batch_status_to_parser_status.return_value = "succeeded"
    aws_mock.get_s3_object.side_effect = [
        Exception("boom"),
        Exception("boom"),
    ]

    created_objects: list = []
    original_create = database.create.side_effect

    def tracking_create(obj):
        created_objects.append(obj)
        return original_create(obj)

    database.create.side_effect = tracking_create

    with patch(
        "utils.tasks.import_tasks.parse_source_task.parse_source_task"
    ), patch(
        "utils.services.activity_service.create_activity"
    ):
        complete_parser_batch(database, aws_mock, batch)

    from utils.models.import_job import ImportJob

    import_jobs = [o for o in created_objects if isinstance(o, ImportJob)]
    assert len(import_jobs) == 0
    assert batch.status == "failed"


def test_idempotent_on_terminal_batch():
    """Running complete_parser_batch on a terminal batch is a no-op."""
    from utils.services.parser_batch_completion import complete_parser_batch

    batch = _make_parser_batch()
    batch.status = "succeeded"

    database = _make_database([])

    aws_mock = MagicMock()

    result = complete_parser_batch(database, aws_mock, batch)

    aws_mock.describe_batch_job.assert_not_called()
    assert result == "succeeded"
