"""Set or update username endpoint."""

import re
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User

# Username validation pattern
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,19}$")

# Reserved usernames that cannot be used
RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "support",
    "help",
    "palateful",
    "system",
    "api",
    "root",
    "user",
    "users",
    "account",
    "settings",
    "profile",
    "mod",
    "moderator",
    "staff",
    "official",
    "team",
    "info",
    "contact",
    "about",
    "terms",
    "privacy",
    "security",
    "null",
    "undefined",
    "test",
    "demo",
}

# Users can only change username once every 30 days
USERNAME_CHANGE_COOLDOWN_DAYS = 30


class SetUsername(Endpoint):
    """Set or update the current user's username."""

    def execute(self, params: "SetUsername.Params"):
        """Set or update username with validation."""
        user: User = self.user
        new_username = params.username.lower().strip()

        # Validate username format
        if not USERNAME_PATTERN.match(new_username):
            raise APIException(
                status_code=400,
                detail="Username must be 3-20 characters, start with a letter, "
                "and contain only lowercase letters, numbers, and underscores",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Check if username is reserved
        if new_username in RESERVED_USERNAMES:
            raise APIException(
                status_code=400,
                detail="This username is reserved and cannot be used",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Check cooldown period (only if user already has a username)
        if user.username and user.username_changed_at:
            cooldown_end = user.username_changed_at + timedelta(
                days=USERNAME_CHANGE_COOLDOWN_DAYS
            )
            now = datetime.now(UTC)
            if now < cooldown_end:
                days_remaining = (cooldown_end - now).days + 1
                raise APIException(
                    status_code=400,
                    detail=f"You can change your username again in {days_remaining} days",
                    code=ErrorCode.RATE_LIMITED,
                )

        # Check if username is already taken (case-insensitive)
        existing_user = self.db.execute(
            select(User).where(User.username == new_username, User.id != user.id)
        ).scalar_one_or_none()

        if existing_user:
            raise APIException(
                status_code=400,
                detail="This username is already taken",
                code=ErrorCode.CONFLICT,
            )

        # Update username
        old_username = user.username
        user.username = new_username
        if old_username is not None:
            # Only update changed_at if this is a change, not initial set
            user.username_changed_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(user)

        return success(
            data=SetUsername.Response(
                success=True,
                username=user.username,
                message="Username set successfully"
                if old_username is None
                else "Username updated successfully",
            )
        )

    class Params(BaseModel):
        """Request parameters."""

        username: str

        @field_validator("username")
        @classmethod
        def validate_username(cls, v: str) -> str:
            v = v.lower().strip()
            if len(v) < 3:
                raise ValueError("Username must be at least 3 characters")
            if len(v) > 20:
                raise ValueError("Username must be at most 20 characters")
            return v

    class Response(BaseModel):
        """Response model."""

        success: bool
        username: str
        message: str
