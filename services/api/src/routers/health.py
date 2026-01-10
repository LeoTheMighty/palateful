"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check():
    """Readiness check - can add DB/Redis checks here."""
    return {"status": "ready"}
