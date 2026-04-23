"""GET /v1/flags/perf — client-side perf-ingest kill-switch (cla-1c).

Returns `{ingest_enabled, sampling_rate}` sourced from the
`CLIENT_LATENCY_INGEST_ENABLED` / `CLIENT_LATENCY_SAMPLING_RATE` env
vars on the ECS task definition. Operator flips these on the ECS
console to shed client-latency writes without a Flutter rebuild —
see `docs/PERFORMANCE_OPS.md` for the runbook.

Public / unauthenticated. Flutter fetches this on every cold-start
before the first `ClientLatencyIngest.enqueue(...)` call. Rationale
for keeping it unauthed: anonymous pre-login clients also need to
honor the kill-switch (else they'd flood the ingest endpoint during
an emergency), and a fetch failure must NOT require the Auth0
roundtrip to resolve.

Fail-open contract: callers treat any error / timeout / unreachable
response as "defaults on". This endpoint therefore returns a concrete
answer on every call — no 404 / 5xx branches.
"""

from __future__ import annotations

from config import settings
from pydantic import BaseModel, Field
from utils.api.endpoint import Endpoint, success


class GetPerfFlags(Endpoint):
    """Emit the current client-latency kill-switch state."""

    def execute(self):
        return success(
            data=GetPerfFlags.Response(
                ingest_enabled=settings.client_latency_ingest_enabled,
                sampling_rate=settings.client_latency_sampling_rate,
            )
        )

    class Response(BaseModel):
        ingest_enabled: bool = Field(
            description=(
                "Whether the client-latency ingest pipeline is live. "
                "When false, Flutter drops all enqueue-ed events on the "
                "floor — no retry, no disk buffer."
            )
        )
        sampling_rate: float = Field(
            ge=0.0,
            le=1.0,
            description=(
                "Fraction of events to keep before batching. 1.0 = no "
                "sampling (ship everything). Soft lever for volume "
                "shedding without fully disabling the pipeline."
            ),
        )
