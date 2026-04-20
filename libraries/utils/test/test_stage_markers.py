"""Tests verifying each pipeline stage writes its last_successful_stage marker
on successful completion.

These tests validate that the retry endpoint (mvp-6) will see the right marker
value for each stage's happy path.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_item(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        import_job_id=uuid.uuid4(),
        status="pending",
        last_successful_stage=None,
        parsed_recipe=None,
        raw_data={"text": "some text"},
        source_type="photo",
        source_url=None,
        ai_cost_cents=0,
        error_message=None,
        error_code=None,
        retry_count=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_database(item, job=None):
    database = MagicMock()

    def find_by(model, **_kwargs):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job or SimpleNamespace(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                total_items=1,
                processed_items=0,
                failed_items=0,
                succeeded_items=0,
                pending_review_items=0,
                status="processing",
                total_ai_cost_cents=0,
            )
        return None

    database.find_by.side_effect = find_by
    database.db = MagicMock()
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("matching", 1)
    ]
    database.db.commit = MagicMock()
    return database


# ------------------------------------------------------------------
# parse_source_task: marks "parsed" before dispatching extraction
# ------------------------------------------------------------------


def test_parse_source_task_marks_parsed_on_pending_items():
    from utils.constants import STAGE_PARSED
    from utils.tasks.import_tasks.parse_source_task import ParseSourceTask

    task = ParseSourceTask()

    # Build two pending items for the same job.
    items = [_make_item(status="pending"), _make_item(status="pending")]
    job = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    database = MagicMock()
    database.db = MagicMock()
    query_chain = MagicMock()
    query_chain.filter.return_value.all.return_value = items
    database.db.query.return_value = query_chain
    database.db.commit = MagicMock()

    task.database = database

    with patch(
        "utils.tasks.import_tasks.extract_recipe_task.extract_task"
    ) as mock_extract:
        task._dispatch_extraction_tasks(job)

    for it in items:
        assert it.last_successful_stage == STAGE_PARSED
    # Extract task was dispatched at least once.
    assert mock_extract.delay.called


# ------------------------------------------------------------------
# extract_recipe_task: marks "extracted" when item transitions to matching
# ------------------------------------------------------------------


def test_extract_task_marks_extracted_on_success():
    from utils.constants import STAGE_EXTRACTED
    from utils.services.recipe_extractors import ExtractionResult
    from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask

    task = ExtractRecipeTask()
    item = _make_item()
    task.database = _make_database(item)

    # Build a successful ExtractionResult.
    recipe_stub = SimpleNamespace(
        name="Test Recipe",
        description=None,
        ingredients=[],
        steps=None,
        instructions="Mix it up.",
        servings=None,
        prep_time_minutes=None,
        cook_time_minutes=None,
        total_time_minutes=None,
        image_url=None,
        source_url=None,
        author=None,
        cuisine=None,
        category=None,
        keywords=None,
        primary_vibe=None,
        secondary_vibe=None,
    )
    result = ExtractionResult(
        success=True,
        recipe=recipe_stub,
        extractor_used="text_ai",
        ai_cost_cents=5,
    )

    task._update_item_from_result(item, result)

    assert item.status == "awaiting_review"
    assert item.last_successful_stage == STAGE_EXTRACTED


def test_extract_task_failure_does_not_mark_stage():
    """Failed extraction must not advance the stage marker."""
    from utils.services.recipe_extractors import ExtractionResult
    from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask

    task = ExtractRecipeTask()
    item = _make_item()
    task.database = _make_database(item)

    result = ExtractionResult(
        success=False,
        error_message="boom",
        error_code="TEST_ERROR",
        extractor_used="text_ai",
        ai_cost_cents=0,
    )

    task._update_item_from_result(item, result)

    assert item.status == "failed"
    assert item.last_successful_stage is None


# match_ingredients_task was retired in epic-ingredients-string-simplification.
# The former STAGE_MATCHED transition is now unused at runtime but remains
# in the STAGE_PLAN for back-compat with legacy `last_successful_stage='matched'`
# rows on retry — no new stage-marker test needed.
