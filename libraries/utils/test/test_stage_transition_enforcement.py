"""AST-lint: only `stage_logging.py` may emit the `StageTransition` audit row.

`StageTransition` is the `error_logs.error_type` that the Flutter caret
expansion reads through `GetImportItemTelemetry`. If random callers
start emitting that type with their own metadata shape, the telemetry
endpoint's status-derivation stops being reliable.

This test walks the repo for any string literal `"StageTransition"`
outside the sanctioned helper module and fails CI if one slips in.

Mirrors `test_unit_alias_miss_enforcement.py` verbatim so the pattern
stays recognizable.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Sanctioned location — the only file allowed to emit the constant.
_ALLOWED = {
    Path("libraries/utils/utils/logging/stage_logging.py"),
}

# Roots to scan. Scoped to the import + parser task modules per the epic
# spec — those are the hot paths that are required to funnel stage
# transitions through `log_stage_transition`. Test fixtures and mock
# factories are intentionally excluded: a test `MockErrorLog` that
# mirrors the constant for assertion shape is a desirable pattern, not a
# linter offense.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAN_DIRS = (
    _REPO_ROOT / "libraries" / "utils" / "utils" / "tasks" / "import_tasks",
    _REPO_ROOT / "libraries" / "utils" / "utils" / "tasks" / "parser_tasks",
    _REPO_ROOT / "libraries" / "utils" / "utils" / "logging",
)

# Skip vendored / generated code, virtualenvs, build dirs.
_SKIP_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    ".pytest_cache",
    "_bmad-output",
    "_bmad",
    "archive",
}


def _iter_python_files():
    for root in _SCAN_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            yield path


def _file_emits_stage_transition(path: Path) -> list[int]:
    """Return line numbers where the literal `"StageTransition"` appears."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        # If a file doesn't parse, leave the linter enforcement to the
        # syntax checker — don't double-fail here.
        return []

    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "StageTransition":
            hits.append(node.lineno)
    return hits


def test_stage_transition_constant_is_only_emitted_from_helper():
    offenders: dict[Path, list[int]] = {}
    for path in _iter_python_files():
        rel = path.relative_to(_REPO_ROOT)
        if rel in _ALLOWED:
            continue
        # Skip the test file itself — referencing the constant in a docstring
        # / assertion is fine.
        if rel == Path(
            "libraries/utils/test/test_stage_transition_enforcement.py"
        ):
            continue
        hits = _file_emits_stage_transition(path)
        if hits:
            offenders[rel] = hits

    assert offenders == {}, (
        "StageTransition may only be emitted from "
        "libraries/utils/utils/logging/stage_logging.py — call "
        "log_stage_transition() instead.\nOffenders:\n"
        + "\n".join(f"  {p}: lines {ls}" for p, ls in offenders.items())
    )
