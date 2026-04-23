"""Runtime feature-flag router (cla-1c).

Public endpoints — no auth — because the perf kill-switch must be
reachable by anonymous pre-login clients during an incident.
"""

from api.v1.flags import GetPerfFlags
from fastapi import APIRouter

flags_router = APIRouter(prefix="/flags", tags=["flags"])


@flags_router.get("/perf")
async def get_perf_flags():
    """Client-latency ingest kill-switch + sampling rate (cla-1c)."""
    return GetPerfFlags.call()
