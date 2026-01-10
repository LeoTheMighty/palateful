"""Health check endpoints."""

from fastapi import APIRouter

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("")
async def health_check():
    """Basic health check."""
    return {"status": "ok"}


@health_router.get("/ready")
async def readiness_check():
    """Readiness check - can add DB/Redis checks here."""
    return {"status": "ready"}
