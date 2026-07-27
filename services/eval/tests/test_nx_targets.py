"""irrd-3a — guards on the nx targets that invoke the eval CLI.

The operator handoff for this story is a documented `npx nx run
eval:confidence-gate` command, so a target whose argv click rejects is a
silent trap: nx reports a non-zero exit that looks like a gate failure
but is really a usage error. These tests parse project.json and replay
each command through click's own parser — no network, no LLM, no run.

The specific rot they catch: `--env-file` / `--config` / `--verbose` are
options on the click *group*, so they must appear before the subcommand.
Every `src.main` target used to spell them after it and died with
"No such option: --env-file".
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.main import cli

PROJECT_JSON_PATH = Path(__file__).resolve().parents[1] / "project.json"

# Options declared on the `cli` group rather than on any subcommand.
GROUP_OPTIONS = {"--env-file", "-e", "--config", "-c", "--verbose", "-v"}


def _load_targets() -> dict[str, str]:
    payload = json.loads(PROJECT_JSON_PATH.read_text(encoding="utf-8"))
    return {
        name: target["options"]["command"]
        for name, target in payload["targets"].items()
        if "command" in target.get("options", {})
    }


def _cli_argv(command: str) -> list[str] | None:
    """Return the argv passed to `python -m src.main`, or None if not a CLI target."""
    parts = shlex.split(command)
    if "src.main" not in parts:
        return None
    return parts[parts.index("src.main") + 1 :]


CLI_TARGETS = sorted(
    (name, argv)
    for name, cmd in _load_targets().items()
    if (argv := _cli_argv(cmd)) is not None
)


def test_project_json_declares_cli_targets() -> None:
    """Sanity: the parsing above actually found the targets it guards."""
    names = {name for name, _ in CLI_TARGETS}
    assert {"run", "run-fixtures", "confidence-gate"} <= names


@pytest.mark.parametrize("name,argv", CLI_TARGETS, ids=[n for n, _ in CLI_TARGETS])
def test_group_options_precede_the_subcommand(name: str, argv: list[str]) -> None:
    """`--env-file` and friends belong to the group, so nothing may follow the subcommand."""
    subcommand_index = next(
        (i for i, token in enumerate(argv) if not token.startswith("-")),
        None,
    )
    assert subcommand_index is not None, f"{name}: no subcommand in {argv}"

    misplaced = [t for t in argv[subcommand_index + 1 :] if t in GROUP_OPTIONS]
    assert not misplaced, (
        f"{name}: group-level option(s) {misplaced} appear after the subcommand "
        f"'{argv[subcommand_index]}'; click will reject them. Move them before it."
    )


@pytest.mark.parametrize("name,argv", CLI_TARGETS, ids=[n for n, _ in CLI_TARGETS])
def test_target_argv_parses(name: str, argv: list[str]) -> None:
    """Replay the target's argv through click with --help appended: parse errors surface as exit 2."""
    result = CliRunner().invoke(cli, [*argv, "--help"])
    assert result.exit_code == 0, f"{name}: `{' '.join(argv)}` -> {result.output}"


def test_confidence_gate_target_is_the_documented_command() -> None:
    """The irrd-3a operator handoff in MANUAL.md/README.md points at this exact target."""
    command = _load_targets()["confidence-gate"]
    assert command == "poetry run python -m src.main --env-file .env.eval confidence-gate"
