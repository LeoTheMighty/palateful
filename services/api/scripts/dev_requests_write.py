"""Write side of the operator channel for dev requests (admin-request-intake).

Usage (through the channel, as the bridge runs it):
    bin/prod-script services/api/scripts/dev_requests_write.py \\
        transition <id> <from> <to> [--sha <hex64>] [--reason <code>]

or standalone, against whatever database ``utils.constants`` resolves:
    python services/api/scripts/dev_requests_write.py transition <id> submitted received

The only writer of the statuses the bridge owns (PRD FR-11, FR-12). One call
applies at most one status change:

- **No free text.** ``id`` is a canonical lowercase UUID, ``from``/``to`` are
  FR-12 statuses, ``--sha`` is 64 lowercase hex, ``--reason`` is an enum code.
  Anything else, a repeated option, or an option the edge does not take, is
  ``invalid_argument`` before any connection is opened.
- **Only the slice edges.** Every other edge is ``illegal_transition`` until
  arq106 adds the widening edges.
- **Compare-and-set, idempotent.** In one transaction with the row locked:
  already at ``to`` -> ``changed: false`` and nothing written; at ``from`` ->
  applied; anywhere else -> ``conflict``.
- ``-> accepted`` re-checks the hash (stored == recomputed == ``--sha``) and
  the submitter (non-null and currently an admin), and stamps ``adopted_at``.
- **Audited.** Each applied change writes exactly one ``error_logs`` row
  (``service="audit"``, ``error_type="DevRequestTransition"``) in the same
  transaction: ``"dev_request <id8>: <from> -> <to>[ reason=<code>]"``, with
  ``user_id`` = the submitter. A no-op or a refusal writes nothing.

Output is the DEVREQ1 record protocol (PRD FR-6); see dev_requests_read.py.
The transition record is printed only after the transaction has committed.

Constraints this file is written to (same as dev_requests_read.py): imports
only the standard library, SQLAlchemy and ``utils.constants``; the URL comes
from ``utils.constants.DATABASE_URL`` (prod has only ``DB_*``); no
``from __future__``; no rebinding of ``sys`` or ``time``.
"""

import argparse
import hashlib
import json
import re
import sys
import uuid

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
DECLINE_REASONS = ("duplicate", "wont_do", "unclear", "unsafe")
WITHDRAW_REASON = "submitter_revoked"
REASONS = (*DECLINE_REASONS, WITHDRAW_REASON)

# The edges PRD FR-12 gives the bridge in slice 1. The widening edges
# (accepted -> scoping ... -> shipped, waiting_on_leo, stopped, reverted) are
# deliberately absent: they stay illegal_transition until arq106.
SLICE_EDGES = frozenset(
    {
        ("submitted", "received"),
        ("submitted", "accepted"),
        ("received", "accepted"),
        ("submitted", "declined"),
        ("received", "declined"),
        ("submitted", "withdrawn"),
        ("received", "withdrawn"),
    }
)

AUDIT_ERROR_TYPE = "DevRequestTransition"

# Bounds on what one run may cost production. lock_timeout is what keeps a
# run from queueing behind another writer's lock on the row.
CONNECT_TIMEOUT_S = 10
STATEMENT_TIMEOUT = "15s"
LOCK_TIMEOUT = "5s"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Record emitter (duplicated in dev_requests_read.py by design: no shared
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


class _Once(argparse.Action):
    """Store an option, refusing a second occurrence (argparse keeps the last)."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            raise Refusal("invalid_argument")
        setattr(namespace, self.dest, values)


def _pattern(regex: re.Pattern):
    def check(value: str) -> str:
        if not regex.match(value):
            raise argparse.ArgumentTypeError("invalid")
        return value

    return check


def _one_of(values: tuple[str, ...]):
    def check(value: str) -> str:
        if value not in values:
            raise argparse.ArgumentTypeError("invalid")
        return value

    return check


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(prog="dev_requests_write.py", add_help=False, allow_abbrev=False)
    modes = parser.add_subparsers(dest="mode", required=True, parser_class=_Parser)
    tr = modes.add_parser("transition", add_help=False, allow_abbrev=False)
    tr.add_argument("id", type=_pattern(_UUID_RE))
    tr.add_argument("frm", metavar="from", type=_one_of(STATUSES))
    tr.add_argument("to", type=_one_of(STATUSES))
    tr.add_argument("--sha", type=_pattern(_SHA_RE), action=_Once, default=None)
    tr.add_argument("--reason", type=_one_of(REASONS), action=_Once, default=None)
    return parser.parse_args(argv)


def check_edge(frm: str, to: str, sha: str | None, reason: str | None) -> None:
    """Everything decidable from the arguments alone, before any query."""
    if (frm, to) not in SLICE_EDGES:
        raise Refusal("illegal_transition")
    if to == "accepted":
        ok = sha is not None and reason is None
    elif to == "declined":
        ok = sha is None and reason in DECLINE_REASONS
    elif to == "withdrawn":
        ok = sha is None and reason == WITHDRAW_REASON
    else:  # received
        ok = sha is None and reason is None
    if not ok:
        raise Refusal("invalid_argument")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def id8(request_id) -> str:
    return str(request_id).replace("-", "")[:8]


def content_sha256(title: str, body: str, done_when: str | None) -> str:
    """PRD FR-2. A copy of utils.models.dev_request.content_sha256, which
    this file may not import."""
    payload = json.dumps(
        {"title": title, "body": body, "done_when": done_when},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_message(request_id, frm: str, to: str, reason: str | None) -> str:
    """Composed only of the id8, two validated statuses and a reason code."""
    message = f"dev_request {id8(request_id)}: {frm} -> {to}"
    return message if reason is None else f"{message} reason={reason}"


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


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------

# FOR UPDATE OF d: lock the request row only, never the submitter's users row.
_LOCK_SQL = """
    SELECT d.id, d.status, d.content_sha256, d.submitter_id,
           COALESCE(u.is_admin, false) AS submitter_is_admin,
           d.title, d.body, d.done_when
    FROM dev_requests d
    LEFT JOIN users u ON u.id = d.submitter_id
    WHERE d.id = CAST(:id AS uuid)
    FOR UPDATE OF d
"""

_UPDATE_SQL = """
    UPDATE dev_requests
    SET status = :to,
        updated_at = now(),
        synced_at = now(),
        adopted_at = CASE WHEN :to = 'accepted' THEN now() ELSE adopted_at END
    WHERE id = CAST(:id AS uuid) AND status = :frm
"""

_AUDIT_SQL = """
    INSERT INTO error_logs (id, created_at, updated_at, error_type, error_message, service, user_id)
    VALUES (CAST(:audit_id AS uuid), now(), now(), :etype, :emsg, 'audit', :uid)
"""


def _hash_matches(row, sha: str) -> bool:
    recomputed = content_sha256(row["title"], row["body"], row["done_when"])
    return row["content_sha256"] == recomputed == sha


def transition(conn, request_id: str, frm: str, to: str, sha, reason) -> bool:
    """Returns whether a change was applied. Raises Refusal otherwise."""
    conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
    conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    row = conn.execute(text(_LOCK_SQL), {"id": request_id}).mappings().first()
    if row is None:
        raise Refusal("not_found")
    current = row["status"]
    if current == to:
        # A repeat. For an adoption, still refuse a hash that is not this
        # row's: the caller must not believe it adopted other text.
        if to == "accepted" and not _hash_matches(row, sha):
            raise Refusal("sha_mismatch")
        return False
    if current != frm:
        raise Refusal("conflict")
    if to == "accepted":
        if not _hash_matches(row, sha):
            raise Refusal("sha_mismatch")
        if row["submitter_id"] is None or not row["submitter_is_admin"]:
            raise Refusal("submitter_revoked")
    updated = conn.execute(text(_UPDATE_SQL), {"id": request_id, "frm": frm, "to": to})
    if updated.rowcount != 1:  # unreachable under the row lock; never write half
        raise Refusal("conflict")
    conn.execute(
        text(_AUDIT_SQL),
        {
            "audit_id": str(uuid.uuid4()),
            "etype": AUDIT_ERROR_TYPE,
            "emsg": audit_message(request_id, frm, to, reason),
            "uid": row["submitter_id"],
        },
    )
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(argv: list[str], out: Emitter) -> None:
    args = _parse(argv)
    check_edge(args.frm, args.to, args.sha, args.reason)  # before any connection
    engine = _engine("dev_requests_write")
    try:
        with engine.connect() as conn, conn.begin():
            changed = transition(conn, args.id, args.frm, args.to, args.sha, args.reason)
    finally:
        engine.dispose()
    # Committed (or a no-op) by now: the record never claims an uncommitted change.
    out.emit(
        "transition",
        id=args.id,
        id8=id8(args.id),
        changed=changed,
        to=args.to,
        **{"from": args.frm},
    )


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
