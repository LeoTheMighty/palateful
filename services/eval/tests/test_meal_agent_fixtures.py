"""msa-4 — CI gate for the 7 Meal-agent eval fixtures.

The epic's bar: "all 7 fixtures must pass in CI before this epic can
ship. One failure = regression." These are pure-Python tests — they do
NOT hit OpenAI (same posture as the eri-5 ingredient-fidelity fixtures);
they gate the *contract* the fixtures encode: the tool traces, the
zero-write clarification rule, and the confirmation policy.

Second half of the file points the validator at deliberately-broken
copies of real fixtures. A structural validator that can't fail isn't a
gate, so every rule that matters has a test proving it bites.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.meal_agent_fixtures import (
    FIXTURE_FILES,
    WRITE_TOOLS,
    count_write_calls,
    fixtures_dir,
    is_blocked,
    iter_scenarios,
    iter_tool_calls,
    load_all_fixtures,
    load_fixture,
    validate_fixture,
)

_FIXTURES = load_all_fixtures()


def _fixture(name: str) -> dict:
    return _FIXTURES[name]


# ---------------------------------------------------------------------------
# Fixture inventory
# ---------------------------------------------------------------------------


def test_exactly_seven_meal_agent_fixtures_exist():
    on_disk = {p.name for p in fixtures_dir().glob("meal_*.json")}
    expected = set(FIXTURE_FILES)
    assert on_disk == expected, (
        f"Missing: {sorted(expected - on_disk)}, Unexpected: {sorted(on_disk - expected)}"
    )


def test_fixture_ids_match_filenames_and_epic_numbers():
    seen_numbers = set()
    for name, fixture in _FIXTURES.items():
        assert fixture["id"] == Path(name).stem, name
        assert fixture["epic_fixture"] == FIXTURE_FILES[name], name
        assert fixture["epic_fixture"] not in seen_numbers, f"duplicate number in {name}"
        seen_numbers.add(fixture["epic_fixture"])
    assert seen_numbers == set(range(1, 8))


@pytest.mark.parametrize("name", sorted(FIXTURE_FILES))
def test_fixture_is_structurally_valid(name):
    """The gate. Any violation here fails CI for the whole epic."""
    errors = validate_fixture(_fixture(name))
    assert errors == [], f"{name}:\n" + "\n".join(errors)


@pytest.mark.parametrize("name", sorted(FIXTURE_FILES))
def test_fixture_json_is_stable_and_pretty(name):
    """Fixtures are reviewed by humans in diffs — keep them 2-space JSON."""
    raw = (fixtures_dir() / name).read_text(encoding="utf-8")
    assert raw.endswith("\n"), f"{name}: needs a trailing newline"
    assert raw == json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + "\n", (
        f"{name}: reformat with json.dumps(..., indent=2, ensure_ascii=False)"
    )


# ---------------------------------------------------------------------------
# Per-fixture intent — one test per epic acceptance bullet
# ---------------------------------------------------------------------------


def test_fixture_1_single_create_meal_with_two_components():
    fixture = _fixture("meal_create_from_explicit_ids.json")
    creates = [
        call
        for _, _, call in iter_tool_calls(fixture)
        if call["name"] == "create_meal"
    ]
    assert len(creates) == 1
    assert len(creates[0]["arguments"]["component_recipe_ids"]) == 2
    assert count_write_calls(fixture) == (1, 0)


def test_fixture_2_clarifies_before_writing():
    fixture = _fixture("meal_create_from_fuzzy_names.json")
    first_turn = fixture["turns"][0]
    assert first_turn["expect_clarifying_question"] is True
    assert [c["name"] for c in first_turn["expected_tool_calls"] if c["name"] in WRITE_TOOLS] == []
    # Both ambiguous candidates must be named back to the user.
    assert "Kale Salad" in first_turn["expect_response_contains"]
    assert "Kale Chips" in first_turn["expect_response_contains"]
    # The write only lands on the turn after the user disambiguates.
    assert [c["name"] for c in fixture["turns"][1]["expected_tool_calls"]] == ["create_meal"]


def test_fixture_3_never_writes_at_all():
    fixture = _fixture("meal_create_with_clarification_needed.json")
    assert count_write_calls(fixture) == (0, 0)
    assert fixture["turns"][0]["expect_clarifying_question"] is True
    assert "create_meal" in fixture["assertions"]["forbidden_tools"]


def test_fixture_4_rename_only():
    fixture = _fixture("meal_update_name.json")
    calls = [call for _, _, call in iter_tool_calls(fixture)]
    assert [c["name"] for c in calls] == ["update_meal"]
    args = calls[0]["arguments"]
    assert args["name"] == "Picnic Box"
    assert "description" not in args, "rename must not smuggle a description edit"
    assert "component_recipe_ids" not in args


def test_fixture_5_add_then_remove_is_silent():
    fixture = _fixture("meal_add_and_remove_component.json")
    names = [call["name"] for _, _, call in iter_tool_calls(fixture)]
    assert names == ["add_recipe_to_meal", "remove_recipe_from_meal"]
    assert count_write_calls(fixture) == (2, 0), "non-degenerate remove must not be gated"
    assert all(not turn["expect_clarifying_question"] for turn in fixture["turns"])
    # The removal has to leave >= 2 components or it isn't the silent path.
    remove_result = fixture["turns"][1]["expected_tool_calls"][0]["tool_result"]
    assert remove_result["component_count"] >= 2


def test_fixture_5_variation_gates_degenerate_remove_then_archives():
    fixture = _fixture("meal_add_and_remove_component.json")
    variations = fixture["variations"]
    assert len(variations) == 1
    variation = variations[0]
    # 2-component starting state is what makes the remove degenerate.
    assert len(variation["context"]["meals"][0]["component_recipe_ids"]) == 2
    calls = [call for _, _, call in iter_tool_calls(variation)]
    assert [c["name"] for c in calls] == ["remove_recipe_from_meal", "archive_meal"]
    assert is_blocked(calls[0]), "remove at 2 components must return CONFIRMATION_REQUIRED"
    assert not is_blocked(calls[1])
    assert count_write_calls(variation) == (1, 1)


def test_fixture_6_archive_requires_confirmed_second_call():
    fixture = _fixture("meal_archive_with_references.json")
    calls = [call for _, _, call in iter_tool_calls(fixture)]
    assert [c["name"] for c in calls] == ["archive_meal", "archive_meal"]

    gated = calls[0]
    assert is_blocked(gated)
    assert gated["arguments"].get("confirmed") is not True
    # The reference list is what the AI surfaces — it has to be in the result.
    assert gated["tool_result"]["events"], "gate must carry the upcoming events"
    assert gated["tool_result"]["rules"], "gate must carry the active recurrence rules"

    committed = calls[1]
    assert committed["arguments"]["confirmed"] is True
    assert not is_blocked(committed)
    assert count_write_calls(fixture) == (1, 1)


def test_fixture_7_schedules_meal_id_with_null_recipe_id():
    fixture = _fixture("meal_event_with_meal_id.json")
    events = [
        call
        for _, _, call in iter_tool_calls(fixture)
        if call["name"] == "create_meal_event"
    ]
    assert len(events) == 1
    args = events[0]["arguments"]
    assert args["recipe_id"] is None, "XOR: recipe_id stays null when meal_id is set"
    assert args["meal_id"] == fixture["context"]["meals"][0]["id"]
    assert args["meal_type"] == "dinner"
    assert args["scheduled_at"].startswith("2026-08-03"), "Monday after context 'today'"
    assert args["calendar_id"] == fixture["context"]["calendar_id"]
    assert events[0]["tool_result"]["recipe"] is None


def test_every_mutation_path_in_the_epic_has_a_fixture():
    """One fixture per mutating tool — the "why 7" arithmetic from the epic."""
    covered = {
        call["name"]
        for fixture in _FIXTURES.values()
        for _, scenario in iter_scenarios(fixture)
        for _, _, call in iter_tool_calls(scenario)
        if call["name"] in WRITE_TOOLS
    }
    assert covered == set(WRITE_TOOLS), f"uncovered mutation paths: {WRITE_TOOLS - covered}"


# ---------------------------------------------------------------------------
# The validator has to bite — negative cases
# ---------------------------------------------------------------------------


def _broken(name: str):
    return copy.deepcopy(_fixture(name))


def _assert_flags(errors: list[str], needle: str):
    assert any(needle in e for e in errors), f"expected '{needle}' in {errors}"


def test_validator_rejects_missing_top_level_keys():
    fixture = _broken("meal_update_name.json")
    del fixture["assertions"]
    _assert_flags(validate_fixture(fixture), "missing keys")


def test_validator_rejects_unknown_tool():
    fixture = _broken("meal_update_name.json")
    fixture["turns"][0]["expected_tool_calls"][0]["name"] = "delete_everything"
    _assert_flags(validate_fixture(fixture), "unknown tool")


def test_validator_rejects_write_on_a_clarifying_turn():
    fixture = _broken("meal_create_from_fuzzy_names.json")
    fixture["turns"][0]["expected_tool_calls"].append(
        {
            "name": "create_meal",
            "arguments": {
                "recipe_book_id": "b0000000-0000-4000-8000-000000000001",
                "name": "Guessed It",
                "component_recipe_ids": [
                    "13000000-0000-4000-8000-000000000001",
                    "13000000-0000-4000-8000-000000000002",
                ],
            },
            "tool_result": {"id": "ea000000-0000-4000-8000-000000000009"},
        }
    )
    _assert_flags(validate_fixture(fixture), "clarify before writing")


def test_validator_rejects_same_turn_confirmation_bypass():
    fixture = _broken("meal_archive_with_references.json")
    # Hoist the confirmed retry into the gated turn.
    retry = fixture["turns"][1]["expected_tool_calls"][0]
    fixture["turns"][0]["expected_tool_calls"].append(retry)
    del fixture["turns"][1]
    fixture["assertions"]["committed_write_calls"] = 1
    _assert_flags(validate_fixture(fixture), "the user never got to confirm")


def test_validator_rejects_preemptive_confirmed_archive():
    fixture = _broken("meal_add_and_remove_component.json")
    variation = fixture["variations"][0]
    variation["turns"][1]["expected_tool_calls"][0]["arguments"]["confirmed"] = True
    _assert_flags(validate_fixture(fixture), "must not pre-confirm")


def test_validator_rejects_meal_event_with_both_ids():
    fixture = _broken("meal_event_with_meal_id.json")
    args = fixture["turns"][0]["expected_tool_calls"][2]["arguments"]
    args["recipe_id"] = "13000000-0000-4000-8000-000000000001"
    _assert_flags(validate_fixture(fixture), "exactly one of recipe_id")


def test_validator_rejects_meal_event_without_calendar_id():
    fixture = _broken("meal_event_with_meal_id.json")
    fixture["turns"][0]["expected_tool_calls"][2]["arguments"]["calendar_id"] = None
    _assert_flags(validate_fixture(fixture), "MEAL_EVENT_CALENDAR_REQUIRED")


def test_validator_rejects_create_meal_with_one_component():
    fixture = _broken("meal_create_from_explicit_ids.json")
    call = fixture["turns"][0]["expected_tool_calls"][1]
    call["arguments"]["component_recipe_ids"] = ["13000000-0000-4000-8000-000000000001"]
    _assert_flags(validate_fixture(fixture), ">= 2 component_recipe_ids")


def test_validator_rejects_hallucinated_id():
    fixture = _broken("meal_update_name.json")
    fixture["turns"][0]["expected_tool_calls"][0]["arguments"]["meal_id"] = (
        "ea000000-0000-4000-8000-0000000000ff"
    )
    _assert_flags(validate_fixture(fixture), "never appeared in the context")


def test_validator_rejects_non_hex_uuid():
    """The documented seed-data trap: 'r0000000-...' is not a valid UUID."""
    fixture = _broken("meal_update_name.json")
    fixture["turns"][0]["expected_tool_calls"][0]["arguments"]["meal_id"] = (
        "ra000000-0000-4000-8000-000000000001"
    )
    _assert_flags(validate_fixture(fixture), "isn't valid hex")


def test_validator_rejects_count_drift():
    fixture = _broken("meal_update_name.json")
    fixture["assertions"]["committed_write_calls"] = 3
    _assert_flags(validate_fixture(fixture), "the trace commits 1")


def test_validator_rejects_forbidden_tool_in_trace():
    fixture = _broken("meal_update_name.json")
    fixture["assertions"]["forbidden_tools"] = ["update_meal"]
    _assert_flags(validate_fixture(fixture), "forbidden tool 'update_meal'")


def test_validator_rejects_required_tool_that_is_only_optional():
    fixture = _broken("meal_create_from_explicit_ids.json")
    fixture["assertions"]["required_tools"] = ["list_recipes"]
    _assert_flags(validate_fixture(fixture), "never appears as a non-optional call")


def test_validator_rejects_blocked_result_without_reason():
    fixture = _broken("meal_archive_with_references.json")
    del fixture["turns"][0]["expected_tool_calls"][0]["tool_result"]["reason"]
    _assert_flags(validate_fixture(fixture), "needs a 'reason'")


def test_validator_rejects_blocked_read_tool():
    fixture = _broken("meal_update_name.json")
    fixture["turns"][0]["expected_tool_calls"] = [
        {
            "name": "list_meals",
            "arguments": {},
            "tool_result": {
                "success": False,
                "error": "CONFIRMATION_REQUIRED",
                "reason": "nope",
            },
        }
    ]
    fixture["assertions"]["required_tools"] = ["list_meals"]
    fixture["assertions"]["committed_write_calls"] = 0
    _assert_flags(validate_fixture(fixture), "only comes from a write tool")


def test_validator_rejects_empty_turns():
    fixture = _broken("meal_update_name.json")
    fixture["turns"] = []
    _assert_flags(validate_fixture(fixture), "non-empty list")


def test_validator_rejects_turn_missing_keys():
    fixture = _broken("meal_update_name.json")
    del fixture["turns"][0]["expect_response_contains"]
    _assert_flags(validate_fixture(fixture), "missing")


def test_validator_rejects_optional_blocked_call():
    fixture = _broken("meal_archive_with_references.json")
    fixture["turns"][0]["expected_tool_calls"][0]["optional"] = True
    _assert_flags(validate_fixture(fixture), "can't be optional")


def test_validator_rejects_bad_story_and_epic_number():
    fixture = _broken("meal_update_name.json")
    fixture["story"] = "msa-9"
    fixture["epic_fixture"] = 42
    errors = validate_fixture(fixture)
    _assert_flags(errors, "epic_fixture must be 1-7")
    _assert_flags(errors, "story must be 'msa-4'")


def test_load_fixture_round_trips_a_single_file():
    path = fixtures_dir() / "meal_update_name.json"
    assert load_fixture(path)["id"] == "meal_update_name"
