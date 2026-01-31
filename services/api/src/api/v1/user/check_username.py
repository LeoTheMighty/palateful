"""Check username availability endpoint."""

import re

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import Endpoint, success
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


class CheckUsername(Endpoint):
    """Check if a username is available."""

    def execute(self, username: str):
        """Check username availability and validity."""
        username = username.lower().strip()

        # Remove @ prefix if present
        if username.startswith("@"):
            username = username[1:]

        # Validate format
        if not USERNAME_PATTERN.match(username):
            return success(
                data=CheckUsername.Response(
                    available=False,
                    username=username,
                    reason="invalid_format",
                    message="Username must be 3-20 characters, start with a letter, "
                    "and contain only lowercase letters, numbers, and underscores",
                )
            )

        # Check if reserved
        if username in RESERVED_USERNAMES:
            return success(
                data=CheckUsername.Response(
                    available=False,
                    username=username,
                    reason="reserved",
                    message="This username is reserved",
                )
            )

        # Check if taken
        existing_user = self.db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if existing_user:
            return success(
                data=CheckUsername.Response(
                    available=False,
                    username=username,
                    reason="taken",
                    message="This username is already taken",
                )
            )

        return success(
            data=CheckUsername.Response(
                available=True,
                username=username,
                reason=None,
                message="Username is available",
            )
        )

    class Response(BaseModel):
        """Response model."""

        available: bool
        username: str
        reason: str | None = None
        message: str
