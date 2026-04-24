"""List all users endpoint."""

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.user import User


class ListUsers(AsyncEndpoint):
    """List all users ordered by created_at desc."""

    async def execute(self, limit: int = 50, offset: int = 0):
        """Query users table with pagination."""
        # Get total count
        total = (await self.db.execute(select(func.count()).select_from(User))).scalar() or 0

        # Get paginated results
        results = (
            (await self.db.execute(
                select(User)
                .order_by(User.created_at.desc())
                .limit(min(limit, 200))
                .offset(offset)
            ))
            .scalars()
            .all()
        )

        users = [
            ListUsers.UserItem(
                id=str(u.id),
                email=u.email,
                name=u.name,
                username=u.username,
                is_admin=u.is_admin,
                created_at=u.created_at.isoformat() if u.created_at else None,
            )
            for u in results
        ]

        return success(
            data=ListUsers.Response(
                users=users,
                total=total,
            )
        )

    class UserItem(BaseModel):
        """A single user entry."""

        id: str
        email: str | None = None
        name: str | None = None
        username: str | None = None
        is_admin: bool
        created_at: str | None = None

    class Response(BaseModel):
        """Response model."""

        users: list["ListUsers.UserItem"]
        total: int
