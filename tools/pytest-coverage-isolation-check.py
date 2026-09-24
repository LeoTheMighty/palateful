#!/usr/bin/env python3
"""covcomb1 — fail when two nx pytest targets would share a coverage data file.

coverage.py writes its data file (`.coverage`, plus `.coverage.*` parallel
fragments) relative to the process cwd unless COVERAGE_FILE says otherwise.
Several projects run `poetry run pytest` from `{workspaceRoot}`, and CI runs
them concurrently (`nx affected -t test --parallel=3`). If two of them write
data into the same place, the last one to finish runs `combine` over the
other's fragments. That is silent while every project measures the same kind
of coverage and turns into
    DataError: Can't combine branch coverage data with statement data
the moment one of them adds `--cov-branch` (PR #29). Running one target on
its own locally never shows it; this check does, without running anything.

Rule: across *different* projects, no two pytest-running targets may resolve
to the same coverage data file. Resolution is COVERAGE_FILE (relative to the
target's cwd) when the command sets it, else `<cwd>/.coverage`.

Usage:
    python3 tools/pytest-coverage-isolation-check.py            # check repo
    python3 tools/pytest-coverage-isolation-check.py --self-test

Exit codes: 0 clean, 1 collision found, 2 tooling error.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_GLOBS = ("libraries/*/project.json", "services/*/project.json")
COVERAGE_FILE_RE = re.compile(r"\bCOVERAGE_FILE=(\S+)")


def _commands(options: dict) -> list[str]:
    out: list[str] = []
    if isinstance(options.get("command"), str):
        out.append(options["command"])
    for c in options.get("commands") or []:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict) and isinstance(c.get("command"), str):
            out.append(c["command"])
    return out


def _resolve_cwd(root: Path, project_root: Path, cwd: str | None) -> Path:
    # nx:run-commands (and @nxlv/python:run-commands) default to the
    # workspace root when no cwd is given.
    if not cwd or cwd == "{workspaceRoot}":
        return root
    cwd = cwd.replace("{workspaceRoot}", str(root)).replace(
        "{projectRoot}", str(project_root)
    )
    p = Path(cwd)
    return (p if p.is_absolute() else root / p).resolve()


def data_files(root: Path) -> dict[Path, list[str]]:
    """Map resolved coverage data file -> ['project:target', ...]."""
    seen: dict[Path, list[str]] = {}
    for pattern in PROJECT_GLOBS:
        for pj in sorted(root.glob(pattern)):
            project = json.loads(pj.read_text())
            name = project.get("name", pj.parent.name)
            for tname, target in (project.get("targets") or {}).items():
                opts = target.get("options") or {}
                cwd = _resolve_cwd(root, pj.parent.resolve(), opts.get("cwd"))
                for cmd in _commands(opts):
                    if "pytest" not in cmd:
                        continue
                    m = COVERAGE_FILE_RE.search(cmd)
                    data = (cwd / m.group(1)) if m else (cwd / ".coverage")
                    key = Path(os.path.normpath(data))
                    seen.setdefault(key, []).append(f"{name}:{tname}")
    return seen


def collisions(root: Path) -> list[tuple[Path, list[str]]]:
    bad = []
    for path, users in data_files(root).items():
        projects = {u.split(":", 1)[0] for u in users}
        if len(projects) > 1:
            bad.append((path, users))
    return bad


def check(root: Path) -> int:
    bad = collisions(root)
    if not bad:
        print("pytest coverage isolation: OK")
        return 0
    print("pytest coverage isolation: FAIL", file=sys.stderr)
    for path, users in bad:
        rel = os.path.relpath(path, root)
        print(f"  {rel} is shared by: {', '.join(users)}", file=sys.stderr)
    print(
        "\nThese targets run concurrently in CI and will combine each other's\n"
        "coverage fragments. Give each its own data file, e.g. prefix the\n"
        "command with `mkdir -p coverage/<projectRoot> &&\n"
        "COVERAGE_FILE=coverage/<projectRoot>/.coverage`, or run it with\n"
        "cwd {projectRoot}. See docs/SETUP.md, 'Python test targets'.",
        file=sys.stderr,
    )
    return 1


def self_test() -> int:
    def write(root: Path, rel: str, cmd: str, cwd: str | None) -> None:
        p = root / rel / "project.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        opts: dict = {"commands": [cmd]}
        if cwd is not None:
            opts["cwd"] = cwd
        p.write_text(json.dumps({"name": Path(rel).name, "targets": {"test": {"options": opts}}}))

    cases = [
        # (description, [(rel, cmd, cwd)], expect_collision)
        ("pre-covcomb1 layout: two workspace-root targets", [
            ("libraries/a", "poetry run pytest libraries/a/", "{workspaceRoot}"),
            ("services/b", "poetry run pytest services/b/", "{workspaceRoot}"),
        ], True),
        ("missing cwd defaults to workspace root", [
            ("libraries/a", "poetry run pytest libraries/a/", None),
            ("services/b", "poetry run pytest services/b/", "{workspaceRoot}"),
        ], True),
        ("same COVERAGE_FILE copy-pasted", [
            ("libraries/a", "COVERAGE_FILE=coverage/x/.coverage poetry run pytest", "{workspaceRoot}"),
            ("services/b", "COVERAGE_FILE=coverage/x/.coverage poetry run pytest", "{workspaceRoot}"),
        ], True),
        ("isolated via COVERAGE_FILE", [
            ("libraries/a", "COVERAGE_FILE=coverage/libraries/a/.coverage poetry run pytest", "{workspaceRoot}"),
            ("services/b", "COVERAGE_FILE=coverage/services/b/.coverage poetry run pytest", "{workspaceRoot}"),
        ], False),
        ("isolated via cwd {projectRoot}", [
            ("libraries/a", "poetry run pytest", "{projectRoot}"),
            ("services/b", "poetry run pytest", "{projectRoot}"),
        ], False),
    ]
    failed = 0
    for desc, projects, expect in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for rel, cmd, cwd in projects:
                write(root, rel, cmd, cwd)
            got = bool(collisions(root))
        status = "ok" if got == expect else "FAIL"
        failed += got != expect
        print(f"  [{status}] {desc}: collision={got} (expected {expect})")
    print("self-test:", "FAIL" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--self-test"]:
            sys.exit(self_test())
        sys.exit(check(ROOT))
    except (OSError, ValueError) as exc:
        print(f"pytest coverage isolation: tooling error: {exc}", file=sys.stderr)
        sys.exit(2)
