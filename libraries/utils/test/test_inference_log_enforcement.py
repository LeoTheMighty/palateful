"""AST-lint: only ``inference_logging.py`` may emit ``InferredFieldClamped``.

efi-1 — the ``InferredFieldClamped`` ``error_logs.error_type`` is the
single signal the correction-log dashboard reads to see how often the
extractor guessed out-of-range. If random callers start emitting that
type with their own metadata shape, the dashboard's aggregations go
wobbly and the feedback-log loses its shape.

This test walks the repo for any string literal ``"InferredFieldClamped"``
outside the sanctioned helper module and fails CI if one slips in.

Mirrors ``test_stage_transition_enforcement.py`` and
``test_unit_alias_miss_enforcement.py`` verbatim so the pattern stays
recognizable.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Sanctioned location — the only file allowed to emit the constant.
_ALLOWED = {
    Path("libraries/utils/utils/logging/inference_logging.py"),
}

# Roots to scan. Walk both services and libraries so any future caller
# that bypasses the helper surfaces immediately.
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


def _file_emits_constant(path: Path) -> list[int]:
    """Return line numbers where the literal ``"InferredFieldClamped"`` appears."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        # If a file doesn't parse, leave the linter enforcement to the
        # syntax checker — don't double-fail here.
        return []

    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "InferredFieldClamped":
            hits.append(node.lineno)
    return hits


def test_inferred_field_clamped_constant_is_only_emitted_from_helper():
    offenders: dict[Path, list[int]] = {}
    for path in _iter_python_files():
        rel = path.relative_to(_REPO_ROOT)
        if rel in _ALLOWED:
            continue
        # Skip the test file itself — referencing the constant in a docstring
        # / assertion is fine.
        if rel == Path(
            "libraries/utils/test/test_inference_log_enforcement.py"
        ):
            continue
        hits = _file_emits_constant(path)
        if hits:
            offenders[rel] = hits

    assert offenders == {}, (
        "InferredFieldClamped may only be emitted from "
        "libraries/utils/utils/logging/inference_logging.py — call "
        "log_inferred_field_clamp() instead.\nOffenders:\n"
        + "\n".join(f"  {p}: lines {ls}" for p, ls in offenders.items())
    )
