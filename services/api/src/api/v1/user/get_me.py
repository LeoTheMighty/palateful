"""Get current user endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.invitation import Invitation
from utils.models.user import User


class GetMe(AsyncEndpoint):
    """Get the current authenticated user."""

    async def execute(self):
        """Return the current user's data."""
        user: User = self.user

        # Count pending invitations for badge
        pending_result = await self.db.execute(
            select(func.count(Invitation.id)).where(
                Invitation.to_user_id == user.id,
                Invitation.status == "pending",
                Invitation.archived_at.is_(None),
            )
        )
        pending_count = pending_result.scalar() or 0

        return success(
            data=GetMe.Response(
                id=str(user.id),
                email=user.email,
                name=user.name,
                username=user.username,
                picture=user.picture,
                has_completed_onboarding=user.has_completed_onboarding,
                is_admin=user.is_admin,
                default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
                previous_recipe_book_id=str(user.previous_recipe_book_id) if user.previous_recipe_book_id else None,
                default_shopping_list_id=str(user.default_shopping_list_id) if user.default_shopping_list_id else None,
                previous_shopping_list_id=str(user.previous_shopping_list_id) if user.previous_shopping_list_id else None,
                created_at=user.created_at,
                username_changed_at=user.username_changed_at,
                pending_invitation_count=pending_count,
            )
        )

    class Response(BaseModel):
        id: str
        email: str | None = None
        name: str | None = None
        username: str | None = None
        picture: str | None = None
        has_completed_onboarding: bool
        is_admin: bool = False
        default_recipe_book_id: str | None = None
        previous_recipe_book_id: str | None = None
        default_shopping_list_id: str | None = None
        previous_shopping_list_id: str | None = None
        created_at: datetime
        username_changed_at: datetime | None = None
        pending_invitation_count: int = 0
