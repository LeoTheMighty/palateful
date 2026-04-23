"""Runtime feature-flag router (cla-1c).

Public endpoints — no auth — because the perf kill-switch must be
reachable by anonymous pre-login clients during an incident.

aam-21: converted to `AsyncEndpoint`; the handler is stateless (pure
settings read) so there's no DB dep to swap — the `await` wrap is
cosmetic but keeps the epic-wide invariant (every handler on the async
engine) intact.
"""

from api.v1.flags import GetPerfFlags
from fastapi import APIRouter

flags_router = APIRouter(prefix="/flags", tags=["flags"])


@flags_router.get("/perf")
async def get_perf_flags():
    """Client-latency ingest kill-switch + sampling rate (cla-1c)."""
    return await GetPerfFlags.call()
