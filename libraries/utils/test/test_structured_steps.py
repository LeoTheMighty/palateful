"""Tests for structured recipe step extraction (mvp-2).

Covers:
- text_extractor._parse_steps happy path and malformed fallback
- text_extractor._parse_response propagates structured steps through
  the ExtractedRecipe dataclass
- extract_recipe_task._update_item_from_result serializes `steps` onto
  item.parsed_recipe so create_recipe_task can persist them without
  falling back to the regex-split path
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_item(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        import_job_id=uuid.uuid4(),
        status="extracting",
        last_successful_stage="parsed",
        parsed_recipe=None,
        raw_data={"text": "..."},
        source_type="photo",
        source_url=None,
        ai_cost_cents=0,
        error_message=None,
        error_code=None,
        retry_count=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_database(item):
    database = MagicMock()

    def find_by(model, **_):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
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
# _parse_steps — directly exercises the helper
# ------------------------------------------------------------------


def test_parse_steps_happy_path():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [
        {"instruction": "Preheat oven to 350F.", "order": 1},
        {"instruction": "Mix dry ingredients.", "order": 2},
        {"instruction": "Bake for 25 minutes.", "order": 3},
    ]
    steps = _parse_steps(raw)
    assert steps is not None
    assert len(steps) == 3
    assert steps[0].order == 1
    assert steps[0].instruction == "Preheat oven to 350F."
    assert steps[2].instruction == "Bake for 25 minutes."


def test_parse_steps_backfills_missing_order():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [
        {"instruction": "First step."},
        {"instruction": "Second step."},
    ]
    steps = _parse_steps(raw)
    assert steps is not None
    assert [s.order for s in steps] == [1, 2]


def test_parse_steps_drops_entries_with_blank_instruction():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [
        {"instruction": "Good."},
        {"instruction": ""},
        {"instruction": "   "},
        {"instruction": "Also good.", "order": 9},
    ]
    steps = _parse_steps(raw)
    assert steps is not None
    assert len(steps) == 2
    assert steps[0].instruction == "Good."
    assert steps[1].instruction == "Also good."
    assert steps[1].order == 9


def test_parse_steps_none_when_input_missing():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    assert _parse_steps(None) is None
    assert _parse_steps([]) is None


def test_parse_steps_none_when_input_not_a_list():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    assert _parse_steps("not a list") is None
    assert _parse_steps({"instruction": "oops"}) is None


def test_parse_steps_none_when_all_entries_are_garbage():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [
        {"instruction": None},  # wrong type
        "just a string",  # not a dict
        42,  # not a dict
        {"instruction": ""},  # blank
    ]
    assert _parse_steps(raw) is None


def test_parse_steps_coerces_string_order():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [{"instruction": "Do thing", "order": "1"}]
    steps = _parse_steps(raw)
    assert steps is not None
    assert steps[0].order == 1


def test_parse_steps_backfills_when_order_is_garbage():
    from utils.services.recipe_extractors.text_extractor import _parse_steps

    raw = [{"instruction": "Do thing", "order": "not a number"}]
    steps = _parse_steps(raw)
    assert steps is not None
    assert steps[0].order == 1  # backfilled by position


# ------------------------------------------------------------------
# _parse_response — exercises the full LLM → ExtractedRecipe conversion
# ------------------------------------------------------------------


def test_parse_response_populates_both_steps_and_instructions():
    from utils.services.recipe_extractors.text_extractor import _parse_response

    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "steps": [
            {"instruction": "Step one.", "order": 1},
            {"instruction": "Step two.", "order": 2},
        ],
    }
    recipe = _parse_response(data)
    assert recipe.steps is not None
    assert len(recipe.steps) == 2
    assert recipe.steps[0].instruction == "Step one."
    # instructions string is also populated (legacy fallback shape)
    assert recipe.instructions is not None
    assert "Step one." in recipe.instructions
    assert "Step two." in recipe.instructions


def test_parse_response_steps_none_when_llm_omits_them():
    from utils.services.recipe_extractors.text_extractor import _parse_response

    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "instructions": "Just do it.",
    }
    recipe = _parse_response(data)
    assert recipe.steps is None
    assert recipe.instructions == "Just do it."


def test_parse_response_steps_none_when_llm_returns_malformed_steps():
    """Graceful fallback: malformed steps → recipe.steps is None,
    instructions still populated (if LLM provided them)."""
    from utils.services.recipe_extractors.text_extractor import _parse_response

    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "steps": "not-a-list",  # malformed
        "instructions": "1. Do it.",
    }
    recipe = _parse_response(data)
    assert recipe.steps is None
    assert recipe.instructions == "1. Do it."


# ------------------------------------------------------------------
# extract_recipe_task._update_item_from_result — structured steps
# flow through to item.parsed_recipe so create_recipe_task can persist
# without the regex fallback.
# ------------------------------------------------------------------


def test_update_item_from_result_serializes_steps_to_parsed_recipe():
    from utils.services.recipe_extractors import ExtractionResult
    from utils.services.recipe_extractors.base import (
        ExtractedRecipe,
        ExtractedStep,
    )
    from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask

    task = ExtractRecipeTask()
    item = _make_item()
    task.database = _make_database(item)

    recipe = ExtractedRecipe(
        name="Roasted Chicken",
        ingredients=[],
        steps=[
            ExtractedStep(order=1, instruction="Preheat to 400F."),
            ExtractedStep(order=2, instruction="Roast for 1 hour."),
        ],
        instructions="1. Preheat to 400F.\n2. Roast for 1 hour.",
    )
    result = ExtractionResult(
        success=True,
        recipe=recipe,
        extractor_used="text_ai",
        ai_cost_cents=5,
    )

    task._update_item_from_result(item, result)

    assert item.status == "awaiting_review"
    parsed = item.parsed_recipe
    assert parsed is not None
    assert parsed["steps"] == [
        {"order": 1, "instruction": "Preheat to 400F.", "timers": []},
        {"order": 2, "instruction": "Roast for 1 hour.", "timers": []},
    ]
    # Legacy instructions string is still stored as a fallback.
    assert parsed["instructions"] == "1. Preheat to 400F.\n2. Roast for 1 hour."


def test_update_item_from_result_steps_none_when_recipe_has_no_steps():
    """Graceful fallback: when the extractor couldn't produce structured
    steps, parsed_recipe['steps'] is None and downstream create_recipe_task
    falls back to its regex split of `instructions`."""
    from utils.services.recipe_extractors import ExtractionResult
    from utils.services.recipe_extractors.base import ExtractedRecipe
    from utils.tasks.import_tasks.extract_recipe_task import ExtractRecipeTask

    task = ExtractRecipeTask()
    item = _make_item()
    task.database = _make_database(item)

    recipe = ExtractedRecipe(
        name="Legacy Recipe",
        ingredients=[],
        steps=None,  # extractor couldn't produce structured steps
        instructions="1. Do this. 2. Do that.",
    )
    result = ExtractionResult(
        success=True,
        recipe=recipe,
        extractor_used="text_ai",
        ai_cost_cents=5,
    )

    task._update_item_from_result(item, result)

    assert item.status == "awaiting_review"
    parsed = item.parsed_recipe
    assert parsed["steps"] is None
    assert parsed["instructions"] == "1. Do this. 2. Do that."
