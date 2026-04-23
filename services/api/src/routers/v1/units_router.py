"""Units endpoints router.

aam-21: flipped to `get_async_database` + `get_current_user_async`.
Response headers patched on the awaited result (endpoint returns a
`CustomJSONResponse`, so the 24h public Cache-Control sticks on the
final response object).
"""

from api.v1.units import GetUnitAliases
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

units_router = APIRouter(prefix="/units", tags=["units"])


@units_router.get("/aliases")
async def get_unit_aliases(
    _user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Return the alias → canonical-unit map for the Flutter client.

    Cache-Control: 24h public — the alias seed only changes on redeploy
    so clients can serve from cache without revalidation. The header is
    set on the returned `CustomJSONResponse` directly because the
    endpoint base class returns a Response object (which causes FastAPI
    to ignore the dependency-injected `Response` param).

    Auth-required so the endpoint can't be scraped anonymously.
    """
    result = await GetUnitAliases.call(database=database)
    result.headers["Cache-Control"] = "max-age=86400, public"
    return result
