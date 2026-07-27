"""nx target wiring for the eval service (bugs-imp-pho-7).

`CLAUDE.md` makes `npx nx run ...` the supported entry point, so a target
that shells out to a command click can't parse is a broken door with a
sign on it. These tests parse `project.json` — no subprocess, no spend.

The `--env-file` ordering assertion is a real regression guard: every
`run-*` target originally passed `--env-file` *after* the subcommand, but
it is an option on the click **group**, so all of them died with
"No such option: --env-file" before they ever reached a suite.
"""

import json
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_JSON = SERVICE_DIR / "project.json"
CLI_ENTRY = "python -m src.main"


def _targets() -> dict[str, dict]:
    return json.loads(PROJECT_JSON.read_text())["targets"]


def _command(target: str) -> str:
    return _targets()[target]["options"]["command"]


def _cli_targets() -> list[str]:
    return [name for name, spec in _targets().items() if CLI_ENTRY in spec["options"]["command"]]


def test_run_vision_target_exists():
    assert "run-vision" in _targets(), "every eval suite gets its own nx run-* target"


def test_run_vision_selects_the_vision_suite():
    assert "--suite vision_extraction" in _command("run-vision")


def test_capture_vision_baseline_target_invokes_the_capture_script():
    assert "scripts/capture_vision_baseline.py" in _command("capture-vision-baseline")


def test_capture_vision_baseline_target_makes_no_run_call():
    # Capture reads a results JSON; it must never be able to bill a run.
    assert CLI_ENTRY not in _command("capture-vision-baseline")


@pytest.mark.parametrize("target", _cli_targets())
def test_env_file_precedes_the_subcommand(target: str):
    """--env-file is a group option, so it must sit before the subcommand."""
    command = _command(target)
    if "--env-file" not in command:
        return
    entry_end = command.index(CLI_ENTRY) + len(CLI_ENTRY)
    tail = command[entry_end:].split()
    assert tail[0] == "--env-file", f"{target}: --env-file must directly follow {CLI_ENTRY!r}"


@pytest.mark.parametrize("target", _cli_targets())
def test_cli_targets_run_from_the_service_dir(target: str):
    assert _targets()[target]["options"]["cwd"] == "{projectRoot}"


def test_every_non_opt_in_suite_has_a_target():
    """Guard the inverse too: run-vision must not be silently dropped."""
    from src.main import ALL_SUITES, OPT_IN_SUITES

    commands = " ".join(spec["options"]["command"] for spec in _targets().values())
    for suite in ALL_SUITES:
        if suite in {"recipe_parse", "chat_agent"}:
            continue  # judged suites are driven by eval-llm --cases, not --suite
        assert f"--suite {suite}" in commands, f"no nx target runs the {suite} suite"

    assert OPT_IN_SUITES == ["vision_extraction"]
