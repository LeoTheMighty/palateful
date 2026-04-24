"""Admin endpoints for client-side perf metrics (cla-10a).

Four GETs under `/v1/admin/metrics/client`, all guarded by `require_admin`:

* `/routes`      — per `(route)` p50/p95/p99 for `type='route_paint'`.
* `/endpoints`   — per `(method, endpoint)` p50/p95/p99 for
                    `type='network_request'`.
* `/jank`        — per `(route)` build-span and raster-span p95 from
                    `type='frame_jank_p95'` events.
* `/sparkline`   — time-bucketed mean for one metric, filtered by
                    type/route/endpoint — drives the detail chart.

All endpoints accept the same filter set: `platform`, `app_version`,
`route`, `window` (1h/24h/7d/30d). The `routes`, `endpoints`, and
`jank` endpoints also sort by p95 desc so the noisiest rows show up
first. Query patterns mirror `get_endpoint_metrics.py` (server-side
percentile aggregation via `percentile_cont`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode

_WINDOWS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_SPARKLINE_BUCKETS = 24


def _resolve_window(window: str) -> timedelta:
    delta = _WINDOWS.get(window)
    if delta is None:
        raise APIException(
            status_code=400,
            detail=f"Invalid window '{window}'. Must be one of {list(_WINDOWS)}.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    return delta


def _base_filters(
    *,
    start_time: datetime,
    platform: str | None,
    app_version: str | None,
    route: str | None,
    type_filter: str,
) -> tuple[str, dict]:
    """Build the WHERE clause + params shared by every route-level
    aggregation. Keeps the SQL assembled via safe parameter binding."""
    clauses = ["created_at >= :start_time", "type = :type_filter"]
    params: dict = {"start_time": start_time, "type_filter": type_filter}
    if platform is not None:
        clauses.append("platform = :platform")
        params["platform"] = platform
    if app_version is not None:
        clauses.append("app_version = :app_version")
        params["app_version"] = app_version
    if route is not None:
        clauses.append("route = :route")
        params["route"] = route
    return " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/routes
# ---------------------------------------------------------------------------


class GetClientRouteMetrics(AsyncEndpoint):
    """Per-route p50/p95/p99 for client route_paint events."""

    async def execute(
        self,
        window: str = "24h",
        platform: str | None = None,
        app_version: str | None = None,
        route: str | None = None,
    ):
        delta = _resolve_window(window)
        now = datetime.now(UTC)
        start_time = now - delta

        where, params = _base_filters(
            start_time=start_time,
            platform=platform,
            app_version=app_version,
            route=route,
            type_filter="route_paint",
        )
        percentile_sql = text(
            f"""
            SELECT
                route,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
                COUNT(*) AS total
            FROM client_latencies
            WHERE {where} AND route IS NOT NULL
            GROUP BY route
            ORDER BY p95 DESC NULLS LAST
            """
        )

        rows = (await self.db.execute(percentile_sql, params)).all()
        return success(
            data=GetClientRouteMetrics.Response(
                window=window,
                rows=[
                    GetClientRouteMetrics.Row(
                        route=r.route,
                        p50_ms=int(r.p50 or 0),
                        p95_ms=int(r.p95 or 0),
                        p99_ms=int(r.p99 or 0),
                        count=int(r.total or 0),
                    )
                    for r in rows
                ],
            )
        )

    class Row(BaseModel):
        route: str
        p50_ms: int
        p95_ms: int
        p99_ms: int
        count: int

    class Response(BaseModel):
        window: str
        rows: list["GetClientRouteMetrics.Row"]  # noqa: UP037


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/endpoints
# ---------------------------------------------------------------------------


class GetClientEndpointMetrics(AsyncEndpoint):
    """Per-endpoint client-observed network latency.

    Groups by (method, endpoint); method comes from the
    `metric_name` column per cla-6's emitter contract. Rows without
    an endpoint are dropped — they'd be noise (WebSocket frames,
    redirects, etc.).
    """

    async def execute(
        self,
        window: str = "24h",
        platform: str | None = None,
        app_version: str | None = None,
        route: str | None = None,
    ):
        delta = _resolve_window(window)
        now = datetime.now(UTC)
        start_time = now - delta

        where, params = _base_filters(
            start_time=start_time,
            platform=platform,
            app_version=app_version,
            route=route,
            type_filter="network_request",
        )
        percentile_sql = text(
            f"""
            SELECT
                metric_name AS method,
                endpoint,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
                COUNT(*) AS total
            FROM client_latencies
            WHERE {where} AND endpoint IS NOT NULL
            GROUP BY metric_name, endpoint
            ORDER BY p95 DESC NULLS LAST
            """
        )

        rows = (await self.db.execute(percentile_sql, params)).all()
        return success(
            data=GetClientEndpointMetrics.Response(
                window=window,
                rows=[
                    GetClientEndpointMetrics.Row(
                        method=r.method or "",
                        endpoint=r.endpoint,
                        p50_ms=int(r.p50 or 0),
                        p95_ms=int(r.p95 or 0),
                        p99_ms=int(r.p99 or 0),
                        count=int(r.total or 0),
                    )
                    for r in rows
                ],
            )
        )

    class Row(BaseModel):
        method: str
        endpoint: str
        p50_ms: int
        p95_ms: int
        p99_ms: int
        count: int

    class Response(BaseModel):
        window: str
        rows: list["GetClientEndpointMetrics.Row"]  # noqa: UP037


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/jank
# ---------------------------------------------------------------------------


class GetClientJankMetrics(AsyncEndpoint):
    """Per-route build-span + raster-span p95 from frame_jank_p95 events.

    Each `frame_jank_p95` event already carries the window's p95 for
    one minute (emitted client-side). We compute the server-side p95
    of those per-minute p95s — i.e. "typical worst minute" — which is
    what the operator wants for "is jank worse this week?"
    """

    async def execute(
        self,
        window: str = "24h",
        platform: str | None = None,
        app_version: str | None = None,
        route: str | None = None,
    ):
        delta = _resolve_window(window)
        now = datetime.now(UTC)
        start_time = now - delta

        where, params = _base_filters(
            start_time=start_time,
            platform=platform,
            app_version=app_version,
            route=route,
            type_filter="frame_jank_p95",
        )
        # duration_ms already carries build_p95; raster_p95 lives in
        # extra['raster_p95_ms'].
        percentile_sql = text(
            f"""
            SELECT
                route,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS build_p95,
                percentile_cont(0.95) WITHIN GROUP (
                    ORDER BY (extra ->> 'raster_p95_ms')::int
                ) AS raster_p95,
                COUNT(*) AS total
            FROM client_latencies
            WHERE {where} AND route IS NOT NULL
            GROUP BY route
            ORDER BY build_p95 DESC NULLS LAST
            """
        )

        rows = (await self.db.execute(percentile_sql, params)).all()
        return success(
            data=GetClientJankMetrics.Response(
                window=window,
                rows=[
                    GetClientJankMetrics.Row(
                        route=r.route,
                        build_p95_ms=int(r.build_p95 or 0),
                        raster_p95_ms=int(r.raster_p95 or 0),
                        count=int(r.total or 0),
                    )
                    for r in rows
                ],
            )
        )

    class Row(BaseModel):
        route: str
        build_p95_ms: int
        raster_p95_ms: int
        count: int

    class Response(BaseModel):
        window: str
        rows: list["GetClientJankMetrics.Row"]  # noqa: UP037


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/sparkline
# ---------------------------------------------------------------------------


SparklineMetric = Literal[
    "route_paint",
    "network_request",
    "frame_jank_p95",
    "app_start",
]


class GetClientSparkline(AsyncEndpoint):
    """Time-bucketed mean duration for one metric — drives the chart.

    `metric` selects which event type. `route`/`endpoint` narrow the
    scope; at most one of the two should be set per call.
    """

    async def execute(
        self,
        metric: str,
        window: str = "24h",
        platform: str | None = None,
        app_version: str | None = None,
        route: str | None = None,
        endpoint: str | None = None,
    ):
        if metric not in (
            "route_paint",
            "network_request",
            "frame_jank_p95",
            "app_start",
        ):
            raise APIException(
                status_code=400,
                detail=f"Invalid metric '{metric}'.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        delta = _resolve_window(window)
        now = datetime.now(UTC)
        start_time = now - delta
        bucket_width = delta.total_seconds() / _SPARKLINE_BUCKETS

        clauses = ["created_at >= :start_time", "type = :metric"]
        params: dict = {
            "start_time": start_time,
            "metric": metric,
            "bucket_width_seconds": bucket_width,
            "n_buckets": _SPARKLINE_BUCKETS,
        }
        if platform is not None:
            clauses.append("platform = :platform")
            params["platform"] = platform
        if app_version is not None:
            clauses.append("app_version = :app_version")
            params["app_version"] = app_version
        if route is not None:
            clauses.append("route = :route")
            params["route"] = route
        if endpoint is not None:
            clauses.append("endpoint = :endpoint")
            params["endpoint"] = endpoint
        where = " AND ".join(clauses)
        sql = text(
            f"""
            SELECT
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
            FROM client_latencies
            WHERE {where}
            GROUP BY bucket_idx
            ORDER BY bucket_idx
            """
        )

        rows = (await self.db.execute(sql, params)).all()
        buckets = [0.0] * _SPARKLINE_BUCKETS
        for r in rows:
            buckets[int(r.bucket_idx)] = float(r.bucket_mean or 0.0)

        return success(
            data=GetClientSparkline.Response(
                metric=metric,
                window=window,
                bucket_seconds=int(bucket_width),
                buckets=buckets,
            )
        )

    class Response(BaseModel):
        metric: str
        window: str
        bucket_seconds: int
        buckets: list[float]
