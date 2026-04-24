"""Update current user profile endpoint."""

from pydantic import BaseModel, field_validator
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User


class UpdateMe(AsyncEndpoint):
    """Update the current user's profile."""

    async def execute(self, params: "UpdateMe.Params"):
        """Update allowed profile fields (name only)."""
        user: User = self.user

        if params.name is not None:
            name = params.name.strip()
            if not name:
                raise APIException(
                    status_code=400,
                    detail="Name cannot be empty",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            user.name = name

        await self.db.commit()
        await self.db.refresh(user)

        return success(
            data=UpdateMe.Response(
                success=True,
                name=user.name,
                message="Profile updated successfully",
            )
        )

    class Params(BaseModel):
        """Request parameters."""

        name: str | None = None

        @field_validator("name")
        @classmethod
        def validate_name(cls, v: str | None) -> str | None:
            if v is not None and len(v.strip()) > 100:
                raise ValueError("Name must be at most 100 characters")
            return v

    class Response(BaseModel):
        """Response model."""

        success: bool
        name: str | None = None
        message: str
