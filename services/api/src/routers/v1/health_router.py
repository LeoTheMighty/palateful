"""Health check endpoints."""

import logging

from dependencies import get_async_database
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from utils.services.async_database import AsyncDatabase

logger = logging.getLogger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("")
async def health_check(
    database: AsyncDatabase = Depends(get_async_database),
):
    # DB probe so a task with stale creds (e.g. post RDS-managed secret
    # rotation, where ECS env vars were resolved at task-start) fails its
    # container health check and gets replaced — instead of staying
    # HEALTHY while every real request 5xx's.
    try:
        await database.db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("health check db probe failed: %s", exc)
        raise HTTPException(status_code=503, detail="db unavailable") from exc
    return {"status": "ok"}


@health_router.get("/ready")
async def readiness_check():
    """Readiness check - can add DB/Redis checks here."""
    return {"status": "ready"}
