"""Admin endpoint: GET /v1/admin/metrics/tasks.

Mirror of GetEndpointMetrics for Celery task latency. Keyed by
`task_name` instead of `(method, normalized_path)`; surfaces
`failure_rate` (fraction with `status='failure'`) instead of
`error_rate`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import text
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode

_WINDOWS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

_SPARKLINE_BUCKETS = 24

_PERCENTILE_SQL = text(
    """
    SELECT
        task_name,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status = 'failure') AS failures
    FROM task_latencies
    WHERE created_at >= :start_time
    GROUP BY task_name
    ORDER BY p95 DESC NULLS LAST
    """
)

_SPARKLINE_SQL = text(
    """
    SELECT
        task_name,
        LEAST(
            :n_buckets - 1,
            GREATEST(
                0,
                floor(
                    EXTRACT(EPOCH FROM (created_at - :start_time))
                    / :bucket_width_seconds
                )::int
            )
        ) AS bucket_idx,
        AVG(duration_ms)::float AS bucket_mean
    FROM task_latencies
    WHERE created_at >= :start_time
    GROUP BY task_name, bucket_idx
    """
)


class GetTaskMetrics(Endpoint):
    """Aggregate task-latency stats for the admin metrics screen."""

    def execute(self, window: str = "24h"):
        delta = _WINDOWS.get(window)
        if delta is None:
            raise APIException(
                status_code=400,
                detail=f"Invalid window '{window}'. Must be one of {list(_WINDOWS)}.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        now = datetime.now(UTC)
        start_time = now - delta
        bucket_width = delta.total_seconds() / _SPARKLINE_BUCKETS

        percentile_rows = self.db.execute(
            _PERCENTILE_SQL, {"start_time": start_time}
        ).all()

        sparkline_rows = self.db.execute(
            _SPARKLINE_SQL,
            {
                "start_time": start_time,
                "bucket_width_seconds": bucket_width,
                "n_buckets": _SPARKLINE_BUCKETS,
            },
        ).all()

        sparklines: dict[str, list[float]] = {}
        for row in sparkline_rows:
            if row.task_name not in sparklines:
                sparklines[row.task_name] = [0.0] * _SPARKLINE_BUCKETS
            sparklines[row.task_name][int(row.bucket_idx)] = float(
                row.bucket_mean or 0.0
            )

        rows: list[GetTaskMetrics.Row] = []
        for r in percentile_rows:
            total = int(r.total or 0)
            failures = int(r.failures or 0)
            failure_rate = (failures / total) if total else 0.0
            rows.append(
                GetTaskMetrics.Row(
                    task_name=r.task_name,
                    p50_ms=int(r.p50 or 0),
                    p95_ms=int(r.p95 or 0),
                    p99_ms=int(r.p99 or 0),
                    count=total,
                    failure_rate=failure_rate,
                    sparkline=sparklines.get(
                        r.task_name, [0.0] * _SPARKLINE_BUCKETS
                    ),
                )
            )

        return success(
            data=GetTaskMetrics.Response(
                window=window,
                rows=rows,
            )
        )

    class Row(BaseModel):
        task_name: str
        p50_ms: int
        p95_ms: int
        p99_ms: int
        count: int
        failure_rate: float
        sparkline: list[float]

    class Response(BaseModel):
        window: str
        rows: list["GetTaskMetrics.Row"]  # noqa: UP037
