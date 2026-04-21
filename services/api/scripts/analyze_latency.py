"""Analyze endpoint + task latency samples from `request_latencies` and
`task_latencies` to surface the slowest paths and hunt for regressions.

Usage:
    # Default — top-15 endpoints + tasks by p95 over the last 24h.
    DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py

    # CSV to pipe into diff.
    DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
        --window 24h --top 15 --format csv > /tmp/baseline.csv

    # Recent-vs-baseline regression hunt (endpoints only).
    DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
        --regression-hunt --format table

    # Endpoints only, last hour, no noise floor.
    DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
        --section endpoints --window 1h --min-samples 0

Default sort is **p95 desc** across every output shape.

Read-only. Never writes. No audit row.

Exit codes:
    0 — rows emitted
    1 — DB / runtime error, or DATABASE_URL unset
    2 — zero rows matched the filter (informational)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

_VALID_WINDOWS = ("1h", "24h", "7d", "all")
_VALID_FORMATS = ("table", "csv", "json")
_VALID_SECTIONS = ("endpoints", "tasks", "both")

# SQL interval strings keyed by the --window preset. `all` returns None so
# the WHERE clause is dropped entirely.
_WINDOW_INTERVALS: dict[str, str | None] = {
    "1h": "1 hour",
    "24h": "24 hours",
    "7d": "7 days",
    "all": None,
}

_ENDPOINT_COLUMNS = (
    "section",
    "method",
    "normalized_path",
    "count",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
)
_TASK_COLUMNS = (
    "section",
    "task_name",
    "status",
    "count",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
)
_REGRESSION_COLUMNS = (
    "section",
    "method",
    "normalized_path",
    "baseline_p95_ms",
    "recent_p95_ms",
    "pct_increase",
    "recent_count",
)


def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    return create_engine(url)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Analyze request_latencies + task_latencies to surface the "
            "slowest paths. Read-only. Default sort: p95 desc. "
            "Use --regression-hunt to compare recent 24h vs 7-to-30d "
            "baseline."
        ),
    )
    p.add_argument(
        "--window",
        choices=_VALID_WINDOWS,
        default="24h",
        help=(
            "Time window for the aggregation. One of "
            "'1h', '24h', '7d', 'all'. Default: 24h."
        ),
    )
    p.add_argument(
        "--top",
        type=int,
        default=15,
        help="Max rows per section. Default 15. Clamped to [1, 100].",
    )
    p.add_argument(
        "--format",
        choices=_VALID_FORMATS,
        default="table",
        help="Output format. Default: table.",
    )
    p.add_argument(
        "--regression-hunt",
        action="store_true",
        help=(
            "Swap the default query for a recent-vs-baseline CTE that "
            "flags endpoints whose recent-24h p95 is >1.5x the "
            "7-to-30d baseline. Implies --section endpoints."
        ),
    )
    p.add_argument(
        "--min-samples",
        type=int,
        default=5,
        help=(
            "Drop groups with fewer than N samples. Default 5. "
            "Pass 0 to disable the floor."
        ),
    )
    p.add_argument(
        "--section",
        choices=_VALID_SECTIONS,
        default="both",
        help="Which sections to emit. Default: both.",
    )
    return p.parse_args(argv)


def _clamp_top(top: int) -> int:
    if top < 1:
        return 1
    if top > 100:
        return 100
    return top


def _window_clause(window: str, column: str = "created_at") -> str:
    """Return ` AND {col} >= NOW() - INTERVAL '...'` or '' for --window all.

    Returned string is already prefixed with the leading ` AND ` so it
    splices cleanly into a WHERE clause that already has at least one
    predicate. Callers that want a WHERE-opener use `_window_where`.
    """
    interval = _WINDOW_INTERVALS[window]
    if interval is None:
        return ""
    return f" AND {column} >= NOW() - INTERVAL '{interval}'"


def _window_where(window: str, column: str = "created_at") -> str:
    """Return ` WHERE {col} >= NOW() - ...` or '' for --window all."""
    interval = _WINDOW_INTERVALS[window]
    if interval is None:
        return ""
    return f" WHERE {column} >= NOW() - INTERVAL '{interval}'"


def _build_endpoint_query(window: str, top: int, min_samples: int) -> str:
    where_sql = _window_where(window)
    having_sql = (
        f" HAVING COUNT(*) >= {min_samples}" if min_samples > 0 else ""
    )
    return (
        "SELECT "
        "method, normalized_path, "
        "COUNT(*) AS count, "
        "PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50_ms, "
        "PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms, "
        "PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99_ms, "
        "MAX(duration_ms) AS max_ms "
        "FROM request_latencies"
        f"{where_sql}"
        " GROUP BY method, normalized_path"
        f"{having_sql}"
        " ORDER BY p95_ms DESC NULLS LAST"
        f" LIMIT {top}"
    )


def _build_task_query(window: str, top: int, min_samples: int) -> str:
    where_sql = _window_where(window)
    having_sql = (
        f" HAVING COUNT(*) >= {min_samples}" if min_samples > 0 else ""
    )
    return (
        "SELECT "
        "task_name, status, "
        "COUNT(*) AS count, "
        "PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50_ms, "
        "PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms, "
        "PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99_ms, "
        "MAX(duration_ms) AS max_ms "
        "FROM task_latencies"
        f"{where_sql}"
        " GROUP BY task_name, status"
        f"{having_sql}"
        " ORDER BY p95_ms DESC NULLS LAST"
        f" LIMIT {top}"
    )


def _build_regression_query(top: int) -> str:
    """Recent-24h vs 7-to-30d-baseline CTE from the architecture addendum.

    Thresholds (hardcoded):
      - recent.cnt >= 10
      - baseline.p95 IS NOT NULL
      - recent.p95 > baseline.p95 * 1.5
    """
    return (
        "WITH recent AS ("
        "  SELECT method, normalized_path, COUNT(*) AS cnt, "
        "         PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95 "
        "  FROM request_latencies"
        "  WHERE created_at >= NOW() - INTERVAL '24 hours'"
        "  GROUP BY method, normalized_path"
        "), baseline AS ("
        "  SELECT method, normalized_path, "
        "         PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95 "
        "  FROM request_latencies"
        "  WHERE created_at >= NOW() - INTERVAL '30 days'"
        "    AND created_at <  NOW() - INTERVAL '7 days'"
        "  GROUP BY method, normalized_path"
        ")"
        " SELECT recent.method AS method,"
        "        recent.normalized_path AS normalized_path,"
        "        baseline.p95 AS baseline_p95_ms,"
        "        recent.p95 AS recent_p95_ms,"
        "        ROUND((recent.p95 / NULLIF(baseline.p95, 0) - 1) * 100, 1) AS pct_increase,"
        "        recent.cnt AS recent_count"
        " FROM recent LEFT JOIN baseline USING (method, normalized_path)"
        " WHERE recent.cnt >= 10"
        "   AND baseline.p95 IS NOT NULL"
        "   AND recent.p95 > baseline.p95 * 1.5"
        " ORDER BY pct_increase DESC NULLS LAST"
        f" LIMIT {top}"
    )


def _stream_query(conn: Connection, sql: str) -> list[dict[str, Any]]:
    """Execute a query and materialize rows as dicts.

    We don't stream here because the aggregation itself already collapses
    the table to <= `top` rows — there's nothing to stream and downstream
    code wants to iterate multiple times (section header + data).
    """
    result = conn.execute(text(sql))
    return [dict(row._mapping) for row in result]


def _round_ms(value: Any) -> float | None:
    """Coerce a numeric result cell to a float with 1-decimal precision.

    `PERCENTILE_CONT` returns a double precision; Postgres may return it
    as a `decimal.Decimal` via psycopg2, or as a float via psycopg3. Keep
    downstream formatters simple by collapsing to float-or-None.
    """
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _coerce_endpoint_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": "endpoints",
        "method": row.get("method"),
        "normalized_path": row.get("normalized_path"),
        "count": int(row["count"]) if row.get("count") is not None else 0,
        "p50_ms": _round_ms(row.get("p50_ms")),
        "p95_ms": _round_ms(row.get("p95_ms")),
        "p99_ms": _round_ms(row.get("p99_ms")),
        "max_ms": int(row["max_ms"]) if row.get("max_ms") is not None else None,
    }


def _coerce_task_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": "tasks",
        "task_name": row.get("task_name"),
        "status": row.get("status"),
        "count": int(row["count"]) if row.get("count") is not None else 0,
        "p50_ms": _round_ms(row.get("p50_ms")),
        "p95_ms": _round_ms(row.get("p95_ms")),
        "p99_ms": _round_ms(row.get("p99_ms")),
        "max_ms": int(row["max_ms"]) if row.get("max_ms") is not None else None,
    }


def _coerce_regression_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": "regression",
        "method": row.get("method"),
        "normalized_path": row.get("normalized_path"),
        "baseline_p95_ms": _round_ms(row.get("baseline_p95_ms")),
        "recent_p95_ms": _round_ms(row.get("recent_p95_ms")),
        "pct_increase": _round_ms(row.get("pct_increase")),
        "recent_count": int(row["recent_count"])
        if row.get("recent_count") is not None
        else 0,
    }


def _emit_table(
    *,
    endpoints: list[dict[str, Any]] | None,
    tasks: list[dict[str, Any]] | None,
    regression: list[dict[str, Any]] | None,
) -> int:
    """Write human-readable table(s) to stdout. Returns total row count."""
    total = 0

    if regression is not None:
        sys.stdout.write(
            "regression_hunt (recent 24h p95 > 1.5x baseline p95, "
            "sorted by % increase)\n"
        )
        if not regression:
            sys.stdout.write("  (no regressions over threshold)\n")
        else:
            sys.stdout.write(
                f"  {'METHOD':<7} {'PATH':<50} "
                f"{'BASE_P95':>10} {'CUR_P95':>10} {'%':>8} {'COUNT':>8}\n"
            )
            for row in regression:
                total += 1
                sys.stdout.write(
                    f"  {str(row.get('method') or '-'):<7} "
                    f"{str(row.get('normalized_path') or '-'):<50.50} "
                    f"{_fmt_num(row.get('baseline_p95_ms')):>10} "
                    f"{_fmt_num(row.get('recent_p95_ms')):>10} "
                    f"{_fmt_num(row.get('pct_increase')):>8} "
                    f"{row.get('recent_count', 0):>8}\n"
                )
        return total

    if endpoints is not None:
        sys.stdout.write("endpoints (top by p95 desc)\n")
        if not endpoints:
            sys.stdout.write("  (no endpoint samples matched the filter)\n")
        else:
            sys.stdout.write(
                f"  {'METHOD':<7} {'PATH':<50} "
                f"{'COUNT':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'MAX':>8}\n"
            )
            for row in endpoints:
                total += 1
                sys.stdout.write(
                    f"  {str(row.get('method') or '-'):<7} "
                    f"{str(row.get('normalized_path') or '-'):<50.50} "
                    f"{row.get('count', 0):>8} "
                    f"{_fmt_num(row.get('p50_ms')):>8} "
                    f"{_fmt_num(row.get('p95_ms')):>8} "
                    f"{_fmt_num(row.get('p99_ms')):>8} "
                    f"{_fmt_num(row.get('max_ms')):>8}\n"
                )

    if tasks is not None:
        if endpoints is not None:
            sys.stdout.write("\n")
        sys.stdout.write("tasks (top by p95 desc)\n")
        if not tasks:
            sys.stdout.write("  (no task samples matched the filter)\n")
        else:
            sys.stdout.write(
                f"  {'TASK':<40} {'STATUS':<8} "
                f"{'COUNT':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'MAX':>8}\n"
            )
            for row in tasks:
                total += 1
                sys.stdout.write(
                    f"  {str(row.get('task_name') or '-'):<40.40} "
                    f"{str(row.get('status') or '-'):<8} "
                    f"{row.get('count', 0):>8} "
                    f"{_fmt_num(row.get('p50_ms')):>8} "
                    f"{_fmt_num(row.get('p95_ms')):>8} "
                    f"{_fmt_num(row.get('p99_ms')):>8} "
                    f"{_fmt_num(row.get('max_ms')):>8}\n"
                )
    return total


def _fmt_num(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{value:.1f}"


def _emit_csv(
    *,
    endpoints: list[dict[str, Any]] | None,
    tasks: list[dict[str, Any]] | None,
    regression: list[dict[str, Any]] | None,
) -> int:
    writer = csv.writer(sys.stdout)
    total = 0

    if regression is not None:
        writer.writerow(_REGRESSION_COLUMNS)
        for row in regression:
            total += 1
            writer.writerow([_csv_cell(row.get(col)) for col in _REGRESSION_COLUMNS])
        return total

    if endpoints is not None:
        writer.writerow(_ENDPOINT_COLUMNS)
        for row in endpoints:
            total += 1
            writer.writerow([_csv_cell(row.get(col)) for col in _ENDPOINT_COLUMNS])

    if tasks is not None:
        writer.writerow(_TASK_COLUMNS)
        for row in tasks:
            total += 1
            writer.writerow([_csv_cell(row.get(col)) for col in _TASK_COLUMNS])

    return total


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _emit_json(
    *,
    endpoints: list[dict[str, Any]] | None,
    tasks: list[dict[str, Any]] | None,
    regression: list[dict[str, Any]] | None,
) -> int:
    total = 0
    for group in (regression, endpoints, tasks):
        if not group:
            continue
        for row in group:
            sys.stdout.write(json.dumps(row, default=str))
            sys.stdout.write("\n")
            total += 1
    return total


def _emit(
    fmt: str,
    *,
    endpoints: list[dict[str, Any]] | None,
    tasks: list[dict[str, Any]] | None,
    regression: list[dict[str, Any]] | None,
) -> int:
    if fmt == "csv":
        return _emit_csv(endpoints=endpoints, tasks=tasks, regression=regression)
    if fmt == "json":
        return _emit_json(endpoints=endpoints, tasks=tasks, regression=regression)
    return _emit_table(endpoints=endpoints, tasks=tasks, regression=regression)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    top = _clamp_top(args.top)
    min_samples = max(0, args.min_samples)

    engine = _get_engine()

    try:
        with engine.connect() as conn:
            if args.regression_hunt:
                rows = _stream_query(conn, _build_regression_query(top))
                regression = [_coerce_regression_row(r) for r in rows]
                endpoints = None
                tasks = None
            else:
                regression = None
                if args.section in ("endpoints", "both"):
                    rows = _stream_query(
                        conn,
                        _build_endpoint_query(args.window, top, min_samples),
                    )
                    endpoints = [_coerce_endpoint_row(r) for r in rows]
                else:
                    endpoints = None

                if args.section in ("tasks", "both"):
                    rows = _stream_query(
                        conn,
                        _build_task_query(args.window, top, min_samples),
                    )
                    tasks = [_coerce_task_row(r) for r in rows]
                else:
                    tasks = None
    except Exception as e:  # noqa: BLE001 — surface any DB/query issue on exit-1
        print(
            f"ERROR: failed to analyze latencies: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    total = _emit(
        args.format,
        endpoints=endpoints,
        tasks=tasks,
        regression=regression,
    )

    if total == 0:
        print(
            "INFO: no latency samples matched the filter.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
