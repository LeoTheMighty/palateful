"""AST-lint: only `unit_logging.py` may emit the `UnitAliasMiss` audit row.

The `UnitAliasMiss` `error_logs.error_type` is the single signal we use
to grow the alias seed table. If random callers start emitting that
type with their own metadata shape, we lose the ability to grep for it
reliably (and the seed harvest becomes a chore).

This test walks the repo for any string literal `"UnitAliasMiss"` outside
the sanctioned helper module and fails CI if one slips in.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Sanctioned location — the only file allowed to emit the constant.
_ALLOWED = {
    Path("libraries/utils/utils/logging/unit_logging.py"),
}

# Roots to scan. Anything else (markdown, planning docs, this test file
# itself) is skipped by extension or explicit allow-list.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAN_DIRS = (
    _REPO_ROOT / "services",
    _REPO_ROOT / "libraries",
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


def _file_emits_unit_alias_miss(path: Path) -> list[int]:
    """Return line numbers where the literal `"UnitAliasMiss"` appears."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        # If a file doesn't parse, leave the linter enforcement to the
        # syntax checker — don't double-fail here.
        return []

    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "UnitAliasMiss":
            hits.append(node.lineno)
    return hits


def test_unit_alias_miss_constant_is_only_emitted_from_helper():
    offenders: dict[Path, list[int]] = {}
    for path in _iter_python_files():
        rel = path.relative_to(_REPO_ROOT)
        if rel in _ALLOWED:
            continue
        # Skip the test file itself — referencing the constant in a docstring
        # / assertion is fine.
        if rel == Path("libraries/utils/test/test_unit_alias_miss_enforcement.py"):
            continue
        hits = _file_emits_unit_alias_miss(path)
        if hits:
            offenders[rel] = hits

    assert offenders == {}, (
        "UnitAliasMiss may only be emitted from "
        "libraries/utils/utils/logging/unit_logging.py — call "
        "log_unit_alias_miss() instead.\nOffenders:\n"
        + "\n".join(f"  {p}: lines {ls}" for p, ls in offenders.items())
    )
