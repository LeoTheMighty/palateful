"""GET /v1/units/aliases — return the alias → canonical map for the Flutter client.

riip-4. Powers the Flutter `SessionAliasMapProvider` so `UnitInput` can
coerce typed text on blur using the live alias map. Reads directly from
the DB (single round trip — two cheap selects on small tables) so the
response is always fresh; the in-process normalizer cache is a write-path
optimization, not a content cache.

Cached at the HTTP layer for 24 h via `Cache-Control: max-age=86400`,
set on the FastAPI `Response` in the router. The alias seed only changes
on a redeploy, so clients don't need to revalidate.
"""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.unit import Unit
from utils.models.unit_alias import UnitAlias


class GetUnitAliases(AsyncEndpoint):
    """Return the full alias → canonical map + the canonical token list."""

    async def execute(self):
        alias_result = await self.db.execute(
            select(UnitAlias.alias, UnitAlias.canonical_unit)
        )
        alias_rows = alias_result.all()
        canonical_result = await self.db.execute(select(Unit.name))
        canonical_rows = canonical_result.scalars().all()

        aliases = {alias: canonical for alias, canonical in alias_rows}
        canonical = sorted({name for name in canonical_rows if name})

        return success(
            data=GetUnitAliases.Response(
                aliases=aliases,
                canonical=canonical,
            )
        )

    class Response(BaseModel):
        aliases: dict[str, str]
        canonical: list[str]
