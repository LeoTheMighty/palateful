"""Search ingredients endpoint."""


from pydantic import BaseModel
from sqlalchemy import text
from utils.api.endpoint import Endpoint, success


class SearchIngredients(Endpoint):
    """Search ingredients using fuzzy matching."""

    def execute(self, q: str, limit: int = 10):
        """
        Search for ingredients using PostgreSQL fuzzy search.

        Args:
            q: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching ingredients with similarity scores
        """
        # Use PostgreSQL pg_trgm for fuzzy search
        # Falls back to ILIKE if the function doesn't exist
        try:
            result = self.db.execute(
                text("""
                    SELECT id, canonical_name, category,
                           similarity(canonical_name, :query) as similarity
                    FROM ingredients
                    WHERE canonical_name % :query
                       OR canonical_name ILIKE :pattern
                    ORDER BY similarity DESC
                    LIMIT :limit
                """),
                {"query": q, "pattern": f"%{q}%", "limit": limit}
            )
        except Exception:
            # Fallback to simple ILIKE search if pg_trgm not available
            result = self.db.execute(
                text("""
                    SELECT id, canonical_name, category, 1.0 as similarity
                    FROM ingredients
                    WHERE canonical_name ILIKE :pattern
                    ORDER BY canonical_name
                    LIMIT :limit
                """),
                {"pattern": f"%{q}%", "limit": limit}
            )

        items = [
            SearchIngredients.IngredientMatch(
                id=row.id,
                canonical_name=row.canonical_name,
                category=row.category,
                similarity=float(row.similarity)
            )
            for row in result
        ]

        return success(data={"items": items})

    class IngredientMatch(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None
        similarity: float

    class Response(BaseModel):
        items: list["SearchIngredients.IngredientMatch"]
