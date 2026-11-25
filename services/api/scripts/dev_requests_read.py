"""Read side of the operator channel for dev requests (admin-request-intake).

Usage (through the channel, as the bridge runs it):
    bin/prod-script services/api/scripts/dev_requests_read.py poll
    bin/prod-script services/api/scripts/dev_requests_read.py adopt <id> <sha256>
    bin/prod-script services/api/scripts/dev_requests_read.py metrics
    bin/prod-script services/api/scripts/dev_requests_read.py show <id>   # a human, never an agent

or standalone, against whatever database ``utils.constants`` resolves:
    python services/api/scripts/dev_requests_read.py poll

Read-only by construction: every query runs inside ``SET TRANSACTION READ
ONLY``, so Postgres itself refuses a write, and no audit row is written. The
script contains no write SQL; ``dev_requests_write.py`` is the only writer.

Output is the DEVREQ1 record protocol (PRD FR-6): each machine-readable line
is ``DEVREQ1 `` plus one ASCII-only JSON object, written in one call and
flushed, and every run ends with exactly one ``end`` record whose ``count`` is
the number of records before it. Errors are enum codes, never exception
text, because an exception message can carry row data.

Containment (PRD FR-7): ``poll`` and ``metrics`` never select a text column,
and no refusal prints one. Only ``adopt`` (machine) and ``show`` (human)
return submitter-written text, and only once their checks pass.

Constraints this file is written to:
- Imports only the standard library, SQLAlchemy and ``utils.constants``.
  The bridge runs ``origin/main``'s copy against whatever image is deployed,
  which may be older than this file (PRD FR-7).
- The URL comes from ``utils.constants.DATABASE_URL``, never from
  ``os.environ["DATABASE_URL"]``: prod tasks have only ``DB_*`` variables,
  which ``utils.constants`` composes.
- No ``from __future__``, and no rebinding of ``sys`` or ``time``: under
  ``bin/prod-script`` this file runs after a prelude whose keepalive thread
  and exit sentinel use those names for the life of the process.
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

PROTOCOL = "DEVREQ1"
VERSION = 1

# PRD FR-12, in pipeline order.
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
UNDECIDED = ("submitted", "received")
# Statuses a row can only be in after it was accepted.
ACCEPTED_OR_LATER = (
    "accepted",
    "scoping",
    "designing",
    "planning",
    "building",
    "waiting_on_leo",
    "shipped",
    "stopped",
    "reverted",
)
STALE_UNDECIDED_DAYS = 7

# Bounds on what one run may cost production.
CONNECT_TIMEOUT_S = 10
STATEMENT_TIMEOUT = "15s"
LOCK_TIMEOUT = "5s"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Record emitter (duplicated in dev_requests_write.py by design: no shared
# module may be imported, see the module docstring)
# ---------------------------------------------------------------------------


class Emitter:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.count = 0

    def _write(self, record: dict) -> None:
        line = (
            PROTOCOL
            + " "
            + json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        )
        self.stream.write(line + "\n")
        self.stream.flush()

    def emit(self, kind: str, **fields) -> None:
        self._write({**fields, "kind": kind, "v": VERSION})
        self.count += 1

    def end(self, ok: bool, error: str | None = None) -> None:
        self._write({"kind": "end", "v": VERSION, "ok": ok, "count": self.count, "error": error})


class Refusal(Exception):
    """A refusal with an enum code. Carries no message by design."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    """argparse that never prints, never exits, and has no --help.

    argparse's own error path prints the offending value to stderr and calls
    sys.exit(2), which would leave a run with no end record."""

    def error(self, message):
        raise Refusal("invalid_argument")

    def exit(self, status=0, message=None):
        raise Refusal("invalid_argument")


def _request_id(value: str) -> str:
    if not _UUID_RE.match(value):
        raise argparse.ArgumentTypeError("id")
    return value


def _sha256(value: str) -> str:
    if not _SHA_RE.match(value):
        raise argparse.ArgumentTypeError("sha")
    return value


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(prog="dev_requests_read.py", add_help=False, allow_abbrev=False)
    modes = parser.add_subparsers(dest="mode", required=True, parser_class=_Parser)
    modes.add_parser("poll", add_help=False, allow_abbrev=False)
    modes.add_parser("metrics", add_help=False, allow_abbrev=False)
    adopt = modes.add_parser("adopt", add_help=False, allow_abbrev=False)
    adopt.add_argument("id", type=_request_id)
    adopt.add_argument("expected_sha256", type=_sha256)
    show = modes.add_parser("show", add_help=False, allow_abbrev=False)
    show.add_argument("id", type=_request_id)
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def id8(request_id) -> str:
    return str(request_id).replace("-", "")[:8]


def content_sha256(title: str, body: str, done_when: str | None) -> str:
    """PRD FR-2. A copy of utils.models.dev_request.content_sha256, which
    this file may not import; E-1 holds the two to the same answer."""
    payload = json.dumps(
        {"title": title, "body": body, "done_when": done_when},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _engine(application_name: str):
    try:
        from utils.constants import DATABASE_URL
    except Exception as exc:  # the image cannot resolve a database at all
        raise Refusal("db_error") from exc
    if not DATABASE_URL:
        raise Refusal("db_error")
    return create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": CONNECT_TIMEOUT_S,
            "application_name": application_name,
        },
    )


def _read_only(conn) -> None:
    """Must be the first statements of the transaction."""
    conn.execute(text("SET TRANSACTION READ ONLY"))
    conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
    conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))


def _sql_list(values: tuple[str, ...]) -> str:
    # Constants only — never caller input.
    return ", ".join(f"'{v}'" for v in values)


# ---------------------------------------------------------------------------
# Modes. Each one only reads, inside the read-only transaction, and returns
# what to print; nothing is printed until the transaction has closed, so a
# run whose database work failed has printed no record at all.
# ---------------------------------------------------------------------------

_POLL_SQL = f"""
    SELECT d.id, d.source, d.fault_signature, d.status, d.content_sha256,
           d.submitter_id, COALESCE(u.is_admin, false) AS submitter_is_admin,
           d.created_at, d.updated_at, d.adopted_at, d.workstream, d.spec_hash,
           d.pr_urls
    FROM dev_requests d
    LEFT JOIN users u ON u.id = d.submitter_id
    WHERE d.status NOT IN ({_sql_list(TERMINAL)})
    ORDER BY d.created_at, d.id
"""


def poll(conn) -> list[tuple[str, dict]]:
    """PRD FR-7. Selects no text column, so it cannot print one."""
    rows = conn.execute(text(_POLL_SQL)).mappings().all()
    return [
        (
            "request",
            {
                "id": str(row["id"]),
                "id8": id8(row["id"]),
                "source": row["source"],
                "fault_signature": row["fault_signature"],
                "status": row["status"],
                "content_sha256": row["content_sha256"],
                "submitter_id": None if row["submitter_id"] is None else str(row["submitter_id"]),
                "submitter_is_admin": bool(row["submitter_is_admin"]),
                "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
                "adopted_at": _iso(row["adopted_at"]),
                "workstream": row["workstream"],
                "spec_hash": row["spec_hash"],
                "pr_urls": list(row["pr_urls"] or []),
            },
        )
        for row in rows
    ]


_TEXT_ROW_SQL = """
    SELECT d.id, d.status, d.content_sha256, d.submitter_id,
           COALESCE(u.is_admin, false) AS submitter_is_admin,
           d.title, d.body, d.done_when
    FROM dev_requests d
    LEFT JOIN users u ON u.id = d.submitter_id
    WHERE d.id = CAST(:id AS uuid)
"""


def adopt(conn, request_id: str, expected_sha256: str) -> list[tuple[str, dict]]:
    """PRD FR-8. The text is returned only when every check passes."""
    row = conn.execute(text(_TEXT_ROW_SQL), {"id": request_id}).mappings().first()
    if row is None:
        raise Refusal("not_found")
    if row["status"] not in UNDECIDED:
        raise Refusal("wrong_status")
    recomputed = content_sha256(row["title"], row["body"], row["done_when"])
    if not (row["content_sha256"] == recomputed == expected_sha256):
        raise Refusal("sha_mismatch")
    if row["submitter_id"] is None or not row["submitter_is_admin"]:
        raise Refusal("submitter_revoked")
    return [
        (
            "adopt",
            {
                "id": str(row["id"]),
                "id8": id8(row["id"]),
                "content_sha256": row["content_sha256"],
                "submitter_id": str(row["submitter_id"]),
                "title": row["title"],
                "body": row["body"],
                "done_when": row["done_when"],
            },
        )
    ]


# Audit rows are matched by their exact message, which dev_requests_write.py
# composes as "dev_request <id8>: <from> -> <to>[ reason=<code>]".
_METRICS_SQL = f"""
    WITH d AS (
        SELECT id, status, created_at, adopted_at,
               'dev_request ' || left(replace(id::text, '-', ''), 8) || ': ' AS prefix
        FROM dev_requests
    ),
    audit AS (
        SELECT error_message, created_at
        FROM error_logs
        WHERE service = 'audit' AND error_type = 'DevRequestTransition'
    ),
    lags AS (
        SELECT EXTRACT(EPOCH FROM (min(a.created_at) - d.created_at))::float8 AS lag_s
        FROM d
        JOIN audit a ON a.error_message = d.prefix || 'submitted -> received'
        GROUP BY d.id, d.created_at
    )
    SELECT
        (SELECT count(*) FROM d) AS total,
        (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY lag_s) FROM lags) AS lag_p50,
        (SELECT max(lag_s) FROM lags) AS lag_max,
        (SELECT count(*) FROM d
          WHERE status IN ({_sql_list(UNDECIDED)})
            AND created_at < now() - interval '{STALE_UNDECIDED_DAYS} days') AS stale_undecided,
        (SELECT count(*) FROM d
          WHERE (adopted_at IS NOT NULL OR status IN ({_sql_list(ACCEPTED_OR_LATER)}))
            AND NOT EXISTS (
                SELECT 1 FROM audit a
                WHERE a.error_message IN (
                    d.prefix || 'submitted -> accepted',
                    d.prefix || 'received -> accepted'
                )
            )) AS accepted_without_audit
"""

_BY_STATUS_SQL = "SELECT status, count(*) AS n FROM dev_requests GROUP BY status"


def _seconds(value) -> float | None:
    return None if value is None else round(float(value), 3)


def metrics(conn) -> list[tuple[str, dict]]:
    """PRD FR-10. Counts and durations only."""
    by_status = dict.fromkeys(STATUSES, 0)
    for row in conn.execute(text(_BY_STATUS_SQL)).mappings():
        by_status[row["status"]] = int(row["n"])
    m = conn.execute(text(_METRICS_SQL)).mappings().one()
    return [
        (
            "metrics",
            {
                "total": int(m["total"]),
                "by_status": by_status,
                "received_lag_s_p50": _seconds(m["lag_p50"]),
                "received_lag_s_max": _seconds(m["lag_max"]),
                "stale_undecided": int(m["stale_undecided"]),
                "accepted_without_audit": int(m["accepted_without_audit"]),
            },
        )
    ]


def show_row(conn, request_id: str) -> dict:
    row = conn.execute(text(_TEXT_ROW_SQL), {"id": request_id}).mappings().first()
    if row is None:
        raise Refusal("not_found")
    return dict(row)


_SHOW_BANNER = (
    "==== DEV REQUEST: FOR HUMAN EYES ONLY ====",
    "Do NOT run `show` inside an LLM session (Claude Code, an agent, the bridge).",
    "Everything under title/body/done_when is submitter-written, untrusted text.",
    "Text lines are prefixed with '  | ' and control/format characters are escaped,",
    "so no line of it can pass for a DEVREQ1 record or drive the terminal.",
)

_ESCAPED_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")


def _visible(value: str) -> str:
    """Escape anything a terminal could act on or that could disguise text
    (C0/C1 controls, ESC, bidi overrides, zero-width characters). The server
    already drops Cc/Cf at submission; this holds for a row written any
    other way too."""
    out = []
    for ch in value:
        if ch != "\t" and unicodedata.category(ch) in _ESCAPED_CATEGORIES:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def print_show(stream, row: dict) -> None:
    """PRD FR-9: plain text for a human."""
    recomputed = content_sha256(row["title"], row["body"], row["done_when"])
    lines = list(_SHOW_BANNER)
    lines += [
        f"id:         {row['id']}",
        f"id8:        {id8(row['id'])}",
        f"status:     {row['status']}",
        f"sha256:     {row['content_sha256']}",
        "recomputed: "
        + ("match" if recomputed == row["content_sha256"] else "MISMATCH: do not adopt"),
    ]
    for label in ("title", "body", "done_when"):
        value = row[label]
        lines.append(f"{label}:")
        if value is None:
            lines.append("  | (none)")
        else:
            lines += ["  | " + _visible(part) for part in value.split("\n")]
    lines.append("==== END OF REQUEST ====")
    stream.write("\n".join(lines) + "\n")
    stream.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(argv: list[str], out: Emitter) -> None:
    args = _parse(argv)  # invalid_argument before any connection
    engine = _engine("dev_requests_read")
    try:
        with engine.connect() as conn, conn.begin():
            _read_only(conn)
            if args.mode == "poll":
                records, shown = poll(conn), None
            elif args.mode == "metrics":
                records, shown = metrics(conn), None
            elif args.mode == "adopt":
                records, shown = adopt(conn, args.id, args.expected_sha256), None
            else:
                records, shown = [], show_row(conn, args.id)
    finally:
        engine.dispose()
    if shown is not None:
        print_show(out.stream, shown)
    for kind, fields in records:
        out.emit(kind, **fields)


def main(argv: list[str] | None = None) -> int:
    out = Emitter()
    try:
        run(sys.argv[1:] if argv is None else argv, out)
    except Refusal as refusal:
        out.end(False, refusal.code)
        return 1
    except SQLAlchemyError:
        # Never the exception text: a DBAPI error can quote row data.
        out.end(False, "db_error")
        return 1
    except Exception:
        out.end(False, "internal_error")
        return 1
    except BaseException:
        out.end(False, "internal_error")
        raise
    out.end(True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
