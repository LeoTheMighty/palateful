"""Client-latency ingest router (cla-1b).

Single endpoint: `POST /v1/client-latencies`. Auth is optional — the
endpoint accepts anonymous pre-login cold-start events, gated by an
IP rate-limit. See `api/v1/client_latency/ingest.py` for the full
contract.
"""

from api.v1.client_latency import IngestClientLatencies
from dependencies import get_database, get_optional_user
from fastapi import APIRouter, Depends, Request
from utils.models.user import User
from utils.services.database import Database

client_latency_router = APIRouter(
    prefix="/client-latencies", tags=["client-latencies"]
)


@client_latency_router.post("")
async def ingest_client_latencies(
    params: IngestClientLatencies.Params,
    request: Request,
    user: User | None = Depends(get_optional_user),
    database: Database = Depends(get_database),
):
    """Bulk-ingest ≤100 client-side perf samples."""
    return IngestClientLatencies.call(
        params=params,
        request=request,
        user=user,
        database=database,
    )
