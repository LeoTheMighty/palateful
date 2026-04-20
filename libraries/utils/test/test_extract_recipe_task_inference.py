"""efi-3 — extract_recipe_task wires guardrails + penalty + persist.

Verifies the post-extraction sequence on ``_update_item_from_result``:

1. ``apply_guardrails`` clamps out-of-range numeric inferred values,
   truncates over-long strings, and drops bogus vibes from
   ``inferred_fields`` entirely.
2. ``apply_inference_penalty`` subtracts 0.05 per POST-guardrail
   inferred field (capped at 5) from the already-resolved
   ``confidence_score``.
3. ``_serialize_recipe`` writes ``inferred_fields`` at the top level of
   ``parsed_recipe`` alongside ``confidence_score`` / ``confidence_source``.

Uses the same ``_FakeDatabase`` pattern as
``test_extract_recipe_task_fanout.py`` so we don't pay the cost of a
real DB just to assert the wiring.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.recipe_extractors import ExtractionResult
from utils.services.recipe_extractors.base import ExtractedRecipe
from utils.tasks.import_tasks.extract_recipe_task import (
    ExtractRecipeTask,
    _apply_inference_post_processing,
)


class _FakeDatabase:
    def __init__(self, items: list[ImportItem], job: SimpleNamespace):
        self.items = items
        self.job = job
        self.db = MagicMock()
        self.db.commit = MagicMock()
        self.db.refresh = MagicMock()
        self.db.scalars.side_effect = self._scalars
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


def _make_item(job_id: uuid.UUID) -> ImportItem:
    item = ImportItem(
        import_job_id=job_id,
        source_type="photo",
        status="extracting",
        raw_data={"text": "OCR text", "s3_keys": ["k.jpg"]},
        ai_cost_cents=0,
        retry_count=0,
    )
    item.id = uuid.uuid4()
    item.parsed_recipe = None
    item.last_successful_stage = None
    return item


def _make_task(items, job) -> ExtractRecipeTask:
    task = ExtractRecipeTask()
    task.database = _FakeDatabase(items, job)
    task.user_id = uuid.uuid4()
    return task


# ------------------------------------------------------------------
# Helper: _apply_inference_post_processing
# ------------------------------------------------------------------


def test_post_processing_applies_guardrails_and_penalty(monkeypatch):
    """Integration: one out-of-range numeric + one bogus vibe + two
    clean inferred fields → clamped value, dropped vibe, penalty sized
    to the POST-guardrail count (3 remaining = 0.15 penalty)."""
    # Make log_inferred_field_clamp a no-op so we don't need a real DB.
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    recipe = ExtractedRecipe(
        name="Test",
        cook_time_minutes=9999,   # out of [1, 720] → clamped to 720
        servings=8,                # in range → kept
        cuisine="Italian",         # in cap → kept
        primary_vibe="bogus",      # not in VALID_VIBES → dropped
        inferred_fields=[
            "cook_time_minutes",
            "servings",
            "cuisine",
            "primary_vibe",
        ],
    )
    recipe.confidence_score = 0.80
    recipe.confidence_source = "model"

    _apply_inference_post_processing(recipe, "item-123")

    # Post-guardrails: vibe dropped, numeric clamped, string unchanged.
    assert recipe.cook_time_minutes == 720
    assert recipe.primary_vibe is None
    assert recipe.inferred_fields == [
        "cook_time_minutes",
        "servings",
        "cuisine",
    ]
    # Penalty: 3 remaining × 0.05 = 0.15. 0.80 − 0.15 = 0.65.
    assert recipe.confidence_score == 0.65
    assert recipe.confidence_source == "model"


def test_post_processing_noop_when_no_inferred_fields(monkeypatch):
    """``inferred_fields`` empty → no guardrail log, no penalty."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    recipe = ExtractedRecipe(name="Plain")
    recipe.confidence_score = 0.72
    recipe.confidence_source = "heuristic"

    _apply_inference_post_processing(recipe, "item-123")

    assert recipe.inferred_fields == []
    assert recipe.confidence_score == 0.72
    assert recipe.confidence_source == "heuristic"


def test_post_processing_tolerates_missing_confidence(monkeypatch):
    """Legacy / mock paths without ``confidence_score`` set don't crash."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    recipe = ExtractedRecipe(
        name="Legacy",
        cook_time_minutes=60,
        inferred_fields=["cook_time_minutes"],
    )
    # `confidence_score` defaults to None on ExtractedRecipe.
    assert recipe.confidence_score is None
    _apply_inference_post_processing(recipe, "item-123")
    # Guardrails still ran (60 in range → unchanged), penalty skipped.
    assert recipe.confidence_score is None
    assert recipe.inferred_fields == ["cook_time_minutes"]


# ------------------------------------------------------------------
# Integration: full _update_item_from_result path
# ------------------------------------------------------------------


def test_update_item_persists_inferred_fields_in_parsed_recipe(monkeypatch):
    """End-to-end: extractor emits inferred_fields → parsed_recipe
    carries the POST-guardrail list and the penalized confidence_score."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    job = _make_job()
    item = _make_item(job.id)
    task = _make_task([item], job)

    recipe = ExtractedRecipe(
        name="Brownies",
        cook_time_minutes=27,
        prep_time_minutes=15,
        servings=16,
        cuisine="American",
        inferred_fields=[
            "cook_time_minutes",
            "prep_time_minutes",
            "servings",
            "cuisine",
        ],
    )
    recipe.confidence_score = 0.75
    recipe.confidence_source = "model"
    result = ExtractionResult(
        success=True,
        recipes=[recipe],
        extractor_used="vision",
        ai_cost_cents=3,
    )

    task._update_item_from_result(item, result)

    assert item.parsed_recipe["inferred_fields"] == [
        "cook_time_minutes",
        "prep_time_minutes",
        "servings",
        "cuisine",
    ]
    # 4 inferred × 0.05 = 0.20 penalty. 0.75 − 0.20 = 0.55.
    assert item.parsed_recipe["confidence_score"] == 0.55
    assert item.parsed_recipe["confidence_source"] == "model"


def test_update_item_legacy_extractor_emits_empty_list(monkeypatch):
    """Extractor that emits no inferred_fields → parsed_recipe has
    ``inferred_fields: []`` (never missing / null)."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    job = _make_job()
    item = _make_item(job.id)
    task = _make_task([item], job)

    recipe = ExtractedRecipe(name="Clean Extract", cook_time_minutes=30)
    recipe.confidence_score = 0.90
    recipe.confidence_source = "model"
    result = ExtractionResult(
        success=True,
        recipes=[recipe],
        extractor_used="text_ai",
        ai_cost_cents=2,
    )

    task._update_item_from_result(item, result)

    assert item.parsed_recipe["inferred_fields"] == []
    # No penalty when count = 0.
    assert item.parsed_recipe["confidence_score"] == 0.90


def test_update_item_fanout_applies_guardrails_to_every_recipe(monkeypatch):
    """Multi-recipe fan-out → guardrails + penalty fire on every
    recipe, not just the first."""
    monkeypatch.setattr(
        "utils.services.recipe_extractors.inference_guardrails.log_inferred_field_clamp",
        lambda **kwargs: None,
    )
    job = _make_job()
    item = _make_item(job.id)
    task = _make_task([item], job)

    r1 = ExtractedRecipe(
        name="A",
        cook_time_minutes=5000,
        inferred_fields=["cook_time_minutes"],
    )
    r1.confidence_score = 0.60
    r2 = ExtractedRecipe(
        name="B",
        servings=0,
        inferred_fields=["servings"],
    )
    r2.confidence_score = 0.40
    result = ExtractionResult(
        success=True,
        recipes=[r1, r2],
        extractor_used="vision",
        ai_cost_cents=6,
    )

    task._update_item_from_result(item, result)

    # Original item: cook_time clamped 5000 → 720, penalty 0.05 → 0.55.
    assert item.parsed_recipe["inferred_fields"] == ["cook_time_minutes"]
    assert item.parsed_recipe["cook_time_minutes"] == 720
    assert item.parsed_recipe["confidence_score"] == pytest.approx(0.55)

    # Sibling: servings clamped 0 → 1, penalty 0.05 → 0.35.
    sibling = [i for i in task.database.items if i is not item][0]
    assert sibling.parsed_recipe["inferred_fields"] == ["servings"]
    assert sibling.parsed_recipe["servings"] == 1
    assert sibling.parsed_recipe["confidence_score"] == pytest.approx(0.35)
