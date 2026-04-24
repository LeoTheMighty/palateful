"""Search endpoints router."""

from api.v1.search import UnifiedSearch
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.database import Database

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get("")
def search(
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
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Unified search across recipes and users."""
    return UnifiedSearch.call(
        q=q, limit=limit, scope=scope, user=user, database=database
    )
