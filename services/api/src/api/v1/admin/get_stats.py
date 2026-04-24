"""Get dashboard stats endpoint."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select, text
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.error_log import ErrorLog
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.user import User
from utils.models.user_feedback import UserFeedback

# Top-level p95 + slowest-endpoint over the last 24 hours. Used for the
# admin dashboard header strip added in obs-latency-3.
_OVERALL_P95_SQL = text(
    """
    SELECT
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::int AS p95_ms
    FROM request_latencies
    WHERE created_at >= :start_time
    """
)

_SLOWEST_ENDPOINT_SQL = text(
    """
    SELECT
        method,
        normalized_path,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::int AS p95_ms
    FROM request_latencies
    WHERE created_at >= :start_time
    GROUP BY method, normalized_path
    ORDER BY p95_ms DESC NULLS LAST
    LIMIT 1
    """
)


class GetStats(AsyncEndpoint):
    """Return aggregate dashboard statistics."""

    async def execute(self):
        """Compute and return aggregate counts."""
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        seven_days_ago = now - timedelta(days=7)

        total_users = (
            (await self.db.execute(select(func.count()).select_from(User))).scalar() or 0
        )

        total_recipes = (
            (await self.db.execute(select(func.count()).select_from(Recipe))).scalar() or 0
        )

        total_recipe_books = (
            (await self.db.execute(select(func.count()).select_from(RecipeBook))).scalar() or 0
        )

        errors_24h = (
            (await self.db.execute(
                select(func.count())
                .select_from(ErrorLog)
                .where(ErrorLog.created_at >= twenty_four_hours_ago)
            )).scalar()
            or 0
        )

        active_users_7d = (
            (await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.updated_at >= seven_days_ago)
            )).scalar()
            or 0
        )

        unread_feedback = (
            (await self.db.execute(
                select(func.count())
                .select_from(UserFeedback)
                .where(UserFeedback.status == "unread")
            )).scalar()
            or 0
        )

        overall_p95_ms = (await self.db.execute(
            _OVERALL_P95_SQL, {"start_time": twenty_four_hours_ago}
        )).scalar()
        overall_p95_ms = int(overall_p95_ms) if overall_p95_ms is not None else None

        slowest_rows = (await self.db.execute(
            _SLOWEST_ENDPOINT_SQL, {"start_time": twenty_four_hours_ago}
        )).all()
        slowest_endpoint: GetStats.SlowestEndpoint | None = None
        if slowest_rows and slowest_rows[0].p95_ms is not None:
            slowest_row = slowest_rows[0]
            slowest_endpoint = GetStats.SlowestEndpoint(
                method=slowest_row.method,
                normalized_path=slowest_row.normalized_path,
                p95_ms=int(slowest_row.p95_ms),
            )

        return success(
            data=GetStats.Response(
                total_users=total_users,
                total_recipes=total_recipes,
                total_recipe_books=total_recipe_books,
                errors_24h=errors_24h,
                active_users_7d=active_users_7d,
                unread_feedback=unread_feedback,
                overall_p95_ms=overall_p95_ms,
                slowest_endpoint=slowest_endpoint,
            )
        )

    class SlowestEndpoint(BaseModel):
        """The single slowest endpoint over the 24 h window."""

        method: str
        normalized_path: str
        p95_ms: int

    class Response(BaseModel):
        """Response model."""

        total_users: int
        total_recipes: int
        total_recipe_books: int
        errors_24h: int
        active_users_7d: int
        unread_feedback: int
        overall_p95_ms: int | None = None
        slowest_endpoint: "GetStats.SlowestEndpoint | None" = None
