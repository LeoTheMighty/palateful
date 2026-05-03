"""Tests for the share-img-1 image branch in extract_recipe_task.

When `ImportItem.source_type == "image"`, the task fetches bytes from
`S3_IMPORTS_BUCKET` and runs `extract_recipe_from_image` (gpt-4o-mini
vision). ParseSourceTask is intentionally a no-op for image — the
parse stage has nothing to decode, and the bytes are read here.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils.models.import_item import ImportItem
from utils.services.recipe_extractors import ExtractionResult
from utils.services.recipe_extractors.base import ExtractedRecipe
from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask


class _FakeDatabase:
    """Narrow fake of the BaseTask database handle.

    Only supports the slice of the API the image branch + post-extract
    fanout/job-counts path actually exercises:
    `find_by(model, id=...)`, `create(row)`,
    `db.scalars(select).all()`, `db.query().filter().group_by().all()`,
    and `db.commit()`.
    """

    def __init__(self, items: list[ImportItem], job: SimpleNamespace):
        self.items = items
        self.job = job
        self.db = MagicMock()
        self.db.commit = MagicMock()
        self.db.refresh = MagicMock()
        self.db.scalars.side_effect = self._scalars
        # _update_job_counts uses db.query().filter().group_by().all().
        self.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("awaiting_review", len(items)),
        ]

    def _scalars(self, _stmt):
        scalars_result = MagicMock()
        scalars_result.all.return_value = list(self.items)
        return scalars_result

    def find_by(self, model, **_kwargs):
        from utils.models.import_job import ImportJob
        if model is ImportItem:
            return self.items[0] if self.items else None
        if model is ImportJob:
            return self.job
        return None

    def create(self, row):
        if isinstance(row, ImportItem):
            if getattr(row, "id", None) is None:
                row.id = uuid.uuid4()
            self.items.append(row)


def _make_job() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total_items=1,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
        total_ai_cost_cents=0,
        recipe_book_id=uuid.uuid4(),
    )


def _make_image_item(job_id: uuid.UUID, s3_key: str) -> ImportItem:
    item = ImportItem(
        import_job_id=job_id,
        source_type="image",
        s3_key=s3_key,
        raw_data={
            "s3_key": s3_key,
            "original_filename": "recipe.jpg",
            "mime_type": "image/jpeg",
            "etag": '"abc123"',
        },
        status="pending",
        ai_cost_cents=0,
        retry_count=0,
    )
    item.id = uuid.uuid4()
    item.parsed_recipe = None
    item.last_successful_stage = None
    return item


def _make_task(items: list[ImportItem], job: SimpleNamespace) -> ExtractRecipeTask:
    task = ExtractRecipeTask()
    task.database = _FakeDatabase(items, job)
    task.user_id = uuid.uuid4()
    return task


def test_image_extract_fetches_s3_and_calls_vision():
    """share-img-1: image branch reads S3 bytes and runs vision extractor."""
    job = _make_job()
    s3_key = "imports/abc-user/photo.jpg"
    item = _make_image_item(job.id, s3_key)
    task = _make_task([item], job)

    fake_aws = SimpleNamespace(read_object=MagicMock(return_value=b"\xff\xd8imgbytes"))
    recipe = ExtractedRecipe(name="Vision Recipe", ingredients=[])
    vision_result = ExtractionResult(
        success=True,
        recipes=[recipe],
        extractor_used="vision_ai",
        ai_cost_cents=12,
    )

    with patch.object(task, "_aws_service", return_value=fake_aws), \
         patch(
             "utils.tasks.import_tasks.extract_recipe_task.extract_recipe_from_image",
             return_value=vision_result,
         ) as mock_vision:
        task._extract_single_item(str(item.id))

    fake_aws.read_object.assert_called_once()
    args, _kwargs = fake_aws.read_object.call_args
    # First arg is s3_key; second is the bucket from constants. Don't pin the
    # bucket value here — env-driven and not the contract under test.
    assert args[0] == s3_key

    mock_vision.assert_called_once()
    passed_bytes = mock_vision.call_args.args[0]
    assert passed_bytes == b"\xff\xd8imgbytes"

    assert item.parsed_recipe["name"] == "Vision Recipe"
    assert item.status == "awaiting_review"
    assert item.ai_cost_cents == 12
    assert item.last_successful_stage == "extracted"
    assert job.total_ai_cost_cents == 12


def test_image_extract_falls_back_to_raw_data_s3_key():
    """share-img-1: if `s3_key` column is unset (legacy item), pull from
    raw_data. start_import writes both, so this is a defensive belt-and-
    suspenders for any pre-existing rows in the queue.
    """
    job = _make_job()
    s3_key = "imports/abc-user/legacy.jpg"
    item = _make_image_item(job.id, s3_key)
    item.s3_key = None  # legacy: only in raw_data
    task = _make_task([item], job)

    fake_aws = SimpleNamespace(read_object=MagicMock(return_value=b"bytes"))
    vision_result = ExtractionResult(
        success=True,
        recipes=[ExtractedRecipe(name="R", ingredients=[])],
        extractor_used="vision_ai",
        ai_cost_cents=1,
    )

    with patch.object(task, "_aws_service", return_value=fake_aws), \
         patch(
             "utils.tasks.import_tasks.extract_recipe_task.extract_recipe_from_image",
             return_value=vision_result,
         ):
        task._extract_single_item(str(item.id))

    fake_aws.read_object.assert_called_once()
    assert fake_aws.read_object.call_args.args[0] == s3_key
    assert item.status == "awaiting_review"


def test_image_without_s3_key_marks_item_failed():
    """An image item missing both `s3_key` and `raw_data.s3_key` is a
    contract violation. Surface it as a failed item so the user sees it
    in the import-review queue rather than swallowing silently.
    """
    job = _make_job()
    item = _make_image_item(job.id, "ignored")
    item.s3_key = None
    item.raw_data = {}  # nothing to fall back to
    task = _make_task([item], job)

    with patch.object(task, "_aws_service", return_value=MagicMock()), \
         patch(
             "utils.tasks.import_tasks.extract_recipe_task.extract_recipe_from_image",
         ) as mock_vision:
        result = task._extract_single_item(str(item.id))

    # The except-block in _extract_single_item catches the ValueError,
    # marks failed, and returns a {status: "failed"} dict.
    assert result["status"] == "failed"
    assert item.status == "failed"
    assert item.error_code == "EXTRACTION_ERROR"
    mock_vision.assert_not_called()
