"""Health check endpoints."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from utils.services.db_probe import ProbeVerdict, cached_verdict_async

logger = logging.getLogger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("")
async def health_check():
    """Liveness + credential validity.

    Deliberately does **not** take a `get_async_database` dependency. A
    pooled connection stays authenticated across an RDS-managed secret
    rotation, so probing one structurally cannot observe the failure this
    endpoint exists to catch (rotation-self-heal FR-2). The probe opens a
    genuinely fresh connection instead; see `utils.services.db_probe`.

    503 **only** on a positively-identified credential failure, which ECS
    turns into a task replacement — the self-heal for a task holding a
    password resolved at start-up. Every other failure returns 200:
    replacing tasks cannot fix a timeout or a DNS blip, and with
    `deployment_minimum_healthy_percent = 0` on both services, doing it
    anyway escalates a blip into an outage.
    """
    try:
        verdict = await cached_verdict_async()
    except Exception:  # noqa: BLE001 - fail-open must be structural
        # Nothing below the probe is supposed to raise, but "supposed to"
        # is not a guarantee, and an escaping exception becomes a 500.
        # The container health check runs `urllib.request.urlopen`, which
        # raises `HTTPError` on ANY non-2xx — so a 500 replaces the task
        # exactly as a 503 does, with no credential failure anywhere.
        # Anything that gets here is by definition unclassified, and
        # unclassified fails open.
        logger.exception("health check: probe raised — failing open")
        verdict = ProbeVerdict.UNKNOWN

    if verdict is ProbeVerdict.AUTH_FAILED:
        logger.error(
            "health check: db credentials invalid — reporting 503 so this "
            "task is replaced and re-resolves its password"
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "db credentials invalid", "db": verdict.name},
        )

    return {"status": "ok", "db": verdict.name}


@health_router.get("/ready")
async def readiness_check():
    """Readiness check - can add DB/Redis checks here."""
    return {"status": "ready"}
