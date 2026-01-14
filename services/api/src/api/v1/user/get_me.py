"""Get current user endpoint."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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
                picture=user.picture,
                has_completed_onboarding=user.has_completed_onboarding,
                default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
                created_at=user.created_at
            )
        )

    class Response(BaseModel):
        id: str
        email: str
        name: Optional[str] = None
        picture: Optional[str] = None
        has_completed_onboarding: bool
        default_recipe_book_id: Optional[str] = None
        created_at: datetime
