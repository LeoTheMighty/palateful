#!/usr/bin/env python3
"""Assert per-module coverage from a Cobertura `coverage.xml`.

Why this exists (rsh102, T2.8)
------------------------------
`services/api` pins `fail_under = 100`, so anything that lands there is
coverage-enforced by construction. `libraries/utils` sets no `fail_under`
at all — which means the rotation-self-heal probe, the highest-risk new
code in the workstream, would otherwise land in the one package where
nothing checks it. Raising `fail_under` for the whole package is a
different and much larger change (the package is not at 100% today), so
this asserts the specific modules instead.

Runs as a second command in the nx `test` target rather than as a pytest
test: a test that reads `coverage.xml` during the run it is part of can
only see the *previous* run's file, and on a fresh CI checkout there is
no previous run — it would skip exactly where it is most needed.

Usage:
    python tools/assert_module_coverage.py --xml coverage/.../coverage.xml \
        --min 100 utils/services/db_probe.py utils/services/db_credentials.py

Exit codes: 0 all modules meet the threshold; 1 one or more fall short or
the report is missing/unparsable.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _rate(element, attr: str) -> float | None:
    raw = element.get(attr)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def branch_data_present(tree) -> bool:
    """Whether the run measured branches at all.

    `branch = true` lives in `libraries/utils/pyproject.toml`, but a
    pytest invoked from the workspace root reads the ROOT config instead,
    which does not set it — every branch-rate then comes back `0` and a
    naive check reports "branch coverage 0.0%" for fully-covered code.
    That misdiagnosis costs more than the check is worth, so distinguish
    "no branches measured" from "branches missed".
    """
    root = tree.getroot()
    if root.get("branches-valid") not in (None, "0"):
        return True
    return any(
        cls.get("branch-rate") not in (None, "0")
        for cls in root.iter("class")
    )


def collect(tree) -> dict[str, tuple[float, float | None]]:
    """Map every class filename in the report to (line_rate, branch_rate).

    A filename can appear more than once (`coverage combine` over
    unremapped paths). Keep the WORST rates rather than the last ones
    seen — otherwise a fully-covered duplicate silently hides a
    poorly-covered one, and which wins depends on document order.
    """
    found: dict[str, tuple[float, float | None]] = {}
    for cls in tree.getroot().iter("class"):
        filename = cls.get("filename")
        if not filename:
            continue
        line_rate = _rate(cls, "line-rate")
        if line_rate is None:
            continue
        branch_rate = _rate(cls, "branch-rate")
        previous = found.get(filename)
        if previous is not None:
            line_rate = min(line_rate, previous[0])
            if previous[1] is not None:
                branch_rate = (
                    previous[1]
                    if branch_rate is None
                    else min(branch_rate, previous[1])
                )
        found[filename] = (line_rate, branch_rate)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path)
    parser.add_argument(
        "--min",
        type=float,
        default=100.0,
        help="minimum percent, applied to line AND branch rate (default 100)",
    )
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args(argv)

    # A gate that reports "OK" while asserting nothing is worse than no
    # gate — this tool is the only thing checking the highest-risk code
    # in a package with no `fail_under`.
    if not 0 < args.min <= 100:
        print(
            f"coverage gate: --min must be in (0, 100]; got {args.min}",
            file=sys.stderr,
        )
        return 1

    if not args.xml.exists():
        print(
            f"coverage gate: no report at {args.xml} — run the test suite "
            f"first so there is something to assert against",
            file=sys.stderr,
        )
        return 1

    try:
        tree = ET.parse(args.xml)
    except ET.ParseError as exc:
        print(f"coverage gate: {args.xml} is not parsable XML: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        # `.exists()` is true for a directory, and for a file we cannot read.
        print(f"coverage gate: cannot read {args.xml}: {exc}", file=sys.stderr)
        return 1

    found = collect(tree)
    if not branch_data_present(tree):
        # Fail rather than silently degrading to line-only. A warning on
        # stderr with exit 0 is not a gate: CI reads the exit code, so a
        # 100%-line / 0%-branch module would sail through.
        print(
            f"coverage gate: {args.xml} contains no branch data. The runner "
            f"must pass --cov-branch (see libraries/utils/project.json); "
            f"refusing to report a pass on line coverage alone.",
            file=sys.stderr,
        )
        return 1

    threshold = args.min / 100.0
    failures: list[str] = []

    for module in args.modules:
        # Cobertura writes filenames relative to the coverage source
        # root, so an exact match is too strict — but a bare `endswith`
        # has no path boundary, and `db_probe.py` would happily match
        # `vendor/third_party/my_db_probe.py`. A single wrong match
        # defeats the ABSENT check entirely, which is the one branch
        # whose whole job is "this module was never imported".
        matches = [
            name
            for name in found
            if name == module or name.endswith("/" + module)
        ]
        if not matches:
            failures.append(
                f"  {module}: ABSENT from the report — it was never imported "
                f"during the run, so it has no coverage at all"
            )
            continue
        if len(matches) > 1:
            failures.append(
                f"  {module}: ambiguous — matches {sorted(matches)}; pass a "
                f"longer path"
            )
            continue

        line_rate, branch_rate = found[matches[0]]
        if branch_rate is None:
            failures.append(
                f"  {matches[0]}: no branch-rate in the report — cannot "
                f"assert branch coverage"
            )
        if line_rate < threshold:
            failures.append(
                f"  {matches[0]}: line coverage {line_rate:.1%} < {args.min:.0f}%"
            )
        if branch_rate is not None and branch_rate < threshold:
            failures.append(
                f"  {matches[0]}: branch coverage {branch_rate:.1%} < {args.min:.0f}%"
            )

    if failures:
        print(
            f"coverage gate FAILED against {args.xml}:", file=sys.stderr
        )
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        f"coverage gate OK — {len(args.modules)} module(s) at "
        f">= {args.min:.0f}% line and branch coverage"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
