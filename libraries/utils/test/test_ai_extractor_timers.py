"""cmt-1 — AI extractor steps+timers parsing.

Tests `_parse_steps_with_timers` (new helper in ai_extractor.py) and the
downstream `_parse_ai_response` flow that pipes parsed steps onto
`ExtractedRecipe.steps`. Also covers `_serialize_recipe` in
`extract_recipe_task` which must carry the `timers` list through to the
`parsed_recipe` JSONB.
"""

from unittest.mock import MagicMock

from utils.services.recipe_extractors.ai_extractor import (
    AIExtractor,
    _parse_steps_with_timers,
)
from utils.services.recipe_extractors.base import ExtractedRecipe, ExtractedStep


# ---------------------------------------------------------------------
# _parse_steps_with_timers
# ---------------------------------------------------------------------


def test_parse_steps_with_timers_happy_path():
    raw = [
        {
            "order": 1,
            "instruction": "Simmer 10 min",
            "timers": [{"duration_minutes": 10, "label": "simmer"}],
        }
    ]
    parsed = _parse_steps_with_timers(raw)
    assert parsed is not None
    assert parsed[0].order == 1
    assert parsed[0].instruction == "Simmer 10 min"
    assert parsed[0].timers == [{"duration_minutes": 10, "label": "simmer"}]


def test_parse_steps_with_timers_returns_none_when_absent():
    assert _parse_steps_with_timers(None) is None
    assert _parse_steps_with_timers([]) is None
    assert _parse_steps_with_timers("not a list") is None


def test_parse_steps_with_timers_backfills_missing_order():
    raw = [{"instruction": "A"}, {"instruction": "B"}]
    parsed = _parse_steps_with_timers(raw)
    assert parsed is not None
    assert [s.order for s in parsed] == [1, 2]
    assert all(s.timers == [] for s in parsed)


def test_parse_steps_with_timers_drops_blank_instructions():
    raw = [
        {"instruction": "Good.", "order": 1},
        {"instruction": "", "order": 2},
        {"instruction": "   ", "order": 3},
    ]
    parsed = _parse_steps_with_timers(raw)
    assert parsed is not None
    assert len(parsed) == 1
    assert parsed[0].instruction == "Good."


def test_parse_steps_with_timers_non_list_timers_coerces_to_empty():
    raw = [
        {"instruction": "X", "timers": "not a list"},
        {"instruction": "Y", "timers": None},
    ]
    parsed = _parse_steps_with_timers(raw)
    assert parsed is not None
    assert parsed[0].timers == []
    assert parsed[1].timers == []


def test_parse_steps_with_timers_passes_malformed_entries_through():
    """AC7: schema is permissive; wrong-type timer entries pass through.
    create_recipe_task (cmt-2) does the strict clamp + filter."""
    raw = [
        {
            "instruction": "Bake 25 min",
            "timers": [{"duration_minutes": "25", "label": "bake"}],
        }
    ]
    parsed = _parse_steps_with_timers(raw)
    assert parsed is not None
    assert parsed[0].timers == [{"duration_minutes": "25", "label": "bake"}]


def test_parse_steps_with_timers_none_when_all_entries_garbage():
    raw = ["not a dict", 42, {"instruction": ""}]
    assert _parse_steps_with_timers(raw) is None


# ---------------------------------------------------------------------
# _parse_ai_response integration (via AIExtractor._parse_ai_response)
# ---------------------------------------------------------------------


def _make_extractor() -> AIExtractor:
    ex = AIExtractor(openai_client=MagicMock())
    return ex


def test_parse_ai_response_populates_steps_with_timers():
    """AC5: mock response with `steps:[{timers:[...]}]` flows onto
    ExtractedRecipe.steps."""
    ex = _make_extractor()
    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "steps": [
            {
                "order": 1,
                "instruction": "Simmer 10 min",
                "timers": [{"duration_minutes": 10, "label": "simmer"}],
            }
        ],
    }
    recipe = ex._parse_ai_response(data)
    assert recipe.steps is not None
    assert len(recipe.steps) == 1
    assert recipe.steps[0].timers == [
        {"duration_minutes": 10, "label": "simmer"}
    ]


def test_parse_ai_response_steps_none_when_only_instructions():
    """AC6: response with only `instructions` leaves `steps=None`."""
    ex = _make_extractor()
    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "instructions": "Mix, then bake.",
    }
    recipe = ex._parse_ai_response(data)
    assert recipe.steps is None
    assert recipe.instructions == "Mix, then bake."


def test_parse_ai_response_steps_passthrough_wrong_type_timer():
    """AC7: `timers:[{"duration_minutes":"25"}]` (string not int) is
    preserved — filtering happens at persist time (cmt-2)."""
    ex = _make_extractor()
    data = {
        "name": "Test Recipe",
        "ingredients": [],
        "steps": [
            {
                "instruction": "Bake 25 min",
                "timers": [{"duration_minutes": "25", "label": "bake"}],
            }
        ],
    }
    recipe = ex._parse_ai_response(data)
    assert recipe.steps is not None
    assert recipe.steps[0].timers == [
        {"duration_minutes": "25", "label": "bake"}
    ]


# ---------------------------------------------------------------------
# _serialize_recipe pipes timers through to parsed_recipe JSONB (AC8)
# ---------------------------------------------------------------------


def test_serialize_recipe_includes_timers_on_each_step():
    from utils.tasks.import_tasks.extract_recipe_task import _serialize_recipe

    recipe = ExtractedRecipe(
        name="R",
        ingredients=[],
        steps=[
            ExtractedStep(
                order=1,
                instruction="Simmer 10 min",
                timers=[{"duration_minutes": 10, "label": "simmer"}],
            ),
            ExtractedStep(
                order=2,
                instruction="Rest",
                timers=[],
            ),
        ],
    )

    # _serialize_recipe runs unit normalization; stub the session.
    session = MagicMock()
    serialized = _serialize_recipe(recipe, extractor_used="ai", session=session)
    assert serialized["steps"] == [
        {
            "order": 1,
            "instruction": "Simmer 10 min",
            "timers": [{"duration_minutes": 10, "label": "simmer"}],
        },
        {"order": 2, "instruction": "Rest", "timers": []},
    ]


def test_serialize_recipe_steps_none_when_no_structured_steps():
    from utils.tasks.import_tasks.extract_recipe_task import _serialize_recipe

    recipe = ExtractedRecipe(
        name="R",
        ingredients=[],
        steps=None,
        instructions="1. Mix. 2. Bake.",
    )
    session = MagicMock()
    serialized = _serialize_recipe(recipe, extractor_used="ai", session=session)
    assert serialized["steps"] is None
    assert serialized["instructions"] == "1. Mix. 2. Bake."


# ---------------------------------------------------------------------
# Prompt contains steps+timers rules (AC2)
# ---------------------------------------------------------------------


def test_prompt_mentions_timers_rules_and_examples():
    from utils.services.recipe_extractors.ai_extractor import _extraction_prompt

    prompt = _extraction_prompt()
    assert "timers" in prompt
    assert "Simmer for 10 minutes" in prompt
    assert "rise overnight" in prompt
    assert "supersedes" in prompt or "superseded" in prompt
