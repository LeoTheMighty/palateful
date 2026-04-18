"""Admin endpoint: GET /v1/admin/metrics/endpoints.

Returns percentile-aggregated request latency per (method, normalized_path)
over a user-selected window (1h / 24h / 7d), sorted by p95 desc. Each row
carries a 24-bucket sparkline of mean latency so the operator can eyeball
the shape of the degradation without drilling in further.

Query plan (captured in tests): two round-trips — one `percentile_cont` +
`count` aggregation, one `generate_series`-bucketed mean aggregation.
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
        method,
        normalized_path,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status_code >= 500) AS errors
    FROM request_latencies
    WHERE created_at >= :start_time
    GROUP BY method, normalized_path
    ORDER BY p95 DESC NULLS LAST
    """
)

_SPARKLINE_SQL = text(
    """
    SELECT
        method,
        normalized_path,
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
    FROM request_latencies
    WHERE created_at >= :start_time
    GROUP BY method, normalized_path, bucket_idx
    """
)


class GetEndpointMetrics(Endpoint):
    """Aggregate endpoint-latency stats for the admin metrics screen."""

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

        # Merge: key = (method, normalized_path); value = 24-bucket list.
        sparklines: dict[tuple[str, str], list[float]] = {}
        for row in sparkline_rows:
            key = (row.method, row.normalized_path)
            if key not in sparklines:
                sparklines[key] = [0.0] * _SPARKLINE_BUCKETS
            sparklines[key][int(row.bucket_idx)] = float(row.bucket_mean or 0.0)

        rows: list[GetEndpointMetrics.Row] = []
        for r in percentile_rows:
            total = int(r.total or 0)
            errors = int(r.errors or 0)
            error_rate = (errors / total) if total else 0.0
            key = (r.method, r.normalized_path)
            rows.append(
                GetEndpointMetrics.Row(
                    method=r.method,
                    normalized_path=r.normalized_path,
                    p50_ms=int(r.p50 or 0),
                    p95_ms=int(r.p95 or 0),
                    p99_ms=int(r.p99 or 0),
                    count=total,
                    error_rate=error_rate,
                    sparkline=sparklines.get(key, [0.0] * _SPARKLINE_BUCKETS),
                )
            )

        return success(
            data=GetEndpointMetrics.Response(
                window=window,
                rows=rows,
            )
        )

    class Row(BaseModel):
        method: str
        normalized_path: str
        p50_ms: int
        p95_ms: int
        p99_ms: int
        count: int
        error_rate: float
        sparkline: list[float]

    class Response(BaseModel):
        window: str
        rows: list["GetEndpointMetrics.Row"]  # noqa: UP037
