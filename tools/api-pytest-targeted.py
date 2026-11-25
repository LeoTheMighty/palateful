#!/usr/bin/env python3
"""gate4api1 — run *some* api tests and return an exit code that means something.

This is the `api` runner in devx.config.yaml `projects:`, so it is what
`devx gate evals` (Gate 4, the RED gate) runs for every Verified-by target
under services/api. The gate appends one artifact path and reads the exit
code: nonzero is RED, zero is not.

Why not `poetry run pytest <file>`, which is what the runner used to be:

1. Coverage. services/api's addopts carry `--cov`, and `fail_under = 100`
   is a whole-suite threshold. A subset of the suite cannot meet it, so a
   targeted run exits 1 with every test green ("Coverage failure: total of
   0 is less than fail-under=100"). RED and GREEN read the same.
2. Environment. tests/conftest.py defaults DATABASE_URL to "", and Settings
   rejects an empty one, so from a shell without the variable every test
   that builds Settings fails with a ValidationError. The CI job that
   defines the suite sets DATABASE_URL; a gate run inherited whatever the
   operator's shell had.

How the two are separated, rather than the bar lowered: the 100% pin is
untouched and still enforced where it means something, on the whole suite
(`npx nx run api:test`, CI's `test` job). A targeted run is not asked to
satisfy it (`--no-cov`). Called with no arguments this runner *is* the
whole suite and execs `poetry run pytest` verbatim, threshold included.

Exit codes — pytest's own vocabulary, with one correction:
  0  GREEN       at least one test ran and passed; none failed or errored.
  1  RED         at least one test failed or errored (pytest's code).
  2  INTERRUPTED usually a collection error, e.g. an import of a module the
                 eval is written ahead of. Read the quote.
  3  INTERNAL    pytest internal error; or this runner could not read the
                 junit report and so will not claim GREEN; or pytest exited
                 1 with no test failed or errored — the original defect's
                 shape (a plugin or hook, not a test, set the status), so
                 it is not reported as RED.
  4  USAGE       bad path or option.
  5  NO-RESULT   nothing collected, or — the correction — pytest said 0 but
                 no test passed (every selected test skipped). Pytest
                 exits 0 there; a runner that did would call an eval that
                 never ran GREEN.

The last line is always one `api-pytest-targeted:` verdict line on stderr,
so it is the last line of the gate's captured excerpt.

Proof that it can tell the two apart: tools/api-pytest-targeted-self-test.py
(run in CI's `test` job), including a control proving its fixtures sit under
the same coverage pin a real eval does.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PREFIX = "api-pytest-targeted:"
API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"
# The value CI's `test` job sets (.github/workflows/ci.yml). Tests that
# build Settings need it non-empty; tests that connect need Postgres there.
CI_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test"


def note(msg: str) -> None:
    print(f"{PREFIX} {msg}", file=sys.stderr, flush=True)


def to_api_relative(arg: str, cwd: Path) -> str:
    """Make a path argument valid from API_DIR, wherever the caller stood.

    devx calls from services/api with `tests/x.py`; a human at the repo root
    types `services/api/tests/x.py`. Node ids keep their `::` suffix. Options
    and anything that is not an existing path pass through untouched.
    """
    if arg.startswith("-"):
        return arg
    head, sep, tail = arg.partition("::")
    candidate = (cwd / head).resolve()
    if not candidate.exists():
        return arg
    return f"{candidate}{sep}{tail}"


def junit_counts(path: Path) -> dict[str, int] | None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    counts = {"tests": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in root.iter("testcase"):
        counts["tests"] += 1
        if case.find("failure") is not None:
            counts["failed"] += 1
        elif case.find("error") is not None:
            counts["errors"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
    counts["passed"] = (
        counts["tests"] - counts["failed"] - counts["errors"] - counts["skipped"]
    )
    return counts


def verdict(rc: int, c: dict[str, int] | None) -> tuple[int, str]:
    """Map (pytest exit, junit counts) to (runner exit, verdict text)."""
    if c is None:
        if rc == 0:
            return 3, (
                "INTERNAL — pytest exited 0 but its junit report is unreadable, "
                "so nothing proves a test passed; refusing to report GREEN"
            )
        tally = "counts unavailable"
    else:
        tally = (
            f"{c['passed']} passed, {c['failed']} failed, "
            f"{c['errors']} errors, {c['skipped']} skipped"
        )
    if rc == 0:
        if c["passed"] >= 1:
            return 0, f"GREEN — {tally} (pytest exit 0)"
        return 5, (
            f"NO-RESULT — no test passed ({tally}); pytest exits 0 here, "
            "this runner does not (pytest exit 0 → 5)"
        )
    if rc == 1:
        if c is not None and c["failed"] == 0 and c["errors"] == 0:
            return 3, (
                f"INTERNAL — pytest exited 1 but no test failed or errored "
                f"({tally}): something other than a test set the exit status "
                f"(a threshold plugin or hook); not RED (pytest exit 1 → 3)"
            )
        if c is not None and c["failed"] == 0 and c["errors"] > 0:
            return 1, (
                f"RED (errors only: no assertion failed; a fixture, setup or "
                f"teardown raised — read the quote) — {tally} (pytest exit 1)"
            )
        return 1, f"RED — {tally} (pytest exit 1)"
    meaning = {
        2: "INTERRUPTED — usually a collection error (an import the eval is "
        "written ahead of, or a broken test file); read the quote",
        3: "INTERNAL — pytest internal error",
        4: "USAGE — bad path or option",
        5: "NO-RESULT — no tests collected",
    }.get(rc, "NO-RESULT — pytest did not run to a verdict")
    return rc, f"{meaning} — {tally} (pytest exit {rc})"


def main(argv: list[str]) -> int:
    if not argv:
        note(
            "no test path given — running the whole api suite exactly as "
            "`npx nx run api:test` does (coverage pin applies)"
        )
        os.chdir(API_DIR)
        os.execvp("poetry", ["poetry", "run", "pytest"])

    env = dict(os.environ)
    if not env.get("DATABASE_URL"):
        env["DATABASE_URL"] = CI_DATABASE_URL
        note(f"DATABASE_URL unset — using CI's value ({CI_DATABASE_URL})")

    cwd = Path.cwd()
    args = [to_api_relative(a, cwd) for a in argv]
    with tempfile.TemporaryDirectory(prefix="api-pytest-targeted-") as tmp:
        junit = Path(tmp) / "junit.xml"
        # --no-cov: the coverage pin is a whole-suite property (see module
        # docstring). The report paths are overridden, not dropped, so a
        # targeted run does not overwrite the full suite's reports/ output,
        # and every other addopt still applies.
        cmd = [
            "poetry", "run", "pytest",
            "--no-cov",
            "-p", "no:cacheprovider",
            f"--junitxml={junit}",
            f"--html={Path(tmp) / 'report.html'}",
            *args,
        ]
        sys.stdout.flush()
        try:
            rc = subprocess.run(cmd, cwd=API_DIR, env=env).returncode
        except FileNotFoundError:
            note("NO-RESULT — `poetry` not found on PATH (exit 127)")
            return 127
        code, text = verdict(rc, junit_counts(junit))
    note(text)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
