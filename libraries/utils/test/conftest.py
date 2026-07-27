"""rshred1 — keep registered RED artifacts out of default collection.

Tests-first files that land on `main` ahead of their implementation error
at setup (`ModuleNotFoundError` for the module they pin), which turns the
shared `ci.yml / test` gate red for every unrelated PR. `tools/red-artifacts.txt`
is the registry of such files; entries whose path lives in *this* directory
are added to `collect_ignore` here.

Set `PYTEST_RUN_RED=1` to collect them anyway — that is how the
implementing story drives its artifact from RED to GREEN. The registry
header documents the full policy, including the requirement that the
GREEN commit delete the entry.
"""

from __future__ import annotations

import os
from pathlib import Path

RED_REGISTRY = "tools/red-artifacts.txt"
RED_OPT_IN_ENV = "PYTEST_RUN_RED"

_HERE = Path(__file__).resolve().parent


def _repo_root() -> Path | None:
    """Nearest ancestor holding the registry (None outside a checkout)."""
    for parent in _HERE.parents:
        if (parent / RED_REGISTRY).is_file():
            return parent
    return None


def _ignored_filenames() -> list[str]:
    if os.environ.get(RED_OPT_IN_ENV):
        return []

    root = _repo_root()
    if root is None:
        return []

    ignored = []
    for raw in (root / RED_REGISTRY).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel = line.split(":", 1)[0].strip()
        path = (root / rel).resolve()
        if not path.is_file():
            # A typo'd path would silently register nothing and leave the
            # gate red, which is the exact failure this registry prevents.
            raise RuntimeError(
                f"{RED_REGISTRY} registers a path that does not exist: {rel}. "
                "Fix the path, or delete the entry if the artifact is gone."
            )
        if path.parent == _HERE:
            ignored.append(path.name)
    return ignored


collect_ignore = _ignored_filenames()
