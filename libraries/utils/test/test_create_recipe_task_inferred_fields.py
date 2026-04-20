"""efi-3 — create_recipe_task allow-lists + dedupes inferred_fields.

The standalone ``_filter_inferred_fields`` helper is the single defense
between whatever ``user_edits`` / ``parsed_recipe`` shipped and the
``Recipe.inferred_fields`` row. Exercises the full tolerance contract:
garbage in → empty list out, never exceptions.
"""

from utils.tasks.import_tasks.create_recipe_task import _filter_inferred_fields


def test_filter_happy_path():
    result = _filter_inferred_fields(
        ["cook_time_minutes", "servings", "primary_vibe"]
    )
    assert result == ["cook_time_minutes", "servings", "primary_vibe"]


def test_filter_drops_non_allowlist():
    # `name`, `ingredients`, `steps` are NOT inferable per the epic.
    result = _filter_inferred_fields(
        ["cook_time_minutes", "name", "steps", "servings"]
    )
    assert result == ["cook_time_minutes", "servings"]


def test_filter_dedupes_preserving_order():
    result = _filter_inferred_fields(
        ["servings", "cook_time_minutes", "servings", "cook_time_minutes"]
    )
    assert result == ["servings", "cook_time_minutes"]


def test_filter_rejects_non_list_inputs():
    assert _filter_inferred_fields(None) == []
    assert _filter_inferred_fields("cook_time_minutes") == []
    assert _filter_inferred_fields({"cook_time_minutes": True}) == []
    assert _filter_inferred_fields(42) == []


def test_filter_rejects_non_string_entries():
    result = _filter_inferred_fields(
        ["cook_time_minutes", 1, None, True, {"field": "x"}, "servings"]
    )
    assert result == ["cook_time_minutes", "servings"]


def test_filter_empty_list_returns_empty():
    assert _filter_inferred_fields([]) == []
