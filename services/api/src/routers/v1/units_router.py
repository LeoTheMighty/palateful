"""Units endpoints router."""

from api.v1.units import GetUnitAliases
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

units_router = APIRouter(prefix="/units", tags=["units"])


@units_router.get("/aliases")
async def get_unit_aliases(
    _user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Return the alias → canonical-unit map for the Flutter client.

    Cache-Control: 24h public — the alias seed only changes on redeploy
    so clients can serve from cache without revalidation. The header is
    set on the returned `CustomJSONResponse` directly because the
    endpoint base class returns a Response object (which causes FastAPI
    to ignore the dependency-injected `Response` param).

    Auth-required so the endpoint can't be scraped anonymously.
    """
    result = GetUnitAliases.call(database=database)
    result.headers["Cache-Control"] = "max-age=86400, public"
    return result
