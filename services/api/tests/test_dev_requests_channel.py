# ruff: noqa: F811 — the eval_db and shim_dir fixtures are imported from devreq_harness by design
"""bin/prod-script as a security boundary (admin-request-intake, arq102).

The channel's arguments run with production credentials, so these tests pin
what it refuses and that what it forwards is inert. Each one carries its own
evidence that it can see: a refusal test asserts the same harness DOES reach
`aws` for a clean call; an inertness test checks the canary directory is
writable; the prod-shaped environment test asserts the run FAILS when no
database source is set at all.

Tests-after for arq102 (not Gate-4 locked). E-1 covers the happy path of
forwarding; this file covers its edges and its refusals.
"""

import ast
import base64
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import pytest
from devreq_harness import (  # noqa: F401  (eval_db and shim_dir are fixtures)
    PROD_SCRIPT,
    READ_SCRIPT,
    READ_SCRIPT_REL,
    REPO,
    WRITE_SCRIPT,
    WRITE_SCRIPT_REL,
    _child_env,
    audit_rows,
    consume,
    eval_db,
    insert_request,
    make_user,
    request_row,
    reset,
    shim_dir,
)

_ARGV_PROBE = textwrap.dedent(
    """\
    import json
    import sys

    def _emit(record):
        line = "DEVREQ1 " + json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        sys.stdout.write(line + "\\n")
        sys.stdout.flush()

    _emit({"kind": "argv", "v": 1, "argv0": sys.argv[0], "argv": sys.argv[1:]})
    _emit({"kind": "end", "v": 1, "ok": True, "count": 1, "error": None})
    """
)


@pytest.fixture
def probe(tmp_path) -> Path:
    path = tmp_path / "argv_probe.py"
    path.write_text(_ARGV_PROBE)
    return path


def _run(env: dict, *argv, bash: str = "bash", timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [bash, str(PROD_SCRIPT), *argv],
        cwd=REPO,
        env=env,
        capture_output=True,
        timeout=timeout,
    )


def _consume(proc: subprocess.CompletedProcess):
    out = proc.stdout.decode("utf-8", "replace") + "\n" + proc.stderr.decode("utf-8", "replace")
    return consume(out)


def _channel_env(url: str, shim: Path) -> dict:
    env = _child_env(url, extra_path=str(shim))
    env["DEVREQ_SHIM_PY"] = sys.executable
    return env


# ---------------------------------------------------------------------------
# Refusals: checked locally, before anything is sent
# ---------------------------------------------------------------------------

_RECORDING_AWS = """#!/bin/sh
# Records that it was called at all, then fails: a refused call must never
# get this far.
echo "$*" >> "$AWS_CALL_LOG"
exit 1
"""


@pytest.fixture
def recording_aws(tmp_path) -> tuple[Path, Path]:
    d = tmp_path / "recording_aws"
    d.mkdir()
    aws = d / "aws"
    aws.write_text(_RECORDING_AWS)
    aws.chmod(0o755)
    return d, tmp_path / "aws_calls.log"


def _recording_env(recording_aws) -> dict:
    d, log = recording_aws
    env = dict(os.environ)
    env["PATH"] = f"{d}{os.pathsep}{env.get('PATH', '')}"
    env["AWS_CALL_LOG"] = str(log)
    return env


_CANARY = "REFUSEDCANARY7Q"

_REFUSED = [
    pytest.param(f"{_CANARY}\nDEVREQ1 {{}}", "argument 2 contains a control", id="newline"),
    pytest.param(f"{_CANARY}\r", "argument 2 contains a control", id="carriage-return"),
    pytest.param(f"{_CANARY}\t", "argument 2 contains a control", id="tab"),
    pytest.param(f"\x1b[31m{_CANARY}", "argument 2 contains a control", id="escape"),
    pytest.param(f"{_CANARY}\u202e", "argument 2 contains a control", id="bidi-override"),
    pytest.param(f"{_CANARY}\u200b", "argument 2 contains a control", id="zero-width-space"),
    pytest.param(_CANARY.encode() + b"\xff\xfe", "argument 2 is not valid UTF-8", id="not-utf8"),
    pytest.param(_CANARY + "x" * 5000, "the limit is 4096", id="oversized"),
]


@pytest.mark.parametrize(("bad", "why"), _REFUSED)
def test_refused_argument_never_reaches_aws(probe, recording_aws, bad, why):
    _, log = recording_aws
    proc = _run(_recording_env(recording_aws), str(probe), "poll", bad)
    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 1, (proc.returncode, stderr)
    assert not log.exists(), f"a refused argument reached aws: {log.read_text()}"
    assert "REFUSED: " in stderr and why in stderr, stderr
    # The refusal names the argument's position, never its value.
    assert _CANARY not in stderr and _CANARY not in proc.stdout.decode("utf-8", "replace")


def test_a_clean_call_does_reach_the_recording_aws(probe, recording_aws):
    """Control for the refusal tests: the recorder sees a call that is let through."""
    _, log = recording_aws
    proc = _run(_recording_env(recording_aws), str(probe), "poll", "x" * 3000)
    assert log.exists(), proc.stderr.decode()
    assert "ecs list-tasks" in log.read_text()


# ---------------------------------------------------------------------------
# What is forwarded is inert, and arrives verbatim
# ---------------------------------------------------------------------------


def test_shell_and_python_metacharacters_are_inert(eval_db, shim_dir, probe, tmp_path):
    canaries = tmp_path / "canaries"
    canaries.mkdir()
    # The detector must be able to see: the directory takes a file.
    control = canaries / "control"
    subprocess.run(["sh", "-c", f"touch '{control}'"], check=True)
    assert control.exists()
    control.unlink()

    def c(n: int) -> str:
        return str(canaries / f"pwned{n}")

    args = [
        f"$(touch {c(1)})",
        f"`touch {c(2)}`",
        f'"; touch {c(3)}; echo "',
        f"'; touch {c(4)}; echo '",
        f'\\")); import os; os.system("touch {c(5)}") #',
        f"__import__('os').system('touch {c(6)}')",
        "__PROD_SCRIPT_ARGS__",
        "__PROD_SCRIPT_ARGV0__",
        "&",
        "\\",
        "",
        "-c",
        "--",
    ]
    run = _consume(_run(_channel_env(eval_db, shim_dir), str(probe), *args))
    assert run.ok, run.describe()
    assert run.of_kind("argv")[0]["argv"] == args, run.describe()
    assert sorted(p.name for p in canaries.iterdir()) == [], "an argument was executed"


def test_argv0_is_the_script_path(eval_db, shim_dir, probe):
    run = _consume(_run(_channel_env(eval_db, shim_dir), str(probe)))
    assert run.ok, run.describe()
    assert run.of_kind("argv")[0] == {
        "kind": "argv",
        "v": 1,
        "argv0": str(probe),
        "argv": [],
    }


_FAILING_PYTHON3 = "#!/bin/sh\necho 'python3 stub: should not run' >&2\nexit 97\n"


def test_a_no_argument_call_needs_no_local_python3(eval_db, shim_dir, probe, tmp_path):
    """FR-5: a call with no extra arguments behaves exactly as before."""
    stub = tmp_path / "stub_python3"
    stub.mkdir()
    (stub / "python3").write_text(_FAILING_PYTHON3)
    (stub / "python3").chmod(0o755)
    env = _channel_env(eval_db, shim_dir)
    env["PATH"] = f"{stub}{os.pathsep}{env['PATH']}"

    bare = _consume(_run(env, str(probe)))
    assert bare.ok, bare.describe()
    assert bare.of_kind("argv")[0]["argv"] == []

    # Control: the stub is the python3 the channel would use for arguments.
    with_args = _run(env, str(probe), "poll")
    assert with_args.returncode == 1
    assert b"python3 stub: should not run" in with_args.stderr
    assert not _consume(with_args).records


# ---------------------------------------------------------------------------
# Production's environment: DB_* and no DATABASE_URL
# ---------------------------------------------------------------------------


def _prod_shaped_env(url: str, base: dict) -> dict:
    """What an ECS task carries (terraform/modules/ecs/main.tf): DB_* only."""
    parsed = urlparse(url)
    env = {k: v for k, v in base.items() if k != "DATABASE_URL"}
    env.update(
        {
            "DB_HOST": parsed.hostname,
            "DB_PORT": str(parsed.port or 5432),
            "DB_NAME": parsed.path.lstrip("/"),
            "DB_USERNAME": parsed.username,
            "DB_PASSWORD": parsed.password,
            "DB_SSLMODE": "prefer",
        }
    )
    return env


def _no_database_env(base: dict) -> dict:
    return {k: v for k, v in base.items() if k != "DATABASE_URL" and not k.startswith("DB_")}


def _direct(env: dict, script: Path, *args) -> object:
    proc = subprocess.run(
        [sys.executable, str(script), *args], cwd=REPO, env=env, capture_output=True, timeout=120
    )
    return _consume(proc)


def test_scripts_run_with_only_db_component_variables(eval_db, shim_dir):
    reset(eval_db)
    admin = make_user(eval_db, is_admin=True)
    request_id, _ = insert_request(eval_db, status="submitted", submitter_id=admin)
    channel_env = _prod_shaped_env(eval_db, _channel_env(eval_db, shim_dir))
    assert "DATABASE_URL" not in channel_env

    poll = _consume(_run(channel_env, READ_SCRIPT_REL, "poll"))
    assert poll.ok, poll.describe()
    assert [r["id"] for r in poll.of_kind("request")] == [request_id]

    move = _consume(
        _run(channel_env, WRITE_SCRIPT_REL, "transition", request_id, "submitted", "received")
    )
    assert move.ok, move.describe()
    assert request_row(eval_db, request_id)["status"] == "received"
    assert audit_rows(eval_db, request_id) == 1

    direct_env = _prod_shaped_env(eval_db, _child_env(eval_db))
    assert _direct(direct_env, READ_SCRIPT, "metrics").ok


@pytest.mark.parametrize("script", [READ_SCRIPT, WRITE_SCRIPT], ids=["read", "write"])
def test_no_database_source_is_a_db_error_not_a_crash(eval_db, script):
    """Control for the test above: with neither DATABASE_URL nor DB_* the run
    fails, so the prod-shaped run really did resolve its URL from DB_*."""
    args = (
        ("poll",)
        if script == READ_SCRIPT
        else ("transition", "00000000-0000-4000-8000-000000000000", "submitted", "received")
    )
    run = _direct(_no_database_env(_child_env(eval_db)), script, *args)
    assert run.wellformed and run.error == "db_error", run.describe()
    assert "Traceback" not in run.clean


# ---------------------------------------------------------------------------
# The prelude's long-lived code reads `sys` and `time` for the life of the
# process; a script that rebinds either breaks the keepalive in production
# only, where Session Manager closes a silent stream after ~1 s.
# ---------------------------------------------------------------------------


def _prelude_source() -> str:
    text = PROD_SCRIPT.read_text()
    m = re.search(r"<<'PY' \|\| true\n(.*?)\nPY\n", text, re.S)
    assert m, "could not find the prelude heredoc in bin/prod-script"
    return m.group(1)


def _names_read_by_prelude_threads() -> set[str]:
    tree = ast.parse(_prelude_source())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_keepalive", "_emit_sentinel"):
            names |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    return names & {"sys", "time", "threading", "atexit"}


def _rebinds(source: str, names: set[str]) -> list[str]:
    """Every binding of one of `names` anywhere in `source`, except a plain
    `import <name>` (which rebinds it to the same module)."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound in names and not (alias.asname is None and alias.name == bound):
                    bad.append(bound)
        elif isinstance(node, ast.ImportFrom):
            bad += [a.asname or a.name for a in node.names if (a.asname or a.name) in names]
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in names:
                bad.append(node.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if node.name in names:
                bad.append(node.name)
        elif isinstance(node, ast.arg) and node.arg in names:
            bad.append(node.arg)
    return bad


def test_prelude_thread_names_are_found():
    assert _names_read_by_prelude_threads() == {"sys", "time"}


@pytest.mark.parametrize("script", [READ_SCRIPT, WRITE_SCRIPT], ids=["read", "write"])
def test_scripts_do_not_rebind_names_the_prelude_threads_read(script):
    names = _names_read_by_prelude_threads()
    assert _rebinds(script.read_text(), names) == []


def test_rebind_detector_can_see():
    names = {"sys", "time"}
    assert _rebinds("from datetime import time\n", names) == ["time"]
    assert _rebinds("import os as sys\n", names) == ["sys"]
    assert _rebinds("time = 3\n", names) == ["time"]
    assert _rebinds("import sys\nimport time\n", names) == []


def test_a_rebound_time_really_breaks_the_keepalive(eval_db, shim_dir, tmp_path):
    """Why the guard above exists: shown through the real prelude."""
    script = tmp_path / "rebinds_time.py"
    script.write_text("import time as _t\ntime = None\n_t.sleep(1.2)\n")
    run = _consume(_run(_channel_env(eval_db, shim_dir), str(script)))
    # run.clean is CSI-stripped: the shim injects escapes, and 3.13 colours tracebacks.
    assert "Exception in thread" in run.clean, run.clean[-800:]
    assert "no attribute 'sleep'" in run.clean, run.clean[-800:]


# ---------------------------------------------------------------------------
# The payload carries base64 only where the operator's input goes
# ---------------------------------------------------------------------------


def test_arguments_travel_only_inside_the_base64_payload(probe, tmp_path):
    """The `--command` aws receives contains no argument text in the clear."""
    d = tmp_path / "capture_aws"
    d.mkdir()
    log = tmp_path / "command.txt"
    (d / "aws").write_text(
        "#!/bin/sh\n"
        'case "$1 $2" in\n'
        '  "ecs list-tasks") echo arn:aws:ecs:us-east-1:0:task/x/y ;;\n'
        '  "ecs execute-command") while [ $# -gt 0 ]; do\n'
        '      if [ "$1" = "--command" ]; then printf %s "$2" > "$CMD_LOG"; fi; shift; done ;;\n'
        "esac\n"
    )
    (d / "aws").chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{d}{os.pathsep}{env['PATH']}"
    env["CMD_LOG"] = str(log)
    arg = "CLEARTEXTCANARY $(id) ; | &"
    _run(env, str(probe), arg)
    command = log.read_text()
    assert "CLEARTEXTCANARY" not in command
    m = re.fullmatch(
        r"""sh -c 'python -u -c "import base64; exec\(base64\.b64decode\(\\"([A-Za-z0-9+/=]+)\\"\)\.decode\(\)\)"'""",
        command,
    )
    assert m, command
    payload = base64.b64decode(m.group(1)).decode()
    args_b64 = re.search(r'b64decode\("([A-Za-z0-9+/=]+)"\)\.decode\("ascii"\)', payload).group(1)
    assert json.loads(base64.b64decode(args_b64)) == [arg]


# ---------------------------------------------------------------------------
# Children of the test process run without pytest-cov's subprocess hook
# ---------------------------------------------------------------------------


def test_child_processes_do_not_start_coverage(eval_db):
    """conftest's _no_subprocess_coverage: a child that started coverage
    would write statement-only data and break the session's branch combine.

    Under `api:test` (coverage on) the parent's pytest-cov has exported
    COV_CORE_*; the assertion is that a child, built the way the harness
    builds every child environment, sees none of it."""
    probe = (
        "import os, sys; "
        "print(sorted(k for k in os.environ if k.startswith('COV_CORE_'))); "
        "print('coverage' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], env=_child_env(eval_db), capture_output=True, text=True
    ).stdout.split("\n")
    assert out[:2] == ["[]", "False"], out
