"""Audit recent `error_logs` rows to surface the most common errors.

Two modes:

    - **Aggregate (default)**: group by (service, error_type), emit the
      noisiest + freshest groups. Use for triage — "what's on fire?".
    - **Drill**: dump the most-recent N *full* rows for one group
      (stack_trace, request_id, user_id, error_code, import_item_id,
      stage, full error_message). Use after triage — "what do I need to
      fix?".

Usage:
    # Triage — top-20 (service, error_type) groups over the last 24h.
    DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py

    # Triage, last hour, all services including audit rows, JSON-lines.
    DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
        --window 1h --include-audit --format json

    # Triage, one service, 7d, noisy groups only (>= 5 hits).
    DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
        --service api --window 7d --min-samples 5 --top 50

    # Drill — last 10 full rows for api:ValueError over 24h.
    DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
        --drill api:ValueError --top 10

    # Drill, any error_type from one service (empty error_type after ':').
    DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
        --drill push_notifications: --window 7d

Default sort (aggregate): **count desc, last_seen desc** — noisiest +
freshest groups float to the top. Drill mode sorts by `created_at
DESC`. `service='audit'` rows are excluded in aggregate unless
`--include-audit` is passed; drill always operates on the exact
service you name, even `audit`.

Aggregate sample columns (all "most-recent non-null per group"):
    sample_status, sample_method, sample_path, sample_request_id,
    sample_user_id, sample_error_code, sample_stage,
    sample_import_item_id, sample_message.

Drill row columns:
    id, created_at, service, error_type, error_code, status_code,
    method, path, request_id, user_id, import_item_id, stage,
    error_message, stack_trace.

Read-only. Never writes. No audit row.

Exit codes:
    0 — rows emitted
    1 — DB / runtime error, or DATABASE_URL unset, or malformed --drill
    2 — zero rows matched the filter (informational)

Note: when this script is exec'd via `bin/prod-script` (which
concatenates a prelude before the source), `from __future__` imports
cannot appear here — they must be at the true start of a module.
`str | None` syntax works natively on Python 3.10+ so no future
import is needed.
"""

import argparse
import csv
import json
import os
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

_VALID_WINDOWS = ("1h", "24h", "7d", "30d", "all")
_VALID_FORMATS = ("table", "csv", "json")

_WINDOW_INTERVALS: dict[str, str | None] = {
    "1h": "1 hour",
    "24h": "24 hours",
    "7d": "7 days",
    "30d": "30 days",
    "all": None,
}

# Message samples can be long stack-trace-ish strings; truncate for tables
# so a single row doesn't blow up the terminal. CSV and JSON keep the
# full string.
_MESSAGE_TRUNCATE = 160

# Aggregate columns — the "most-recent non-null sample" fields give a
# reader enough correlation handles (request_id, user_id, path) to jump
# straight from a group into concrete debugging without a second query.
_AGG_COLUMNS = (
    "service",
    "error_type",
    "count",
    "distinct_users",
    "first_seen",
    "last_seen",
    "sample_status",
    "sample_method",
    "sample_path",
    "sample_request_id",
    "sample_user_id",
    "sample_error_code",
    "sample_stage",
    "sample_import_item_id",
    "sample_message",
)

# Drill columns — the full ErrorLog row, same order as the model file.
_DRILL_COLUMNS = (
    "id",
    "created_at",
    "service",
    "error_type",
    "error_code",
    "status_code",
    "method",
    "path",
    "request_id",
    "user_id",
    "import_item_id",
    "stage",
    "error_message",
    "stack_trace",
)


def _get_engine() -> Engine:
    # Prefer the env var (how the script is invoked from a developer
    # shell); fall back to utils.constants.DATABASE_URL, which is how the
    # value reaches the container when the script is exec'd via
    # `bin/prod-script` (that runner pulls the secret via Python import,
    # not into the shell env).
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            from utils.constants import DATABASE_URL  # type: ignore[import-not-found]
            url = DATABASE_URL
        except ImportError:
            pass
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    return create_engine(url)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Audit rows from `error_logs`. Default mode aggregates by "
            "(service, error_type) and shows the noisiest groups. "
            "Pass --drill SERVICE:ERROR_TYPE to dump the most-recent N "
            "full rows for one group (stack_trace, request_id, user_id, "
            "etc.). Read-only."
        ),
    )
    p.add_argument(
        "--window",
        choices=_VALID_WINDOWS,
        default="24h",
        help=(
            "Time window for the aggregation. One of "
            "'1h', '24h', '7d', '30d', 'all'. Default: 24h."
        ),
    )
    p.add_argument(
        "--top",
        type=int,
        default=20,
        help=(
            "Aggregate mode: max groups (default 20, clamped [1, 200]). "
            "Drill mode: max rows to dump (default 20, clamped [1, 200])."
        ),
    )
    p.add_argument(
        "--format",
        choices=_VALID_FORMATS,
        default="table",
        help="Output format. Default: table.",
    )
    p.add_argument(
        "--service",
        default=None,
        help=(
            "Aggregate mode: restrict to one service value (e.g. 'api', "
            "'push_notifications', 'worker'). Omit for all non-audit "
            "services. Ignored in --drill mode (--drill encodes service)."
        ),
    )
    p.add_argument(
        "--include-audit",
        action="store_true",
        help=(
            "Aggregate mode: include service='audit' rows. By default "
            "these are excluded because they are admin-action trails, "
            "not errors. Ignored in --drill mode."
        ),
    )
    p.add_argument(
        "--min-samples",
        type=int,
        default=1,
        help=(
            "Aggregate mode: drop groups with fewer than N rows. "
            "Default 1. Pass 0 to disable the floor (same effect). "
            "Ignored in --drill mode."
        ),
    )
    p.add_argument(
        "--drill",
        default=None,
        metavar="SERVICE:ERROR_TYPE",
        help=(
            "Switch to drill mode. Dumps the most-recent N full rows "
            "for one (service, error_type) group — complete with "
            "stack_trace, request_id, user_id, error_code, "
            "import_item_id, stage. Format: 'api:ValueError'. Leave "
            "error_type empty ('api:') to match any error_type within "
            "the service. JSON format is recommended for stack traces."
        ),
    )
    return p.parse_args(argv)


def _clamp_top(top: int) -> int:
    if top < 1:
        return 1
    if top > 200:
        return 200
    return top


def _parse_drill(drill: str) -> tuple[str, str | None]:
    """Parse 'service:error_type' → (service, error_type_or_None).

    Empty error_type ('api:') means "any error_type for this service".
    Validates the basic shape — one colon, non-empty service.
    """
    if ":" not in drill:
        raise ValueError(
            "--drill must be 'SERVICE:ERROR_TYPE' (colon required; "
            "error_type may be empty to match any)."
        )
    service, _, error_type = drill.partition(":")
    service = service.strip()
    error_type = error_type.strip()
    if not service:
        raise ValueError("--drill service part must be non-empty.")
    return service, (error_type or None)


def _build_agg_query(
    *,
    window: str,
    min_samples: int,
    top: int,
    service: str | None,
    include_audit: bool,
) -> tuple[str, dict[str, Any]]:
    """Return (sql, bind_params) for aggregate mode.

    The bind params carry user-supplied strings (`service`) so they
    can't be SQL-injected via the CLI. Interval / LIMIT / HAVING
    threshold are literal-interpolated because they're CLI-constrained
    enums or ints — this matches the style of analyze_latency.py.
    """
    predicates: list[str] = []
    params: dict[str, Any] = {}

    interval = _WINDOW_INTERVALS[window]
    if interval is not None:
        predicates.append(f"created_at >= NOW() - INTERVAL '{interval}'")

    if service is not None:
        predicates.append("service = :service")
        params["service"] = service
    elif not include_audit:
        predicates.append("service <> 'audit'")

    where_sql = f" WHERE {' AND '.join(predicates)}" if predicates else ""
    having_sql = (
        f" HAVING COUNT(*) >= {min_samples}" if min_samples > 1 else ""
    )

    # array_agg(... ORDER BY created_at DESC) FILTER (...)[1] gives us
    # the most-recent non-null value per group. error_message is NOT
    # NULL per schema, so no FILTER on that one.
    return (
        "SELECT "
        "  service, "
        "  error_type, "
        "  COUNT(*) AS count, "
        "  COUNT(DISTINCT user_id) AS distinct_users, "
        "  MIN(created_at) AS first_seen, "
        "  MAX(created_at) AS last_seen, "
        "  (array_agg(status_code ORDER BY created_at DESC) "
        "     FILTER (WHERE status_code IS NOT NULL))[1] AS sample_status, "
        "  (array_agg(method ORDER BY created_at DESC) "
        "     FILTER (WHERE method IS NOT NULL))[1] AS sample_method, "
        "  (array_agg(path ORDER BY created_at DESC) "
        "     FILTER (WHERE path IS NOT NULL))[1] AS sample_path, "
        "  (array_agg(request_id ORDER BY created_at DESC) "
        "     FILTER (WHERE request_id IS NOT NULL))[1] AS sample_request_id, "
        "  (array_agg(user_id ORDER BY created_at DESC) "
        "     FILTER (WHERE user_id IS NOT NULL))[1] AS sample_user_id, "
        "  (array_agg(error_code ORDER BY created_at DESC) "
        "     FILTER (WHERE error_code IS NOT NULL))[1] AS sample_error_code, "
        "  (array_agg(stage ORDER BY created_at DESC) "
        "     FILTER (WHERE stage IS NOT NULL))[1] AS sample_stage, "
        "  (array_agg(import_item_id ORDER BY created_at DESC) "
        "     FILTER (WHERE import_item_id IS NOT NULL))[1] AS sample_import_item_id, "
        "  (array_agg(error_message ORDER BY created_at DESC))[1] AS sample_message "
        "FROM error_logs"
        f"{where_sql}"
        " GROUP BY service, error_type"
        f"{having_sql}"
        " ORDER BY count DESC, last_seen DESC NULLS LAST"
        f" LIMIT {top}"
    ), params


def _build_drill_query(
    *,
    window: str,
    top: int,
    service: str,
    error_type: str | None,
) -> tuple[str, dict[str, Any]]:
    """Return (sql, bind_params) for drill mode.

    Emits individual rows, most-recent first, for one (service,
    error_type) group. error_type=None means "any error_type for this
    service".
    """
    predicates: list[str] = ["service = :service"]
    params: dict[str, Any] = {"service": service}

    interval = _WINDOW_INTERVALS[window]
    if interval is not None:
        predicates.append(f"created_at >= NOW() - INTERVAL '{interval}'")

    if error_type is not None:
        predicates.append("error_type = :error_type")
        params["error_type"] = error_type

    where_sql = f" WHERE {' AND '.join(predicates)}"

    return (
        "SELECT "
        "  id, "
        "  created_at, "
        "  service, "
        "  error_type, "
        "  error_code, "
        "  status_code, "
        "  method, "
        "  path, "
        "  request_id, "
        "  user_id, "
        "  import_item_id, "
        "  stage, "
        "  error_message, "
        "  stack_trace "
        "FROM error_logs"
        f"{where_sql}"
        " ORDER BY created_at DESC"
        f" LIMIT {top}"
    ), params


def _stream_query(
    conn: Connection, sql: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    result = conn.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


def _truncate(value: Any, limit: int = _MESSAGE_TRUNCATE) -> str:
    if value is None:
        return ""
    s = str(value).replace("\n", " ").replace("\r", " ")
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _short_uuid(value: Any) -> str:
    if value is None:
        return "-"
    s = str(value)
    return s[:8] if len(s) >= 8 else s


def _coerce_agg_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": row.get("service"),
        "error_type": row.get("error_type"),
        "count": int(row["count"]) if row.get("count") is not None else 0,
        "distinct_users": int(row["distinct_users"])
        if row.get("distinct_users") is not None
        else 0,
        "first_seen": row.get("first_seen"),
        "last_seen": row.get("last_seen"),
        "sample_status": int(row["sample_status"])
        if row.get("sample_status") is not None
        else None,
        "sample_method": row.get("sample_method"),
        "sample_path": row.get("sample_path"),
        "sample_request_id": row.get("sample_request_id"),
        "sample_user_id": row.get("sample_user_id"),
        "sample_error_code": int(row["sample_error_code"])
        if row.get("sample_error_code") is not None
        else None,
        "sample_stage": row.get("sample_stage"),
        "sample_import_item_id": row.get("sample_import_item_id"),
        "sample_message": row.get("sample_message"),
    }


def _coerce_drill_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "created_at": row.get("created_at"),
        "service": row.get("service"),
        "error_type": row.get("error_type"),
        "error_code": int(row["error_code"])
        if row.get("error_code") is not None
        else None,
        "status_code": int(row["status_code"])
        if row.get("status_code") is not None
        else None,
        "method": row.get("method"),
        "path": row.get("path"),
        "request_id": row.get("request_id"),
        "user_id": row.get("user_id"),
        "import_item_id": row.get("import_item_id"),
        "stage": row.get("stage"),
        "error_message": row.get("error_message"),
        "stack_trace": row.get("stack_trace"),
    }


def _fmt_ts(value: Any) -> str:
    if value is None:
        return "-"
    # sqlalchemy gives us datetime; stringify cheaply, drop microseconds.
    s = str(value)
    if "." in s:
        s = s.split(".", 1)[0]
    return s


def _emit_agg_table(rows: list[dict[str, Any]]) -> int:
    if not rows:
        sys.stdout.write("(no error_logs rows matched the filter)\n")
        return 0
    # Short correlation-ID columns (REQ, USER) give enough info to cross-
    # reference logs / reproduce without blowing up line width. Full
    # values are preserved in --format json / csv.
    sys.stdout.write(
        f"{'SERVICE':<18} {'ERROR_TYPE':<28} "
        f"{'COUNT':>6} {'USERS':>5} {'LAST_SEEN':<19} "
        f"{'STS':>4} {'MTH':<5} {'REQ':<9} {'USER':<9} "
        f"{'PATH':<32} MESSAGE\n"
    )
    for row in rows:
        sys.stdout.write(
            f"{_truncate(row.get('service'), 18):<18} "
            f"{_truncate(row.get('error_type'), 28):<28} "
            f"{row.get('count', 0):>6} "
            f"{row.get('distinct_users', 0):>5} "
            f"{_fmt_ts(row.get('last_seen')):<19} "
            f"{row.get('sample_status') or '-':>4} "
            f"{_truncate(row.get('sample_method'), 5):<5} "
            f"{_short_uuid(row.get('sample_request_id')):<9} "
            f"{_short_uuid(row.get('sample_user_id')):<9} "
            f"{_truncate(row.get('sample_path'), 32):<32} "
            f"{_truncate(row.get('sample_message'), 80)}\n"
        )
    return len(rows)


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _emit_agg_csv(rows: list[dict[str, Any]]) -> int:
    writer = csv.writer(sys.stdout)
    writer.writerow(_AGG_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(row[c]) for c in _AGG_COLUMNS])
    return len(rows)


def _emit_agg_json(rows: list[dict[str, Any]]) -> int:
    for row in rows:
        sys.stdout.write(json.dumps(row, default=str))
        sys.stdout.write("\n")
    return len(rows)


def _emit_agg(fmt: str, rows: list[dict[str, Any]]) -> int:
    if fmt == "csv":
        return _emit_agg_csv(rows)
    if fmt == "json":
        return _emit_agg_json(rows)
    return _emit_agg_table(rows)


def _emit_drill_table(rows: list[dict[str, Any]]) -> int:
    """Vertical per-row display — one record per block, field:value lines,
    dash separators. Readable for small N; JSON is better for large N or
    for piping into another tool."""
    if not rows:
        sys.stdout.write("(no error_logs rows matched --drill filter)\n")
        return 0
    for idx, row in enumerate(rows):
        if idx > 0:
            sys.stdout.write("-" * 72 + "\n")
        sys.stdout.write(f"id:              {row.get('id') or '-'}\n")
        sys.stdout.write(
            f"created_at:      {_fmt_ts(row.get('created_at'))}\n"
        )
        sys.stdout.write(f"service:         {row.get('service') or '-'}\n")
        sys.stdout.write(
            f"error_type:      {row.get('error_type') or '-'}\n"
        )
        sys.stdout.write(
            f"error_code:      {row.get('error_code') if row.get('error_code') is not None else '-'}\n"
        )
        sys.stdout.write(
            f"status_code:     {row.get('status_code') if row.get('status_code') is not None else '-'}\n"
        )
        sys.stdout.write(f"method:          {row.get('method') or '-'}\n")
        sys.stdout.write(f"path:            {row.get('path') or '-'}\n")
        sys.stdout.write(
            f"request_id:      {row.get('request_id') or '-'}\n"
        )
        sys.stdout.write(f"user_id:         {row.get('user_id') or '-'}\n")
        sys.stdout.write(
            f"import_item_id:  {row.get('import_item_id') or '-'}\n"
        )
        sys.stdout.write(f"stage:           {row.get('stage') or '-'}\n")
        sys.stdout.write("error_message:\n")
        msg = row.get("error_message") or "-"
        for line in str(msg).splitlines() or ["-"]:
            sys.stdout.write(f"  {line}\n")
        sys.stdout.write("stack_trace:\n")
        trace = row.get("stack_trace")
        if trace is None:
            sys.stdout.write("  (none)\n")
        else:
            for line in str(trace).splitlines():
                sys.stdout.write(f"  {line}\n")
    return len(rows)


def _emit_drill_csv(rows: list[dict[str, Any]]) -> int:
    writer = csv.writer(sys.stdout)
    writer.writerow(_DRILL_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(row[c]) for c in _DRILL_COLUMNS])
    return len(rows)


def _emit_drill_json(rows: list[dict[str, Any]]) -> int:
    for row in rows:
        sys.stdout.write(json.dumps(row, default=str))
        sys.stdout.write("\n")
    return len(rows)


def _emit_drill(fmt: str, rows: list[dict[str, Any]]) -> int:
    if fmt == "csv":
        return _emit_drill_csv(rows)
    if fmt == "json":
        return _emit_drill_json(rows)
    return _emit_drill_table(rows)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    top = _clamp_top(args.top)
    min_samples = max(0, args.min_samples)

    drill_service: str | None = None
    drill_error_type: str | None = None
    if args.drill is not None:
        try:
            drill_service, drill_error_type = _parse_drill(args.drill)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    engine = _get_engine()

    try:
        with engine.connect() as conn:
            if drill_service is not None:
                sql, params = _build_drill_query(
                    window=args.window,
                    top=top,
                    service=drill_service,
                    error_type=drill_error_type,
                )
                raw = _stream_query(conn, sql, params)
                rows = [_coerce_drill_row(r) for r in raw]
            else:
                sql, params = _build_agg_query(
                    window=args.window,
                    min_samples=min_samples,
                    top=top,
                    service=args.service,
                    include_audit=args.include_audit,
                )
                raw = _stream_query(conn, sql, params)
                rows = [_coerce_agg_row(r) for r in raw]
    except Exception as e:  # noqa: BLE001 — surface any DB/query issue on exit-1
        print(
            f"ERROR: failed to audit error_logs: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if drill_service is not None:
        total = _emit_drill(args.format, rows)
    else:
        total = _emit_agg(args.format, rows)

    if total == 0:
        print(
            "INFO: no error_logs rows matched the filter.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
