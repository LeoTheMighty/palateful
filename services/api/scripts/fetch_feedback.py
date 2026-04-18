"""Fetch user feedback rows for offline review.

Usage:
    # Default — last 7 days of unread feedback as CSV to stdout.
    DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py

    # 30 days of all feedback, JSON-lines.
    DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py \
        --since 30d --status all --format json > /tmp/feedback.jsonl

    # Everything ever, tab-separated.
    DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py \
        --since all --status all --format tsv > /tmp/feedback.tsv

Requires DATABASE_URL to be set in the environment. Uses raw SQLAlchemy
so the script can run against prod without booting the FastAPI app.
Read-only — no mutations. Streams rows to stdout via `stream_results`
so memory stays bounded at any `--since` window.

Writes a single audit row to `error_logs` at end-of-run with filter args
and row count (service="audit", error_type="FeedbackExport") — keeps
ops-side visibility without polluting api-error dashboards.

Exit codes:
    0 — success (at least one row emitted)
    1 — DB / runtime error
    2 — zero rows matched the filter (informational, not a failure)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

SCRIPT_ACTOR = "script:fetch_feedback"

_SINCE_PRESETS = {
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}

_VALID_STATUS = ("unread", "read", "archived", "all")
_VALID_FORMAT = ("csv", "tsv", "json")

_COLUMNS = [
    "id",
    "user_id",
    "user_email",
    "user_name",
    "body",
    "category",
    "status",
    "context",
    "created_at",
    "updated_at",
]


def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    return create_engine(url)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export user feedback rows to stdout. Read-only. "
            "Streams results so memory stays bounded at any window size."
        ),
    )
    p.add_argument(
        "--since",
        default="7d",
        help="Time window. One of '7d', '30d', '90d', 'all'. Default: 7d.",
    )
    p.add_argument(
        "--status",
        choices=_VALID_STATUS,
        default="unread",
        help="Filter by status. Default: unread.",
    )
    p.add_argument(
        "--format",
        choices=_VALID_FORMAT,
        default="csv",
        help="Output format. Default: csv.",
    )
    return p.parse_args(argv)


def _resolve_since(value: str) -> datetime | None:
    """Return the cutoff datetime for the SQL `created_at >= :cutoff` filter.

    Returns None for `--since all`, which means no filter.
    """
    if value == "all":
        return None
    if value not in _SINCE_PRESETS:
        print(
            f"ERROR: --since must be one of {list(_SINCE_PRESETS) + ['all']}, "
            f"got {value!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    return datetime.now(UTC) - _SINCE_PRESETS[value]


def _build_query(status: str, cutoff: datetime | None) -> tuple[str, dict[str, Any]]:
    """Build the SELECT. Parameters are bound via `text(...).bindparams`."""
    wheres: list[str] = []
    params: dict[str, Any] = {}
    if status != "all":
        wheres.append("f.status = :status")
        params["status"] = status
    if cutoff is not None:
        wheres.append("f.created_at >= :cutoff")
        params["cutoff"] = cutoff
    where_sql = (" WHERE " + " AND ".join(wheres)) if wheres else ""
    sql = (
        "SELECT f.id, f.user_id, u.email AS user_email, u.name AS user_name, "
        "f.body, f.category, f.status, f.context, f.created_at, f.updated_at "
        "FROM user_feedbacks f "
        "LEFT JOIN users u ON u.id = f.user_id"
        f"{where_sql} "
        "ORDER BY f.created_at DESC"
    )
    return sql, params


def _stream_rows(conn: Connection, sql: str, params: dict[str, Any]):
    """Yield each row as a dict. Uses streaming execution so large windows
    don't buffer the full result set in memory."""
    result = conn.execution_options(stream_results=True).execute(
        text(sql), params
    )
    for row in result:
        yield dict(row._mapping)


def _format_value_for_text(value: Any) -> str:
    """Coerce a value to a safe string for CSV/TSV cells."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, default=str)
    return str(value)


def _emit_rows(rows_iter, fmt: str) -> int:
    """Write rows to stdout in the requested format.

    Returns the number of rows emitted.
    """
    count = 0
    if fmt == "json":
        for row in rows_iter:
            encoded = {}
            for key in _COLUMNS:
                raw = row.get(key)
                if isinstance(raw, datetime):
                    encoded[key] = raw.isoformat()
                else:
                    encoded[key] = raw
            sys.stdout.write(json.dumps(encoded, default=str))
            sys.stdout.write("\n")
            count += 1
        return count

    delimiter = "\t" if fmt == "tsv" else ","
    writer = csv.writer(sys.stdout, delimiter=delimiter)
    writer.writerow(_COLUMNS)
    for row in rows_iter:
        writer.writerow([_format_value_for_text(row.get(k)) for k in _COLUMNS])
        count += 1
    return count


def _write_audit_row(
    engine: Engine,
    *,
    since: str,
    status: str,
    fmt: str,
    row_count: int,
) -> None:
    """Best-effort audit write. Silent on failure so a flaky DB write at
    end-of-run doesn't turn a successful export into exit-code-1."""
    try:
        message = (
            f"feedback_export since={since} status={status} format={fmt} "
            f"rows={row_count} by {SCRIPT_ACTOR}"
        )
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO error_logs (
                        id, created_at, updated_at,
                        error_type, error_message, service
                    ) VALUES (
                        gen_random_uuid(), :now, :now,
                        :etype, :emsg, :svc
                    )
                    """
                ),
                {
                    "now": datetime.now(UTC),
                    "etype": "FeedbackExport",
                    "emsg": message,
                    "svc": "audit",
                },
            )
    except Exception as e:  # noqa: BLE001 — audit is best-effort
        print(
            f"WARN: failed to write audit row: {type(e).__name__}: {e}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    cutoff = _resolve_since(args.since)
    sql, params = _build_query(args.status, cutoff)
    engine = _get_engine()

    try:
        with engine.connect() as conn:
            row_count = _emit_rows(_stream_rows(conn, sql, params), args.format)
    except Exception as e:  # noqa: BLE001 — surface any DB issue on exit-1
        print(
            f"ERROR: failed to export feedback: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    _write_audit_row(
        engine,
        since=args.since,
        status=args.status,
        fmt=args.format,
        row_count=row_count,
    )

    if row_count == 0:
        print(
            "INFO: no feedback rows matched the filter.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
