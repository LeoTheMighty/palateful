"""Search endpoints router."""

from api.v1.search import UnifiedSearch
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get("")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max results per category"),
    scope: str | None = Query(
        None,
        description=(
            "Optional comma-separated scope set. `recipes` — no users / no meals "
            "(bugs-cal-2); `recipes,meals` — recipes + Meals + users; `meals` — "
            "Meals only. Unknown / absent values fall back to everything (md-1)."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Unified search across recipes and users."""
    return await UnifiedSearch.call(
        q=q, limit=limit, scope=scope, user=user, database=database
    )
