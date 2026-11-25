"""msa-4 — loader + structural validator for the Meal-agent eval fixtures.

The 7 fixtures in ``services/eval/fixtures/meal_*.json`` describe
conversational traces over the Meal MCP tool surface: what the user says,
which tools the AI is expected to call, in what order, with which
arguments, and what the tool handed back.

Why a validator and not just data: the fixtures encode the epic's
confirmation policy and its anti-guessing bar (Design Principles 6 + 7).
A fixture that quietly drifts out of sync with those rules — a
clarifying turn that also writes, an ``archive_meal(confirmed=True)``
issued before the user ever confirmed, a component id the AI could not
have learned — would still be valid JSON while asserting nothing. The
rules below are the CI-gated bar; ``validate_fixture`` returns a list of
human-readable violations (empty means clean).

This module is pure Python. It does NOT call OpenAI and does not import
``services/api`` — the eval package doesn't depend on it. Cross-checking
the expected tool names/arguments against the real MCP signatures is done
API-side in ``services/api/tests/test_meal_agent_eval_fixtures.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------

#: Tools that mutate Meal / calendar state. A call to one of these is a
#: "write" for the purposes of the zero-write assertions.
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "create_meal",
        "update_meal",
        "add_recipe_to_meal",
        "remove_recipe_from_meal",
        "archive_meal",
        "create_meal_event",
    }
)

#: Read-only tools the AI is allowed to use while resolving names.
READ_TOOLS: frozenset[str] = frozenset(
    {
        "get_meal",
        "list_meals",
        "get_recipe",
        "list_recipes",
        "search_recipes",
        "list_meal_events",
        "get_meal_event",
    }
)

KNOWN_TOOLS: frozenset[str] = WRITE_TOOLS | READ_TOOLS

#: filename -> epic fixture number (epic § "Eval fixtures").
FIXTURE_FILES: dict[str, int] = {
    "meal_create_from_explicit_ids.json": 1,
    "meal_create_from_fuzzy_names.json": 2,
    "meal_create_with_clarification_needed.json": 3,
    "meal_update_name.json": 4,
    "meal_add_and_remove_component.json": 5,
    "meal_archive_with_references.json": 6,
    "meal_event_with_meal_id.json": 7,
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_REQUIRED_FIXTURE_KEYS = {
    "id",
    "epic_fixture",
    "story",
    "title",
    "description",
    "tags",
    "context",
    "turns",
    "assertions",
}
_REQUIRED_ASSERTION_KEYS = {
    "committed_write_calls",
    "blocked_write_calls",
    "required_tools",
    "forbidden_tools",
}
_REQUIRED_TURN_KEYS = {
    "user",
    "expected_tool_calls",
    "expect_clarifying_question",
    "expect_response_contains",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def fixtures_dir() -> Path:
    """Absolute path to ``services/eval/fixtures``."""
    return Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(path: str | Path) -> dict[str, Any]:
    """Load one fixture JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_all_fixtures(directory: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load every known Meal-agent fixture, keyed by filename.

    Only the filenames in :data:`FIXTURE_FILES` are loaded — an unrelated
    JSON file dropped in ``fixtures/`` is ignored here and caught by the
    exactly-7 test instead.
    """
    root = Path(directory) if directory is not None else fixtures_dir()
    return {
        name: load_fixture(root / name)
        for name in sorted(FIXTURE_FILES)
        if (root / name).is_file()
    }


# ---------------------------------------------------------------------------
# Traversal helpers
# ---------------------------------------------------------------------------


def iter_scenarios(fixture: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(label, scenario)`` for the main track plus every variation.

    A scenario is any dict carrying ``context`` / ``turns`` / ``assertions``.
    Variations (fixture 5 has one) are full scenarios with their own
    starting state, so they get validated by exactly the same rules.
    """
    yield fixture.get("id", "<unknown>"), fixture
    for variation in fixture.get("variations", []):
        yield f"{fixture.get('id')}::{variation.get('id', '<unnamed>')}", variation


def iter_tool_calls(
    scenario: dict[str, Any],
) -> Iterator[tuple[int, int, dict[str, Any]]]:
    """Yield ``(turn_index, call_index, call)`` across a scenario's turns."""
    for turn_index, turn in enumerate(scenario.get("turns", [])):
        for call_index, call in enumerate(turn.get("expected_tool_calls", [])):
            yield turn_index, call_index, call


def is_blocked(call: dict[str, Any]) -> bool:
    """True when the tool answered ``CONFIRMATION_REQUIRED`` (no mutation)."""
    result = call.get("tool_result")
    return isinstance(result, dict) and result.get("error") == "CONFIRMATION_REQUIRED"


def count_write_calls(scenario: dict[str, Any]) -> tuple[int, int]:
    """Return ``(committed, blocked)`` write-call counts for a scenario."""
    committed = blocked = 0
    for _, _, call in iter_tool_calls(scenario):
        if call.get("name") not in WRITE_TOOLS:
            continue
        if is_blocked(call):
            blocked += 1
        else:
            committed += 1
    return committed, blocked


def _uuids_in(value: Any) -> Iterator[str]:
    """Yield every UUID-shaped string nested anywhere inside ``value``."""
    if isinstance(value, str):
        if _UUID_RE.match(value):
            yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _uuids_in(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _uuids_in(nested)


def _malformed_uuids_in(value: Any) -> Iterator[str]:
    """Yield id-looking strings that are NOT valid lowercase hex UUIDs.

    Guards the documented seed-data trap: PostgreSQL only accepts hex
    characters, so a placeholder like ``r0000000-...`` blows up at
    insert time rather than at fixture-authoring time.
    """
    if isinstance(value, str):
        if "-" in value and len(value) == 36 and not _UUID_RE.match(value):
            yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _malformed_uuids_in(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _malformed_uuids_in(nested)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_shape(label: str, scenario: dict[str, Any], errors: list[str]) -> bool:
    """Structural checks. Returns False when the scenario is too broken
    to run the semantic rules against."""
    turns = scenario.get("turns")
    if not isinstance(turns, list) or not turns:
        errors.append(f"{label}: 'turns' must be a non-empty list")
        return False

    assertions = scenario.get("assertions")
    if not isinstance(assertions, dict):
        errors.append(f"{label}: 'assertions' must be an object")
        return False
    missing = _REQUIRED_ASSERTION_KEYS - set(assertions)
    if missing:
        errors.append(f"{label}: assertions missing {sorted(missing)}")
        return False

    ok = True
    for turn_index, turn in enumerate(turns):
        missing = _REQUIRED_TURN_KEYS - set(turn)
        if missing:
            errors.append(f"{label} turn {turn_index}: missing {sorted(missing)}")
            ok = False
            continue
        if not isinstance(turn["user"], str) or not turn["user"].strip():
            errors.append(f"{label} turn {turn_index}: 'user' must be non-empty text")
            ok = False
        if not isinstance(turn["expect_clarifying_question"], bool):
            errors.append(
                f"{label} turn {turn_index}: 'expect_clarifying_question' must be bool"
            )
            ok = False
        contains = turn["expect_response_contains"]
        if not isinstance(contains, list) or not contains:
            errors.append(
                f"{label} turn {turn_index}: 'expect_response_contains' must be "
                "a non-empty list — a turn with nothing to assert on asserts nothing"
            )
            ok = False
        if not isinstance(turn["expected_tool_calls"], list):
            errors.append(f"{label} turn {turn_index}: 'expected_tool_calls' must be a list")
            ok = False

    return ok


def _validate_calls(label: str, scenario: dict[str, Any], errors: list[str]) -> None:
    """Per-call checks: known tool, argument shape, confirmation shape."""
    for turn_index, call_index, call in iter_tool_calls(scenario):
        where = f"{label} turn {turn_index} call {call_index}"
        name = call.get("name")
        if name not in KNOWN_TOOLS:
            errors.append(f"{where}: unknown tool '{name}'")
            continue
        if not isinstance(call.get("arguments"), dict):
            errors.append(f"{where} ({name}): 'arguments' must be an object")
            continue
        if not isinstance(call.get("tool_result"), dict):
            errors.append(
                f"{where} ({name}): 'tool_result' must be an object — the trace has "
                "to say what came back or the next turn is unmotivated"
            )
            continue
        if "optional" in call and not isinstance(call["optional"], bool):
            errors.append(f"{where} ({name}): 'optional' must be bool")

        if is_blocked(call):
            if name not in WRITE_TOOLS:
                errors.append(
                    f"{where} ({name}): CONFIRMATION_REQUIRED only comes from a write tool"
                )
            result = call["tool_result"]
            if result.get("success") is not False:
                errors.append(f"{where} ({name}): blocked result needs 'success': false")
            if not str(result.get("reason", "")).strip():
                errors.append(f"{where} ({name}): blocked result needs a 'reason'")
            if call.get("optional"):
                errors.append(
                    f"{where} ({name}): a blocked call can't be optional — the "
                    "follow-up turn depends on it"
                )

        for bad in _malformed_uuids_in(call.get("arguments")):
            errors.append(
                f"{where} ({name}): '{bad}' looks like a UUID but isn't valid hex"
            )


def _validate_tool_specific(
    label: str, scenario: dict[str, Any], errors: list[str]
) -> None:
    """Rules that mirror what the MCP tools themselves enforce."""
    for turn_index, call_index, call in iter_tool_calls(scenario):
        where = f"{label} turn {turn_index} call {call_index}"
        name = call.get("name")
        args = call.get("arguments")
        if not isinstance(args, dict):
            continue

        if name == "create_meal":
            components = args.get("component_recipe_ids")
            if not isinstance(components, list) or len(components) < 2:
                errors.append(
                    f"{where}: create_meal needs >= 2 component_recipe_ids "
                    "(the tool raises ValueError below 2)"
                )
            elif len(set(components)) != len(components):
                errors.append(f"{where}: create_meal has duplicate component_recipe_ids")

        if name == "create_meal_event":
            for key in ("recipe_id", "meal_id"):
                if key not in args:
                    errors.append(
                        f"{where}: create_meal_event must state '{key}' explicitly "
                        "(null counts) so the XOR the fixture exercises is visible"
                    )
            recipe_id = args.get("recipe_id")
            meal_id = args.get("meal_id")
            if (recipe_id is None) == (meal_id is None):
                errors.append(
                    f"{where}: create_meal_event needs exactly one of recipe_id / "
                    "meal_id set (ck_meal_events_recipe_xor_meal)"
                )
            if not args.get("calendar_id"):
                errors.append(
                    f"{where}: create_meal_event needs calendar_id — CreateMealEvent "
                    "400s with MEAL_EVENT_CALENDAR_REQUIRED without it"
                )


def _validate_policy(label: str, scenario: dict[str, Any], errors: list[str]) -> None:
    """The epic's behavioural bar: zero-write clarification + confirmation gate."""
    # Zero-write: a turn where the AI is supposed to ask must not commit
    # anything. A *blocked* write is fine — that's how the AI learns it
    # needs to ask in the archive / degenerate-remove fixtures.
    for turn_index, turn in enumerate(scenario.get("turns", [])):
        if not turn.get("expect_clarifying_question"):
            continue
        committed = [
            call.get("name")
            for call in turn.get("expected_tool_calls", [])
            if call.get("name") in WRITE_TOOLS and not is_blocked(call)
        ]
        if committed:
            errors.append(
                f"{label} turn {turn_index}: clarifying turn commits writes "
                f"{committed} — Design Principle 6 says clarify before writing"
            )

    # Confirmation gate: once a tool has answered CONFIRMATION_REQUIRED,
    # the committing retry must live in a LATER turn (i.e. after the user
    # actually answered), never in the same turn.
    first_blocked: dict[str, int] = {}
    for turn_index, _, call in iter_tool_calls(scenario):
        name = call.get("name")
        if name in WRITE_TOOLS and is_blocked(call):
            first_blocked.setdefault(name, turn_index)
    for turn_index, _, call in iter_tool_calls(scenario):
        name = call.get("name")
        if name not in first_blocked or is_blocked(call):
            continue
        if turn_index <= first_blocked[name]:
            errors.append(
                f"{label} turn {turn_index}: '{name}' commits in the same turn it "
                "was gated — the user never got to confirm"
            )

    # archive_meal specifically: confirmed=True is only legitimate after a
    # gated attempt.
    for turn_index, _, call in iter_tool_calls(scenario):
        if call.get("name") != "archive_meal":
            continue
        if call.get("arguments", {}).get("confirmed") is True and (
            "archive_meal" not in first_blocked
        ):
            errors.append(
                f"{label} turn {turn_index}: archive_meal(confirmed=True) without a "
                "prior CONFIRMATION_REQUIRED — the AI must not pre-confirm for the user"
            )


def _validate_counts(label: str, scenario: dict[str, Any], errors: list[str]) -> None:
    """Declared assertion counts must match the trace they describe."""
    assertions = scenario["assertions"]
    committed, blocked = count_write_calls(scenario)
    if committed != assertions["committed_write_calls"]:
        errors.append(
            f"{label}: declares committed_write_calls="
            f"{assertions['committed_write_calls']} but the trace commits {committed}"
        )
    if blocked != assertions["blocked_write_calls"]:
        errors.append(
            f"{label}: declares blocked_write_calls="
            f"{assertions['blocked_write_calls']} but the trace blocks {blocked}"
        )

    called_required = {
        call.get("name")
        for _, _, call in iter_tool_calls(scenario)
        if not call.get("optional")
    }
    all_called = {call.get("name") for _, _, call in iter_tool_calls(scenario)}

    for tool in assertions["required_tools"]:
        if tool not in KNOWN_TOOLS:
            errors.append(f"{label}: required_tools names unknown tool '{tool}'")
        elif tool not in called_required:
            errors.append(
                f"{label}: required tool '{tool}' never appears as a non-optional call"
            )
    for tool in assertions["forbidden_tools"]:
        if tool not in KNOWN_TOOLS:
            errors.append(f"{label}: forbidden_tools names unknown tool '{tool}'")
        elif tool in all_called:
            errors.append(f"{label}: forbidden tool '{tool}' appears in the trace")


def _validate_id_provenance(
    label: str, scenario: dict[str, Any], errors: list[str]
) -> None:
    """Every id the AI passes must be one it could have learned.

    Known ids start as whatever the scenario context declares, and grow
    as tool results come back. Passing an id from nowhere is the fixture
    equivalent of the model hallucinating a UUID.
    """
    known: set[str] = set(_uuids_in(scenario.get("context", {})))
    for turn in scenario.get("turns", []):
        for call in turn.get("expected_tool_calls", []):
            args = call.get("arguments")
            if isinstance(args, dict):
                for uuid in _uuids_in(args):
                    if uuid not in known:
                        errors.append(
                            f"{label}: {call.get('name')} passes id {uuid} that never "
                            "appeared in the context or in an earlier tool result"
                        )
            known.update(_uuids_in(call.get("tool_result", {})))


def validate_fixture(fixture: dict[str, Any]) -> list[str]:
    """Validate one fixture (main track + every variation).

    Returns a list of violation strings; empty means the fixture is clean.
    """
    errors: list[str] = []

    missing = _REQUIRED_FIXTURE_KEYS - set(fixture)
    if missing:
        errors.append(f"{fixture.get('id', '<unknown>')}: missing keys {sorted(missing)}")
        return errors

    if fixture["epic_fixture"] not in range(1, 8):
        errors.append(f"{fixture['id']}: epic_fixture must be 1-7")
    if fixture["story"] != "msa-4":
        errors.append(f"{fixture['id']}: story must be 'msa-4'")
    if not fixture["tags"]:
        errors.append(f"{fixture['id']}: needs at least one tag")

    for label, scenario in iter_scenarios(fixture):
        if not _validate_shape(label, scenario, errors):
            continue
        _validate_calls(label, scenario, errors)
        _validate_tool_specific(label, scenario, errors)
        _validate_policy(label, scenario, errors)
        _validate_counts(label, scenario, errors)
        _validate_id_provenance(label, scenario, errors)

    return errors
