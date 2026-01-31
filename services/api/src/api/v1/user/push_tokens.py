"""Push notification token management endpoints."""

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.user import User


class RegisterPushToken(Endpoint):
    """Register a device push token for notifications."""

    def execute(self, params: "RegisterPushToken.Params"):
        """
        Register a push notification token for the current user's device.

        Called when:
        - App starts and gets FCM token
        - FCM token is refreshed

        Args:
            params: Token registration parameters

        Returns:
            Success with token count
        """
        user: User = self.user

        # Get current tokens (or empty list)
        tokens = user.push_tokens or []

        # Add token if not already present
        if params.token not in tokens:
            tokens.append(params.token)
            user.push_tokens = tokens
            self.database.db.commit()

        return success(
            data=RegisterPushToken.Response(
                registered=True,
                token_count=len(tokens),
            )
        )

    class Params(BaseModel):
        token: str
        device_type: str | None = None  # "ios" | "android"
        device_name: str | None = None

    class Response(BaseModel):
        registered: bool
        token_count: int


class UnregisterPushToken(Endpoint):
    """Unregister a device push token."""

    def execute(self, params: "UnregisterPushToken.Params"):
        """
        Remove a push notification token when user logs out or uninstalls.

        Args:
            params: Token to unregister

        Returns:
            Success with remaining token count
        """
        user: User = self.user

        tokens = user.push_tokens or []

        if params.token in tokens:
            tokens.remove(params.token)
            user.push_tokens = tokens
            self.database.db.commit()

        return success(
            data=UnregisterPushToken.Response(
                unregistered=True,
                token_count=len(tokens),
            )
        )

    class Params(BaseModel):
        token: str

    class Response(BaseModel):
        unregistered: bool
        token_count: int


class UpdateNotificationPreferences(Endpoint):
    """Update user notification preferences."""

    def execute(self, params: "UpdateNotificationPreferences.Params"):
        """
        Update notification preferences for the current user.

        Args:
            params: Updated preferences

        Returns:
            Success with current preferences
        """
        user: User = self.user

        # Get current preferences (or defaults)
        prefs = user.notification_preferences or {
            "push_enabled": True,
            "email_digest": "daily",
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "timezone": "America/Denver",
        }

        # Update provided fields
        if params.push_enabled is not None:
            prefs["push_enabled"] = params.push_enabled
        if params.email_digest is not None:
            prefs["email_digest"] = params.email_digest
        if params.quiet_hours_start is not None:
            prefs["quiet_hours_start"] = params.quiet_hours_start
        if params.quiet_hours_end is not None:
            prefs["quiet_hours_end"] = params.quiet_hours_end
        if params.timezone is not None:
            prefs["timezone"] = params.timezone

        user.notification_preferences = prefs
        self.database.db.commit()

        return success(
            data=UpdateNotificationPreferences.Response(
                push_enabled=prefs.get("push_enabled", True),
                email_digest=prefs.get("email_digest", "daily"),
                quiet_hours_start=prefs.get("quiet_hours_start", "22:00"),
                quiet_hours_end=prefs.get("quiet_hours_end", "08:00"),
                timezone=prefs.get("timezone", "America/Denver"),
            )
        )

    class Params(BaseModel):
        push_enabled: bool | None = None
        email_digest: str | None = None  # "none" | "daily" | "weekly"
        quiet_hours_start: str | None = None  # "HH:MM" format
        quiet_hours_end: str | None = None  # "HH:MM" format
        timezone: str | None = None

    class Response(BaseModel):
        push_enabled: bool
        email_digest: str
        quiet_hours_start: str
        quiet_hours_end: str
        timezone: str


class GetNotificationPreferences(Endpoint):
    """Get user notification preferences."""

    def execute(self):
        """
        Get current notification preferences for the user.

        Returns:
            Current preferences with defaults
        """
        user: User = self.user

        prefs = user.notification_preferences or {}

        return success(
            data=GetNotificationPreferences.Response(
                push_enabled=prefs.get("push_enabled", True),
                email_digest=prefs.get("email_digest", "daily"),
                quiet_hours_start=prefs.get("quiet_hours_start", "22:00"),
                quiet_hours_end=prefs.get("quiet_hours_end", "08:00"),
                timezone=prefs.get("timezone", "America/Denver"),
                token_count=len(user.push_tokens or []),
            )
        )

    class Response(BaseModel):
        push_enabled: bool
        email_digest: str
        quiet_hours_start: str
        quiet_hours_end: str
        timezone: str
        token_count: int
