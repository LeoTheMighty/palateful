#!/usr/bin/env python3
"""gate4api1 self-test — prove the api eval runner can tell RED from GREEN.

Runs tools/api-pytest-targeted.py exactly as `devx gate evals` does (cwd
services/api, one artifact path appended, the operator's environment minus
DATABASE_URL) against generated fixtures, and asserts each exit code and
that the gate's captured excerpt (last 10 non-blank lines of stdout+stderr,
as gate-evals.ts `lastLines` takes it) carries the reason.

The control is what makes the GREEN case worth anything: the same green
fixture run through the runner this replaced, bare `poetry run pytest
<file>`, must exit 1 on the coverage threshold with both its tests
passing. That proves the fixtures sit under the same addopts and
`fail_under = 100` a real eval does. If they were somewhere the pin did not
reach, both commands would exit 0 and the GREEN assertion would prove
nothing. The control redirects only report *destinations* (pytest-cov keys
`--cov-report` by type, so a later one replaces the addopts path), keeping
`--cov` and the threshold as they are: CI uploads coverage/ and reports/ as
artifacts, and a 0.5% api coverage.xml from this step must not be what a
later reader downloads.

Fixtures live in a dot-directory under services/api/tests/ so the real
conftest applies, while the full suite's recursion skips them (pytest's
default norecursedirs includes '.*'). Removed on exit.

Bare mode is checked too: `/devx` Phase 5 runs each project's `test`
command with no arguments, and there the runner must be the whole suite,
coverage pin included — exactly the `poetry run pytest` it replaced. A
`poetry` shim on PATH records what the runner execs, so this costs no
suite run.

Exit codes: 0 every case held, 1 a case failed, 2 the control no longer
reproduces (the hazard this runner exists for is gone, or the fixtures
escaped it — either way, re-read before trusting a GREEN here).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API_DIR = REPO / "services" / "api"
RUNNER = REPO / "tools" / "api-pytest-targeted.py"
REASON = "rst-red-reason-7f3a"

FIXTURES = {
    # Builds Settings, so it also fails without DATABASE_URL — the second
    # way the old runner turned green into exit 1.
    "test_rst_green.py": (
        "def test_settings_build():\n"
        "    from config import Settings\n"
        "    assert Settings().environment\n"
        "\n"
        "def test_arithmetic():\n"
        "    assert 1 + 1 == 2\n"
    ),
    "test_rst_red.py": (
        "def test_passes():\n"
        "    assert True\n"
        "\n"
        "def test_fails_for_its_own_reason():\n"
        f"    assert 1 + 1 == 3, {REASON!r}\n"
    ),
    "test_rst_errors_only.py": (
        "import pytest\n"
        "\n"
        "@pytest.fixture\n"
        "def broken():\n"
        "    raise RuntimeError('fixture-broke')\n"
        "\n"
        "def test_uses_broken(broken):\n"
        "    assert True\n"
    ),
    "test_rst_all_skipped.py": (
        "import pytest\n"
        "\n"
        "@pytest.mark.skip(reason='never runs')\n"
        "def test_skipped():\n"
        "    assert False\n"
    ),
    "test_rst_empty.py": "# no tests\n",
    "test_rst_collect_error.py": "import rst_module_written_ahead_of  # noqa\n",
    # The original defect's shape, minus coverage: every test passes and a
    # hook — not a test — sets exit status 1. Must not read as RED.
    "exit1/conftest.py": (
        "def pytest_sessionfinish(session, exitstatus):\n"
        "    session.exitstatus = 1\n"
    ),
    "exit1/test_rst_passes_but_exit1.py": "def test_ok():\n    assert True\n",
}

# (fixture, expected runner exit, text the gate's excerpt must contain)
CASES = [
    ("test_rst_green.py", 0, ["GREEN — 2 passed"]),
    ("test_rst_red.py", 1, [REASON, "RED — 1 passed, 1 failed"]),
    ("test_rst_errors_only.py", 1, ["RED (errors only"]),
    ("test_rst_all_skipped.py", 5, ["NO-RESULT — no test passed"]),
    ("test_rst_empty.py", 5, ["NO-RESULT — no tests collected"]),
    ("test_rst_collect_error.py", 2, ["INTERRUPTED"]),
    ("test_rst_missing.py", 4, ["USAGE"]),
    ("exit1/test_rst_passes_but_exit1.py", 3, ["no test failed or errored"]),
]


def excerpt(stdout: str, stderr: str) -> str:
    lines = [ln for ln in f"{stdout}\n{stderr}".split("\n") if ln.strip()]
    return "\n".join(lines[-10:])


def run(cmd: str, env: dict[str, str], cwd: Path = API_DIR) -> tuple[int, str, str]:
    """(exit code, gate excerpt, full output)."""
    r = subprocess.run(
        cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True
    )
    return r.returncode, excerpt(r.stdout, r.stderr), f"{r.stdout}\n{r.stderr}"


def main() -> int:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    tmp = Path(tempfile.mkdtemp(prefix=".runner-selftest-", dir=API_DIR / "tests"))
    rel = tmp.relative_to(API_DIR).as_posix()
    try:
        for name, body in FIXTURES.items():
            (tmp / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp / name).write_text(body)

        # Control: the old runner on the green fixture, with DATABASE_URL set
        # so the coverage pin is the only thing that can fail it.
        out_dir = tmp / "control-out"
        code, out, full = run(
            f"poetry run pytest"
            f" --cov-report xml:{out_dir}/coverage.xml"
            f" --cov-report html:{out_dir}/html"
            f" --junitxml={out_dir}/junit.xml --html={out_dir}/report.html"
            f" {rel}/test_rst_green.py",
            {**env, "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/test",
             "COVERAGE_FILE": str(out_dir / ".coverage")},
        )
        if code != 1 or "fail-under=100" not in full or "2 passed" not in full:
            print(f"CONTROL DID NOT REPRODUCE: bare `poetry run pytest` on the "
                  f"green fixture exited {code}; expected 1 from the coverage "
                  f"pin with 2 passed. Excerpt:\n{out}")
            return 2
        print("ok   control: bare `poetry run pytest` on the green fixture "
              "exits 1 (coverage pin) — the fixtures are under it")

        failures = 0
        for name, want, needles in CASES:
            code, out, _ = run(f"python3 ../../{RUNNER.relative_to(REPO)} {rel}/{name}", env)
            missing = [n for n in needles if n not in out]
            if code == want and not missing:
                print(f"ok   {name}: exit {code}")
                continue
            failures += 1
            print(f"FAIL {name}: exit {code} (want {want}); "
                  f"excerpt missing {missing}\n{out}\n")
        # Bare mode: must exec `poetry run pytest` verbatim from services/api.
        # Invoked from the repo root, so the cwd check proves the chdir.
        shim = tmp / "shim-bin"
        shim.mkdir()
        (shim / "poetry").write_text('#!/bin/sh\necho "SHIM cwd=$(pwd -P) argv=$*"\n')
        (shim / "poetry").chmod(0o755)
        code, out, _ = run(
            f"python3 {RUNNER.relative_to(REPO)}",
            {**env, "PATH": f"{shim}{os.pathsep}{env.get('PATH', '')}"},
            cwd=REPO,
        )
        want_line = f"SHIM cwd={API_DIR} argv=run pytest"
        if code == 0 and want_line in out.splitlines():
            print("ok   bare (no args): execs `poetry run pytest` in services/api")
        else:
            failures += 1
            print(f"FAIL bare (no args): exit {code}, want 0 and the line "
                  f"{want_line!r}\n{out}\n")
        total = len(CASES) + 1
        print(f"{total - failures}/{total} cases held")
        return 1 if failures else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
