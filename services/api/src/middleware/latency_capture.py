"""Request-latency capture middleware.

Measures wall-clock request duration and enqueues one sample per request
into the `BatchedLatencyWriter`. Hard-skips `/health` and `/ready` (too
noisy; drowns the aggregation query) and skips any request whose route
could not be matched (404 / static / unmatched path) — these are not
useful for "slow endpoints" surface.

Path normalization uses FastAPI's `request.scope['route'].path` so
parameterized routes (`/v1/recipes/{recipe_id}`) collapse to their
template, not the raw URL with UUIDs baked in. That is the cardinality
guard that keeps the `normalized_path` column's distinct-value count
bounded.

The hot path never raises: enqueue is non-blocking and failures in the
writer are caught and logged there. The middleware itself wraps the
measurement in a broad try/except as a belt-and-braces.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from utils.services.observability import get_request_writer

logger = logging.getLogger(__name__)

_SKIP_RAW_PATHS = {"/health", "/ready"}


class LatencyCaptureMiddleware(BaseHTTPMiddleware):
    """Enqueue one latency sample per matched FastAPI route."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Hard-skip noisy health checks before starting the clock — those
        # paths would flood the `request_latencies` table.
        raw_path = request.url.path if request.url else ""
        if raw_path in _SKIP_RAW_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            try:
                self._capture(request, response, start)
            except Exception:
                # Capture must never surface an error to the client.
                logger.exception("Latency capture middleware failure")

    @staticmethod
    def _capture(
        request: Request,
        response: Response | None,
        start: float,
    ) -> None:
        """Extract the route template + duration, enqueue one sample."""
        duration_ms = max(int((time.perf_counter() - start) * 1000), 0)

        # Only capture matched routes — unmatched scope["route"] means a
        # 404 / static asset / unhandled path, which is noise for the
        # "slow endpoints" view.
        route = request.scope.get("route") if request.scope else None
        normalized_path = getattr(route, "path", None)
        if not normalized_path:
            return

        status_code = response.status_code if response is not None else 500
        method = (request.method or "")[:8]
        state = request.state
        request_id = (getattr(state, "request_id", "") or "")[:64]
        user = getattr(state, "user", None)
        user_id = getattr(user, "id", None) if user is not None else None

        sample = {
            "method": method,
            "normalized_path": normalized_path[:256],
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "request_id": request_id,
        }

        writer = get_request_writer()
        writer.enqueue(sample)
