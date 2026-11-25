"""Contract-eval harness for workstream admin-request-intake (plan 1e84ad).

Not a test module: no ``test_`` prefix, so pytest never collects it. The RED
evals for E-1 … E-5 import it. It is pinned by sha256 in
``_devx/workstreams/admin-request-intake/evals/lib/run_pytest_eval.sh``, so an
edit here makes every wrapper refuse with EVAL-TAMPERED. If the harness is
genuinely wrong, the fix is ``devx revise``, not an edit.

Everything here is written against the PRD contract
(``_devx/workstreams/admin-request-intake/prd/agent.md`` FR-1 … FR-13), never
against an implementation:

* ``eval_db`` — a throwaway Postgres database built from the models.
* ``channel()`` — runs the real ``bin/prod-script`` with ``aws`` replaced by a
  shim that reproduces the ECS-exec stream: banner lines, stderr merged into
  stdout, CRLF line ends, and a CSI escape injected into the middle of every
  long line.
* ``consume()`` — the FR-6 consumer rule, applied exactly as the bridge must.
* ``api_client()`` — the FastAPI app bound to the throwaway database, with the
  caller's identity fixed to a real ``users`` row.

Missing features are reported by the ``require_*`` helpers with
``pytest.fail("RED: …")`` from inside test bodies, never from fixtures. An
unbuilt feature is a test *failure*; a broken harness or an unreachable
database is an *error*. The wrapper treats the two differently.
"""

import ast
import hashlib
import importlib
import json
import os
import pkgutil
import re
import stat
import subprocess
import sys
import unicodedata
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO = Path(__file__).resolve().parents[3]
API_ROOT = REPO / "services" / "api"
READ_SCRIPT_REL = "services/api/scripts/dev_requests_read.py"
WRITE_SCRIPT_REL = "services/api/scripts/dev_requests_write.py"
READ_SCRIPT = REPO / READ_SCRIPT_REL
WRITE_SCRIPT = REPO / WRITE_SCRIPT_REL
PROD_SCRIPT = REPO / "bin" / "prod-script"

ADMIN_URL = os.environ.get(
    "DEVREQ_EVAL_ADMIN_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)

# PRD FR-12.
STATUSES = (
    "submitted",
    "received",
    "accepted",
    "declined",
    "withdrawn",
    "scoping",
    "designing",
    "planning",
    "building",
    "waiting_on_leo",
    "shipped",
    "stopped",
    "reverted",
)
TERMINAL = ("declined", "withdrawn", "shipped", "stopped", "reverted")

# PRD FR-6.
CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
RECORD_RE = re.compile(r"^DEVREQ1 (\{.*\})$")

# Prod tasks carry these instead of DATABASE_URL; utils.constants prefers
# them. They must never leak into an eval run from the developer's shell.
_DB_COMPONENT_VARS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USERNAME", "DB_PASSWORD", "DB_SSLMODE")


# ---------------------------------------------------------------------------
# Reference implementations of the contract (PRD FR-2)
# ---------------------------------------------------------------------------


def ref_normalize(value: str) -> str:
    """NFKC, then drop every Cc/Cf character except \\n and \\t, then strip."""
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        ch for ch in value if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf")
    )
    return value.strip()


def ref_hash(title: str, body: str, done_when: str | None) -> str:
    payload = json.dumps(
        {"title": title, "body": body, "done_when": done_when},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def id8(request_id: str) -> str:
    return str(request_id).replace("-", "")[:8]


# ---------------------------------------------------------------------------
# The FR-6 consumer
# ---------------------------------------------------------------------------


@dataclass
class Consumed:
    raw: str
    clean: str
    records: list[dict] = field(default_factory=list)
    end: dict | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def wellformed(self) -> bool:
        """Exactly one end record, last, with a matching count, all v=1."""
        return not self.problems

    @property
    def ok(self) -> bool:
        return self.wellformed and self.end is not None and self.end.get("ok") is True

    @property
    def error(self) -> str | None:
        return None if self.end is None else self.end.get("error")

    def of_kind(self, kind: str) -> list[dict]:
        return [r for r in self.records if r.get("kind") == kind]

    def describe(self) -> str:
        tail = self.clean[-1500:]
        return f"problems={self.problems} end={self.end} output tail:\n{tail}"


def consume(raw: str) -> Consumed:
    clean_lines = [CSI_RE.sub("", line).rstrip("\r") for line in raw.split("\n")]
    out = Consumed(raw=raw, clean="\n".join(clean_lines))
    ends: list[dict] = []
    for line in clean_lines:
        m = RECORD_RE.match(line)
        if not m:
            continue
        try:
            rec = json.loads(m.group(1))
        except ValueError:
            out.problems.append("unparseable DEVREQ1 line")
            continue
        if not isinstance(rec, dict) or rec.get("v") != 1:
            out.problems.append(f"record with unknown version: {rec!r}"[:200])
            continue
        if ends:
            out.problems.append("record after the end record")
        if rec.get("kind") == "end":
            ends.append(rec)
        else:
            out.records.append(rec)
    if not ends:
        out.problems.append("no end record")
    elif len(ends) > 1:
        out.problems.append("more than one end record")
    else:
        out.end = ends[0]
        if out.end.get("count") != len(out.records):
            out.problems.append(f"end count {out.end.get('count')!r} != {len(out.records)} records")
    return out


def contains_any(haystack: str, needles: list[str]) -> list[str]:
    """Which needles occur in haystack. Used on CSI-stripped output."""
    return [n for n in needles if n in haystack]


# ---------------------------------------------------------------------------
# Throwaway database
# ---------------------------------------------------------------------------


def _import_all_models() -> None:
    import utils.models as pkg

    for mod in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        importlib.import_module(mod.name)


@pytest.fixture(scope="session")
def eval_db() -> Iterator[str]:
    """A fresh database with every model's table. Yields its sync URL."""
    name = f"devreq_eval_{uuid.uuid4().hex[:10]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + "/" + name
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        _import_all_models()
        from utils.models.base import Base

        Base.metadata.create_all(engine)
        yield url
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@contextmanager
def connect(url: str) -> Iterator:
    engine: Engine = create_engine(url)
    try:
        with engine.begin() as conn:
            yield conn
    finally:
        engine.dispose()


def table_exists(url: str, table: str) -> bool:
    with connect(url) as conn:
        return (
            conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar()
            is not None
        )


def reset(url: str) -> None:
    """Empty the tables the evals write. Missing tables are skipped silently
    here on purpose: their absence is reported by require_table() in the test
    body, as a RED failure, not by this helper as an error."""
    with connect(url) as conn:
        for table in ("dev_requests", "error_logs"):
            if conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar():
                conn.execute(text(f"DELETE FROM {table}"))


def make_user(url: str, *, is_admin: bool) -> str:
    from sqlalchemy.orm import Session
    from utils.models.user import User

    engine = create_engine(url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tag = uuid.uuid4().hex[:12]
            user = User(
                auth0_id=f"auth0|devreq-eval-{tag}",
                email=f"devreq-eval-{tag}@example.test",
                name=f"Eval {'Admin' if is_admin else 'User'} {tag}",
                is_admin=is_admin,
            )
            session.add(user)
            session.commit()
            return str(user.id)
    finally:
        engine.dispose()


def set_admin(url: str, user_id: str, is_admin: bool) -> None:
    with connect(url) as conn:
        conn.execute(
            text("UPDATE users SET is_admin = :a WHERE id = :id"), {"a": is_admin, "id": user_id}
        )


def insert_request(
    url: str,
    *,
    status: str,
    submitter_id: str | None,
    title: str = "Eval title",
    body: str = "Eval body",
    done_when: str | None = None,
) -> tuple[str, str]:
    """Insert one row with PRD FR-1's column names. Returns (id, hash)."""
    request_id = str(uuid.uuid4())
    sha = ref_hash(title, body, done_when)
    with connect(url) as conn:
        conn.execute(
            text(
                "INSERT INTO dev_requests (id, submitter_id, title, body, done_when, "
                "content_sha256, status, target, source, pr_urls) VALUES "
                "(:id, :sub, :title, :body, :dw, :sha, :status, 'palateful', 'admin', "
                "CAST('[]' AS jsonb))"
            ),
            {
                "id": request_id,
                "sub": submitter_id,
                "title": title,
                "body": body,
                "dw": done_when,
                "sha": sha,
                "status": status,
            },
        )
    return request_id, sha


def request_row(url: str, request_id: str) -> dict | None:
    with connect(url) as conn:
        row = (
            conn.execute(text("SELECT * FROM dev_requests WHERE id = :id"), {"id": request_id})
            .mappings()
            .first()
        )
        return None if row is None else dict(row)


def count_rows(url: str, table: str) -> int:
    with connect(url) as conn:
        return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar())


def audit_rows(url: str, request_id: str) -> int:
    with connect(url) as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM error_logs WHERE service = 'audit' "
                    "AND error_type = 'DevRequestTransition' AND error_message LIKE :p"
                ),
                {"p": f"%{id8(request_id)}%"},
            ).scalar()
        )


def fingerprint(url: str) -> tuple:
    """A cheap 'did anything write?' check across the two tables."""
    with connect(url) as conn:
        dr = conn.execute(
            text("SELECT count(*), coalesce(max(updated_at)::text, '') FROM dev_requests")
        ).one()
        el = conn.execute(text("SELECT count(*) FROM error_logs")).scalar()
        return (tuple(dr), el)


# ---------------------------------------------------------------------------
# require_* — RED reporters, called from test bodies
# ---------------------------------------------------------------------------


def require_table(url: str) -> None:
    if not table_exists(url, "dev_requests"):
        pytest.fail(
            "RED: no `dev_requests` table in the model metadata — Phase 1 (PRD FR-1) is not built",
            pytrace=False,
        )


def require_script(path: Path, phase: str, fr: str) -> None:
    if not path.is_file():
        pytest.fail(
            f"RED: {path.relative_to(REPO)} does not exist — {phase} ({fr}) is not built",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# Running the scripts
# ---------------------------------------------------------------------------


def _child_env(url: str, extra_path: str | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _DB_COMPONENT_VARS}
    env["DATABASE_URL"] = url
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_path:
        env["PATH"] = extra_path + os.pathsep + env.get("PATH", "")
    return env


def run_direct(url: str, script: Path, *args: str, timeout: int = 120) -> Consumed:
    """Run a script standalone (python <script> args), as a developer would."""
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        env=_child_env(url),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return consume(proc.stdout + "\n" + proc.stderr)


_AWS_SHIM = r"""#!/usr/bin/env bash
# devreq eval shim for `aws` (admin-request-intake, 1e84ad). Reproduces the
# ECS-exec stream locally: banner lines, stderr merged into stdout as a TTY
# does, CRLF line ends, a CSI escape injected mid-line, and exit code 0
# whatever the script did (ECS exec does not carry it).
set -u
case "${1:-} ${2:-}" in
  "ecs list-tasks")
    echo "arn:aws:ecs:us-east-1:000000000000:task/palateful-prod/devreq-eval-shim"
    exit 0 ;;
  "ecs execute-command")
    cmd=""
    while [ $# -gt 0 ]; do
      if [ "$1" = "--command" ]; then cmd="$2"; shift 2; else shift; fi
    done
    printf '\r\nStarting session with SessionId: devreq-eval-shim-0001\r\n'
    sh -c "$cmd" 2>&1 | "$DEVREQ_SHIM_PY" -u -c '
import sys
for line in sys.stdin.buffer:
    body = line.rstrip(b"\n")
    if len(body) > 24 and not body.startswith(b"__PROD_SCRIPT_END_"):
        body = body[:12] + b"\x1b[0C" + body[12:]
    sys.stdout.buffer.write(body + b"\r\n")
    sys.stdout.buffer.flush()
'
    printf '\r\n\r\nExiting session with sessionId: devreq-eval-shim-0001.\r\n\r\n'
    exit 0 ;;
esac
echo "devreq eval shim: unexpected aws call: $*" >&2
exit 64
"""


@pytest.fixture(scope="session")
def shim_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("devreq_aws_shim")
    aws = d / "aws"
    aws.write_text(_AWS_SHIM)
    aws.chmod(aws.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    # bin/prod-script runs `python -u -c …`; pin `python` to this interpreter.
    # An exec wrapper, not a symlink: a symlinked venv interpreter outside its
    # venv directory finds no pyvenv.cfg and loses the venv's site-packages.
    py = d / "python"
    py.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return d


def channel(url: str, shim: Path, script: str | Path, *args: str, timeout: int = 180) -> Consumed:
    """Run `bin/prod-script <script> <args…>` end to end through the shim."""
    env = _child_env(url, extra_path=str(shim))
    env["DEVREQ_SHIM_PY"] = sys.executable
    proc = subprocess.run(
        ["bash", str(PROD_SCRIPT), str(script), *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return consume(proc.stdout + "\n" + proc.stderr)


# ---------------------------------------------------------------------------
# The API, bound to the throwaway database
# ---------------------------------------------------------------------------


@contextmanager
def api_client(url: str, user_id: str) -> Iterator:
    from dependencies import (
        get_async_database,
        get_current_user,
        get_current_user_async,
    )
    from fastapi.testclient import TestClient
    from main import app
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool
    from utils.models.user import User
    from utils.services.async_database import AsyncDatabase

    async_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def _database():
        engine = create_async_engine(async_url, poolclass=NullPool)
        database = AsyncDatabase(engine=engine)
        try:
            yield database
        finally:
            await database.close()
            await engine.dispose()

    async def _user():
        engine = create_async_engine(async_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await session.get(User, uuid.UUID(user_id))
        finally:
            await engine.dispose()

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_async_database] = _database
    app.dependency_overrides[get_current_user_async] = _user
    app.dependency_overrides[get_current_user] = _user
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


CREATE_PATH = "/v1/admin/dev-requests"


def create_request(client, payload: dict):
    return client.post(CREATE_PATH, json=payload)


def require_create_route(response) -> None:
    if response.status_code in (404, 405):
        pytest.fail(
            f"RED: POST {CREATE_PATH} is not routed (got {response.status_code}) — "
            "Phase 1 (PRD FR-3) is not built",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# Static checks on the scripts
# ---------------------------------------------------------------------------


def disallowed_imports(path: Path) -> list[str]:
    """Imports outside the PRD FR-7 allowlist: stdlib, sqlalchemy, utils.constants."""
    tree = ast.parse(path.read_text(), filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _allowed_module(alias.name):
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                bad.append(f"relative import (level {node.level}) of {node.module}")
                continue
            mod = node.module or ""
            if mod == "__future__":
                bad.append("from __future__ (breaks under the bin/prod-script prelude)")
            elif mod == "utils":
                bad.extend(
                    f"from utils import {a.name}" for a in node.names if a.name != "constants"
                )
            elif not _allowed_module(mod):
                bad.append(f"from {mod} import …")
    return bad


def _allowed_module(name: str) -> bool:
    top = name.split(".")[0]
    if name == "utils.constants" or name.startswith("utils.constants."):
        return True
    if top == "sqlalchemy":
        return True
    return top in sys.stdlib_module_names and top != "__future__"
