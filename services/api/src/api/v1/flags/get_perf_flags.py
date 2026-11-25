"""GET /v1/flags/perf — client-side perf-ingest kill-switch (cla-1c).

Returns `{ingest_enabled, sampling_rate, shake_report}`. The first two
come from the `CLIENT_LATENCY_INGEST_ENABLED` /
`CLIENT_LATENCY_SAMPLING_RATE` env vars on the ECS task definition and
shed client-latency writes without a Flutter rebuild — see
`docs/PERFORMANCE_OPS.md` for the runbook.

`shake_report` is a PRODUCT flag on a perf-named endpoint (shk101): the
shake-to-report rollout ring, `off` / `admins` / `everyone`, from
`SHAKE_REPORT_RING`. It rides this endpoint because the client already
fetches it at boot and every 5 minutes; a second flags endpoint would
duplicate that fetch, timeout and refresh. The latency flags fail open,
but the ring must not: the client keeps the last ring it received and
assumes `admins` before it has ever received one, so a failed fetch
never widens the rollout. Terraform sets the variable
(`var.shake_report_ring`); a console-set value lasts only until the
next terraform-managed task-definition revision.

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

from config import ShakeReportRing, settings
from pydantic import BaseModel, Field
from utils.api.endpoint import AsyncEndpoint, success


class GetPerfFlags(AsyncEndpoint):
    """Emit the client-latency kill-switch state and the shake ring."""

    async def execute(self):
        return success(
            data=GetPerfFlags.Response(
                ingest_enabled=settings.client_latency_ingest_enabled,
                sampling_rate=settings.client_latency_sampling_rate,
                shake_report=settings.shake_report_ring,
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
        shake_report: ShakeReportRing = Field(
            description=(
                "Shake-to-report rollout ring — a product flag, not a "
                "perf one. `off` admits no one, `admins` only admins, "
                "`everyone` every eligible user. Clients keep the last "
                "value received and assume `admins` before the first."
            ),
        )
