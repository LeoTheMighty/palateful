"""rshred1 — keep registered RED artifacts out of default collection.

Tests-first files that land on `main` ahead of their implementation fail
at collection or setup (`ModuleNotFoundError` for the module they pin),
which turns the shared `ci.yml / test` gate red for every unrelated PR in
the repo. `tools/red-artifacts.txt` is the registry of such files; the
policy lives in that file's header.

Each test root that can hold a RED artifact wires itself up with a
two-line `conftest.py`::

    from utils.testing.red_registry import collect_ignore_for

    collect_ignore = collect_ignore_for(__file__)

Set `PYTEST_RUN_RED=1` to collect them anyway — that is how the
implementing story drives its artifact from RED to GREEN.
"""

from __future__ import annotations

import os
from pathlib import Path

RED_REGISTRY = "tools/red-artifacts.txt"
RED_OPT_IN_ENV = "PYTEST_RUN_RED"


def _repo_root(start: Path) -> Path | None:
    """Nearest ancestor of `start` holding the registry, else None."""
    for parent in [start, *start.parents]:
        if (parent / RED_REGISTRY).is_file():
            return parent
    return None


def registered_paths(root: Path) -> list[Path]:
    """Every path in the registry, resolved against the repo root.

    A registered path that does not exist is a hard error: a typo would
    silently register nothing and leave the gate red, which is the exact
    failure this registry exists to prevent.
    """
    paths = []
    for raw in (root / RED_REGISTRY).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel = line.split(":", 1)[0].strip()
        path = (root / rel).resolve()
        if not path.is_file():
            raise RuntimeError(
                f"{RED_REGISTRY} registers a path that does not exist: {rel}. "
                "Fix the path, or delete the entry if the artifact is gone."
            )
        paths.append(path)
    return paths


def collect_ignore_for(conftest_file: str | Path) -> list[str]:
    """Filenames pytest should skip when recursing the caller's directory.

    `collect_ignore` entries are matched per-directory, so only registry
    paths that live directly in the calling conftest's directory apply.
    """
    if os.environ.get(RED_OPT_IN_ENV):
        return []

    here = Path(conftest_file).resolve().parent
    root = _repo_root(here)
    if root is None:
        return []

    return [p.name for p in registered_paths(root) if p.parent == here]
