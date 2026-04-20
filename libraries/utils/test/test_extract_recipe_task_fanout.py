"""Tests for multi-recipe fan-out in extract_recipe_task (bugs-imp-pho-2).

When the extractor returns N>1 recipes, `_update_item_from_result`
writes the first recipe into the existing item and creates N-1 sibling
ImportItems on the same ImportJob. `total_items` is bumped atomically.
On retry, existing siblings are not duplicated.

Post-epic-ingredients-string-simplification: the matching stage is
gone. After extraction, items and siblings rest at
`status="awaiting_review"` until the user approves (or the fixture-
less happy path in integration tests dispatches `create_recipe_task`).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.recipe_extractors import ExtractionResult
from utils.services.recipe_extractors.base import ExtractedRecipe
from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask


class _FakeDatabase:
    """In-memory fake of the database handle used by BaseTask.

    Stores ImportItems in a list and supports the narrow slice of the
    SQLAlchemy API the fan-out code actually uses: `scalars(select()).all()`
    filtered by `import_job_id`, plus `find_by(model, id=...)` and
    `create(row)`.
    """

    def __init__(self, items: list[ImportItem], job: SimpleNamespace):
        self.items = items
        self.job = job
        self.db = MagicMock()
        self.db.commit = MagicMock()
        self.db.refresh = MagicMock()
        self.db.scalars.side_effect = self._scalars

        # _update_job_counts uses self.database.db.query(...) — return
        # enough plausible status counts to keep it happy.
        self.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("awaiting_review", len(items)),
        ]

    def _scalars(self, _stmt):
        scalars_result = MagicMock()
        scalars_result.all.return_value = list(self.items)
        return scalars_result

    def find_by(self, model, **_kwargs):
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


def _make_job(total_items: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total_items=total_items,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
        total_ai_cost_cents=0,
        recipe_book_id=uuid.uuid4(),
    )


def _make_original_item(job_id: uuid.UUID, s3_keys: list[str]) -> ImportItem:
    item = ImportItem(
        import_job_id=job_id,
        source_type="photo",
        status="extracting",
        raw_data={"text": "OCR text", "s3_keys": s3_keys},
        ai_cost_cents=0,
        retry_count=0,
    )
    item.id = uuid.uuid4()
    item.parsed_recipe = None
    item.last_successful_stage = None
    return item


def _make_recipe(name: str) -> ExtractedRecipe:
    return ExtractedRecipe(name=name, ingredients=[])


def _make_task(items: list[ImportItem], job: SimpleNamespace) -> ExtractRecipeTask:
    task = ExtractRecipeTask()
    task.database = _FakeDatabase(items, job)
    task.user_id = uuid.uuid4()
    return task


# ------------------------------------------------------------------
# Fan-out: N=3 recipes → 3 ImportItems
# ------------------------------------------------------------------


def test_fanout_three_recipes_creates_two_siblings():
    job = _make_job()
    item = _make_original_item(job.id, s3_keys=["uploads/photo.jpg"])
    task = _make_task([item], job)

    recipes = [_make_recipe("A"), _make_recipe("B"), _make_recipe("C")]
    result = ExtractionResult(
        success=True,
        recipes=recipes,
        extractor_used="text_ai",
        ai_cost_cents=7,
    )

    task._update_item_from_result(item, result)

    assert len(task.database.items) == 3
    # Original absorbs recipes[0] at recipe_index=0
    assert item.parsed_recipe["name"] == "A"
    assert item.raw_data["recipe_index"] == 0
    assert item.raw_data["s3_keys"] == ["uploads/photo.jpg"]
    assert item.status == "awaiting_review"
    assert item.last_successful_stage == "extracted"

    # Siblings exist for recipe_index 1 and 2
    siblings = [i for i in task.database.items if i is not item]
    assert len(siblings) == 2
    indices = sorted(s.raw_data["recipe_index"] for s in siblings)
    assert indices == [1, 2]
    for s in siblings:
        assert s.import_job_id == job.id
        assert s.raw_data["s3_keys"] == ["uploads/photo.jpg"]
        assert s.status == "awaiting_review"
        assert s.last_successful_stage == "extracted"
        assert s.ai_cost_cents == 0  # no double-counting

    # total_items bumped from 1 to 3
    assert job.total_items == 3
    # AI cost from the original extractor call only
    assert job.total_ai_cost_cents == 7


# ------------------------------------------------------------------
# Single-recipe path unchanged
# ------------------------------------------------------------------


def test_single_recipe_no_fanout():
    job = _make_job()
    item = _make_original_item(job.id, s3_keys=["uploads/single.jpg"])
    task = _make_task([item], job)

    result = ExtractionResult(
        success=True,
        recipes=[_make_recipe("Only")],
        extractor_used="text_ai",
        ai_cost_cents=3,
    )

    task._update_item_from_result(item, result)

    assert len(task.database.items) == 1
    assert item.parsed_recipe["name"] == "Only"
    assert item.raw_data["recipe_index"] == 0
    assert item.status == "awaiting_review"
    assert job.total_items == 1  # unchanged


# ------------------------------------------------------------------
# Retry idempotency: don't duplicate siblings
# ------------------------------------------------------------------


def test_fanout_retry_does_not_duplicate():
    """Second call with the same recipes must not create duplicate siblings."""
    job = _make_job()
    item = _make_original_item(job.id, s3_keys=["uploads/dup.jpg"])
    task = _make_task([item], job)

    recipes = [_make_recipe("R0"), _make_recipe("R1"), _make_recipe("R2")]
    result = ExtractionResult(
        success=True,
        recipes=recipes,
        extractor_used="text_ai",
        ai_cost_cents=5,
    )

    task._update_item_from_result(item, result)
    first_count = len(task.database.items)
    assert first_count == 3

    # Simulate a Celery retry — same extractor result, same original item.
    # Reset the original's state to what it would have been at retry.
    # In reality the retry would re-run extraction and get the same array.
    task._update_item_from_result(item, result)

    # Still 3 items — no duplicates.
    assert len(task.database.items) == 3


# ------------------------------------------------------------------
# Failure path: empty recipes → item failed, no siblings
# ------------------------------------------------------------------


def test_empty_recipes_marks_item_failed():
    job = _make_job()
    item = _make_original_item(job.id, s3_keys=["uploads/bad.jpg"])
    task = _make_task([item], job)

    result = ExtractionResult(
        success=False,
        error_message="no recipe found",
        error_code="AI_NO_RECIPE_FOUND",
        extractor_used="text_ai",
    )

    task._update_item_from_result(item, result)

    assert item.status == "failed"
    assert item.error_code == "AI_NO_RECIPE_FOUND"
    assert item.retry_count == 1
    assert len(task.database.items) == 1  # no siblings
    assert job.total_items == 1


# ------------------------------------------------------------------
# s3_keys copied verbatim to siblings (source-photo provenance)
# ------------------------------------------------------------------


def test_fanout_preserves_s3_keys_on_siblings():
    job = _make_job()
    item = _make_original_item(
        job.id, s3_keys=["uploads/a.jpg", "uploads/b.jpg"]
    )
    task = _make_task([item], job)

    recipes = [_make_recipe(f"R{i}") for i in range(3)]
    result = ExtractionResult(
        success=True,
        recipes=recipes,
        extractor_used="text_ai",
        ai_cost_cents=4,
    )

    task._update_item_from_result(item, result)

    for row in task.database.items:
        assert row.raw_data["s3_keys"] == ["uploads/a.jpg", "uploads/b.jpg"]
