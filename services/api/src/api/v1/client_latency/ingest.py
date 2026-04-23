"""POST /v1/client-latencies — batched ingest for client-side perf samples.

Writes rows to `client_latencies` (cla-1a). Accepts up to 100 events per
request; beyond that returns 413 so the Flutter batcher
(`app/lib/core/services/client_latency_ingest.dart`, cla-3) never
silently drops excess samples — they come back as "slow down" signals.

Auth:
- JWT present → `user_id` derived from claims (any user_id the client
  sent in the body is ignored).
- JWT absent → `user_id` persists as NULL and an in-memory IP rate-limit
  (10 events per IP per rolling minute) applies. Over-limit calls return
  429 with a `retry_after_s` hint. The rate-limit is event-weighted, not
  request-weighted — a single batch of 10 events counts as 10.

Validation:
- `type` + `platform` are whitelisted against `CLIENT_LATENCY_TYPES` /
  `CLIENT_LATENCY_PLATFORMS` (Pydantic Literal) so the DB CHECK
  constraint never fires under normal use.
- `route` (when present) is run through
  `utils.route_redaction.is_route_redacted`; any event with a raw UUID
  or long-numeric segment returns 422 for the whole batch. Defense in
  depth vs the client-side redaction in cla-4.
- `duration_ms` is clamped to `[0, 10 minutes]` — negative values or
  silly-large timers are rejected at the Pydantic layer.

Insert:
- Synchronous bulk insert via `Session.bulk_insert_mappings`. Load math
  in the epic (125k rows/day, p95 < 100 ms) is comfortably inside single
  round-trip bounds.

Response: `{accepted: int}` — number of rows actually inserted.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Literal

from api.v1.client_latency.route_redaction import is_route_redacted
from pydantic import BaseModel, ConfigDict, Field, field_validator
from utils.api.endpoint import Endpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.client_latency import ClientLatency

# Literal aliases — kept in sync with the model constants via
# `test_client_latency_ingest.py::test_literal_enums_match_model_constants`.
ClientLatencyType = Literal[
    "app_start",
    "route_paint",
    "network_request",
    "frame_jank_p95",
    "metrickit_daily",
    "jankstats_daily",
    "web_navigation",
    "first_paint",
    "first_contentful_paint",
]
ClientLatencyPlatform = Literal["ios", "android", "web"]

logger = logging.getLogger(__name__)

# Hard cap per request — anything beyond returns 413.
MAX_EVENTS_PER_REQUEST = 100

# Anonymous rate-limit: 10 events per rolling minute per IP.
_ANON_RATE_LIMIT_MAX_EVENTS = 10
_ANON_RATE_LIMIT_WINDOW_S = 60
_anon_rate_events: dict[str, list[float]] = {}


def _anon_rate_limit_check(
    client_ip: str, new_event_count: int
) -> tuple[bool, int]:
    """Return (ok, retry_after_s) for an anonymous caller.

    Counts events, not requests — a 10-event batch consumes the whole
    window in one call. Returns (False, seconds-until-unblock) when
    accepting this batch would push the rolling-60s total over the cap.
    """
    if new_event_count <= 0:
        return True, 0

    now = time.monotonic()
    cutoff = now - _ANON_RATE_LIMIT_WINDOW_S
    times = _anon_rate_events.setdefault(client_ip, [])
    times[:] = [t for t in times if t > cutoff]

    if len(times) + new_event_count > _ANON_RATE_LIMIT_MAX_EVENTS:
        # When the window is empty (first call with a single oversized
        # batch) `times[0]` would IndexError — fall back to the full
        # window length so the client has a concrete retry hint.
        oldest = times[0] if times else now
        retry_after = int(oldest + _ANON_RATE_LIMIT_WINDOW_S - now) + 1
        return False, max(retry_after, 1)

    times.extend([now] * new_event_count)
    return True, 0


def _reset_anon_rate_limit_for_test() -> None:
    """Test-only hook — drops all anonymous rate-limit state."""
    _anon_rate_events.clear()


def _extract_client_ip(request) -> str:
    """Best-effort client-IP extraction.

    In front of ALB/CloudFront we get `X-Forwarded-For: real, p1, p2, ...`
    — the left-most entry is the original client. When the header isn't
    present (direct connection during tests) we fall back to
    `request.client.host`. Defaults to `"unknown"` so the rate-limit
    bucket exists rather than letting an anonymous caller slip the
    guard by spoofing an empty header.
    """
    if request is None:
        return "unknown"
    headers = getattr(request, "headers", {}) or {}
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host or "unknown"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ClientLatencyEvent(BaseModel):
    """One client-side perf sample.

    `extra` is free-form jsonb — MetricKit / JankStats / Navigation
    Timing all dump raw payloads here. `user_id` is deliberately absent
    from this schema: the server derives it from the JWT and ignores
    any client-supplied value.
    """

    model_config = ConfigDict(extra="forbid")

    type: ClientLatencyType
    platform: ClientLatencyPlatform
    app_version: str = Field(min_length=1, max_length=32)
    duration_ms: int = Field(ge=0, le=10 * 60 * 1000)  # 0..10 minutes

    route: str | None = Field(default=None, max_length=256)
    endpoint: str | None = Field(default=None, max_length=256)
    metric_name: str | None = Field(default=None, max_length=64)
    device_class: str | None = Field(default=None, max_length=64)
    extra: dict = Field(default_factory=dict)

    @field_validator("route", "endpoint", "metric_name", "device_class", mode="before")
    @classmethod
    def _empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class IngestClientLatencies(Endpoint):
    """Bulk-ingest client-emitted latency samples."""

    def execute(self, params: IngestClientLatencies.Params):
        events = params.events

        # Over-cap → 413. Must reject BEFORE rate-limit so a client
        # can't blow their quota by sending oversized batches.
        if len(events) > MAX_EVENTS_PER_REQUEST:
            return failure(
                status=413,
                error_code=ErrorCode.VALIDATION_ERROR.value,
                error_message=(
                    f"Batch exceeds {MAX_EVENTS_PER_REQUEST} events "
                    f"(got {len(events)})."
                ),
                data={"max_events": MAX_EVENTS_PER_REQUEST},
            )

        # Server-side redaction guard. Defense in depth — the client
        # should redact, but we reject any event whose route still
        # carries a raw UUID or long-numeric id.
        for idx, ev in enumerate(events):
            if not is_route_redacted(ev.route):
                return failure(
                    status=422,
                    error_code=ErrorCode.VALIDATION_ERROR.value,
                    error_message=(
                        f"event[{idx}].route contains an un-redacted "
                        f"identifier"
                    ),
                    data={"index": idx, "route": ev.route},
                )

        user_id: uuid.UUID | None = None
        if self.user is not None:
            user_id = getattr(self.user, "id", None)
        else:
            # Anonymous — apply IP rate-limit (event-weighted).
            client_ip = _extract_client_ip(self.request)
            allowed, retry_after = _anon_rate_limit_check(
                client_ip, len(events)
            )
            if not allowed:
                logger.info(
                    "client_latencies: anon rate-limited ip=%s retry_after_s=%d",
                    client_ip, retry_after,
                )
                return failure(
                    status=429,
                    error_code=ErrorCode.RATE_LIMITED.value,
                    error_message=(
                        "Anonymous ingest rate-limit exceeded "
                        f"({_ANON_RATE_LIMIT_MAX_EVENTS} events/min)."
                    ),
                    data={"retry_after_s": retry_after},
                )

        # Empty batch is a no-op success — client probes / warm-ups
        # shouldn't cost a 4xx.
        if not events:
            return success(
                data=IngestClientLatencies.Response(accepted=0)
            )

        rows = [
            {
                "type": ev.type,
                "platform": ev.platform,
                "app_version": ev.app_version,
                "route": ev.route,
                "endpoint": ev.endpoint,
                "metric_name": ev.metric_name,
                "device_class": ev.device_class,
                "duration_ms": ev.duration_ms,
                "user_id": user_id,
                "extra": ev.extra or {},
            }
            for ev in events
        ]

        self.db.bulk_insert_mappings(ClientLatency, rows)
        self.db.commit()

        return success(
            data=IngestClientLatencies.Response(accepted=len(rows))
        )

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        events: list[ClientLatencyEvent]

    class Response(BaseModel):
        accepted: int
