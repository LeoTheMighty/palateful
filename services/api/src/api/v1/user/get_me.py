"""Get current user endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.user import User


class GetMe(Endpoint):
    """Get the current authenticated user."""

    def execute(self):
        """Return the current user's data."""
        user: User = self.user

        return success(
            data=GetMe.Response(
                id=str(user.id),
                email=user.email,
                name=user.name,
                username=user.username,
                picture=user.picture,
                has_completed_onboarding=user.has_completed_onboarding,
                default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
                created_at=user.created_at,
                username_changed_at=user.username_changed_at
            )
        )

    class Response(BaseModel):
        id: str
        email: str
        name: str | None = None
        username: str | None = None
        picture: str | None = None
        has_completed_onboarding: bool
        default_recipe_book_id: str | None = None
        created_at: datetime
        username_changed_at: datetime | None = None
