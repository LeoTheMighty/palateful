"""Cooking log endpoints router."""

from api.v1.cooking_log import ListCookingLogs
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.database import Database

cooking_log_router = APIRouter(tags=["cooking-logs"])


@cooking_log_router.get("/cooking-logs")
async def list_cooking_logs(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List recently cooked recipes for the current user."""
    return ListCookingLogs.call(
        limit=limit,
        user=user,
        database=database,
    )
