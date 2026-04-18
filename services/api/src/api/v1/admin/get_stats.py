"""Get dashboard stats endpoint."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import Endpoint, success
from utils.models.error_log import ErrorLog
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.user import User
from utils.models.user_feedback import UserFeedback


class GetStats(Endpoint):
    """Return aggregate dashboard statistics."""

    def execute(self):
        """Compute and return aggregate counts."""
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        seven_days_ago = now - timedelta(days=7)

        total_users = (
            self.db.execute(select(func.count()).select_from(User)).scalar() or 0
        )

        total_recipes = (
            self.db.execute(select(func.count()).select_from(Recipe)).scalar() or 0
        )

        total_recipe_books = (
            self.db.execute(select(func.count()).select_from(RecipeBook)).scalar() or 0
        )

        errors_24h = (
            self.db.execute(
                select(func.count())
                .select_from(ErrorLog)
                .where(ErrorLog.created_at >= twenty_four_hours_ago)
            ).scalar()
            or 0
        )

        active_users_7d = (
            self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.updated_at >= seven_days_ago)
            ).scalar()
            or 0
        )

        unread_feedback = (
            self.db.execute(
                select(func.count())
                .select_from(UserFeedback)
                .where(UserFeedback.status == "unread")
            ).scalar()
            or 0
        )

        return success(
            data=GetStats.Response(
                total_users=total_users,
                total_recipes=total_recipes,
                total_recipe_books=total_recipe_books,
                errors_24h=errors_24h,
                active_users_7d=active_users_7d,
                unread_feedback=unread_feedback,
            )
        )

    class Response(BaseModel):
        """Response model."""

        total_users: int
        total_recipes: int
        total_recipe_books: int
        errors_24h: int
        active_users_7d: int
        unread_feedback: int
