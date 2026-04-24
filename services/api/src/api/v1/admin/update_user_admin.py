"""Update user admin status endpoint."""

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User


class UpdateUserAdmin(AsyncEndpoint):
    """Toggle is_admin on a user by ID."""

    async def execute(self, user_id: str, params: "UpdateUserAdmin.Params"):
        """Set is_admin for the target user with safety checks."""
        current_user: User = self.user

        # Find the target user
        target_user = (await self.db.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()

        if not target_user:
            raise APIException(
                status_code=404,
                detail="User not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Safety: prevent removing admin from yourself if you're the last admin
        if (
            str(target_user.id) == str(current_user.id)
            and not params.is_admin
        ):
            admin_count = (await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_admin.is_(True))
            )).scalar() or 0

            if admin_count <= 1:
                raise APIException(
                    status_code=400,
                    detail="Cannot remove admin from the last admin user",
                    code=ErrorCode.VALIDATION_ERROR,
                )

        target_user.is_admin = params.is_admin
        await self.db.commit()
        await self.db.refresh(target_user)

        return success(
            data=UpdateUserAdmin.Response(
                id=str(target_user.id),
                email=target_user.email,
                name=target_user.name,
                username=target_user.username,
                is_admin=target_user.is_admin,
                created_at=(
                    target_user.created_at.isoformat()
                    if target_user.created_at
                    else None
                ),
            )
        )

    class Params(BaseModel):
        """Request parameters."""

        is_admin: bool

    class Response(BaseModel):
        """Response model."""

        id: str
        email: str | None = None
        name: str | None = None
        username: str | None = None
        is_admin: bool
        created_at: str | None = None
