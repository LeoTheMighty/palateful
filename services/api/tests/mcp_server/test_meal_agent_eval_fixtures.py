"""msa-4 — cross-check the Meal-agent eval fixtures against the real MCP tools.

`services/eval` can't import `services/api`, so the eval-side test
(`services/eval/tests/test_meal_agent_fixtures.py`) validates the
fixtures' internal consistency only. This test closes the other half:
every tool name and every argument key the 7 fixtures expect has to
exist on the actual `@mcp.tool()` signature, with a compatible type.

That's the regression the epic is buying — rename a tool, drop a
parameter, or flip `meal_id` back off `create_meal_event`, and these
fixtures stop describing reality. Without this test they'd keep passing
as well-formed JSON while asserting nothing about the code.
"""

from __future__ import annotations

import inspect
import json
import types
import typing
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE_DIR = _REPO_ROOT / "services/eval/fixtures"
_FIXTURE_NAMES = [
    "meal_create_from_explicit_ids.json",
    "meal_create_from_fuzzy_names.json",
    "meal_create_with_clarification_needed.json",
    "meal_update_name.json",
    "meal_add_and_remove_component.json",
    "meal_archive_with_references.json",
    "meal_event_with_meal_id.json",
]

#: Modules whose module-level `async def`s are the registered MCP tools.
_TOOL_MODULES = (
    "mcp_server.tools.meals",
    "mcp_server.tools.meal_planning",
    "mcp_server.tools.recipes",
    "mcp_server.tools.agent_tools",
)


def _load(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _tool_functions() -> dict[str, typing.Callable]:
    """Map tool name -> function, as the MCP server exposes them."""
    import importlib

    tools: dict[str, typing.Callable] = {}
    for module_path in _TOOL_MODULES:
        module = importlib.import_module(module_path)
        for name, obj in vars(module).items():
            if name.startswith("_") or not callable(obj):
                continue
            if getattr(obj, "__module__", None) != module_path:
                continue
            if inspect.isfunction(obj):
                tools[name] = obj
    return tools


def _iter_scenarios(fixture: dict):
    yield fixture["id"], fixture
    for variation in fixture.get("variations", []):
        yield f"{fixture['id']}::{variation['id']}", variation


def _iter_calls(fixture: dict):
    for label, scenario in _iter_scenarios(fixture):
        for turn_index, turn in enumerate(scenario["turns"]):
            for call in turn["expected_tool_calls"]:
                yield f"{label} turn {turn_index}", call


def _accepts(annotation: typing.Any, value: typing.Any) -> bool:
    """Loose runtime type check of a fixture argument against an annotation."""
    if annotation is inspect.Parameter.empty:
        return True

    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return any(_accepts(arg, value) for arg in typing.get_args(annotation))
    if annotation is type(None):
        return value is None
    if origin is list:
        if not isinstance(value, list):
            return False
        (item_type,) = typing.get_args(annotation) or (typing.Any,)
        return all(_accepts(item_type, item) for item in value)
    if annotation is typing.Any:
        return True
    if annotation is bool:
        return isinstance(value, bool)
    if annotation is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation is str:
        return isinstance(value, str)
    return True


@pytest.mark.parametrize("name", _FIXTURE_NAMES)
def test_fixture_tool_names_exist(name):
    tools = _tool_functions()
    for where, call in _iter_calls(_load(name)):
        assert call["name"] in tools, (
            f"{where}: fixture expects tool '{call['name']}' which no MCP module exports"
        )


@pytest.mark.parametrize("name", _FIXTURE_NAMES)
def test_fixture_arguments_match_tool_signatures(name):
    tools = _tool_functions()
    for where, call in _iter_calls(_load(name)):
        fn = tools[call["name"]]
        params = inspect.signature(fn).parameters
        hints = typing.get_type_hints(fn)

        for key, value in call["arguments"].items():
            assert key in params, (
                f"{where}: {call['name']}({key}=...) — no such parameter "
                f"(has {sorted(params)})"
            )
            annotation = hints.get(key, inspect.Parameter.empty)
            assert _accepts(annotation, value), (
                f"{where}: {call['name']}({key}={value!r}) doesn't fit {annotation}"
            )

        required = {
            key
            for key, param in params.items()
            if param.default is inspect.Parameter.empty
        }
        missing = required - set(call["arguments"])
        assert not missing, (
            f"{where}: {call['name']} call omits required params {sorted(missing)}"
        )


def test_create_meal_event_exposes_meal_id_with_null_default():
    """The msa-4 signature extension itself — fixture 7 depends on it."""
    from mcp_server.tools.meal_planning import create_meal_event

    params = inspect.signature(create_meal_event).parameters
    assert "meal_id" in params
    assert params["meal_id"].default is None
    assert params["recipe_id"].default is None
    hints = typing.get_type_hints(create_meal_event)
    assert hints["meal_id"] == (str | None)


def test_archive_meal_exposes_confirmed_flag():
    """Fixture 6's second call passes confirmed=True."""
    from mcp_server.tools.meals import archive_meal

    params = inspect.signature(archive_meal).parameters
    assert params["confirmed"].default is False


def test_every_fixture_is_cross_checked():
    """Guard against a new fixture landing without being wired in here."""
    on_disk = {p.name for p in _FIXTURE_DIR.glob("meal_*.json")}
    assert on_disk == set(_FIXTURE_NAMES)
