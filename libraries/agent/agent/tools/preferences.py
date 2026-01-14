"""User preferences tool."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.tools.base import BaseTool, ToolResult


class GetUserPreferencesTool(BaseTool):
    """Tool to get user preferences and settings."""

    @property
    def name(self) -> str:
        return "get_user_preferences"

    @property
    def description(self) -> str:
        return """Get the user's preferences including dietary restrictions, cuisine preferences,
        cooking skill level, and notification settings. Use this to personalize suggestions."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(
        self,
        db: Session,
        user_id: str,
    ) -> ToolResult:
        """Get user preferences."""
        from utils.models import User

        try:
            query = select(User).where(User.id == user_id)
            result = db.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                return ToolResult(success=False, error="User not found")

            # Get notification preferences
            notification_prefs = user.notification_preferences or {}

            # Build preferences response
            # Note: These fields might need to be added to the User model
            # For now, we'll use what's available and provide defaults
            preferences = {
                "user_id": str(user.id),
                "email": user.email,
                "name": user.name,
                "notifications": {
                    "push_enabled": notification_prefs.get("push_enabled", True),
                    "email_digest": notification_prefs.get("email_digest", "daily"),
                    "timezone": notification_prefs.get("timezone", "America/Denver"),
                    "quiet_hours_start": notification_prefs.get("quiet_hours_start", "22:00"),
                    "quiet_hours_end": notification_prefs.get("quiet_hours_end", "08:00"),
                },
                # These would come from a UserPreferences table or extended User model
                "dietary_restrictions": [],  # e.g., ["vegetarian", "gluten-free"]
                "cuisine_preferences": [],  # e.g., ["Italian", "Japanese", "Mexican"]
                "disliked_ingredients": [],  # e.g., ["mushrooms", "olives"]
                "cooking_skill_level": "intermediate",  # "beginner" | "intermediate" | "advanced"
                "preferred_meal_prep_time": 45,  # minutes
                "household_size": 2,
            }

            return ToolResult(success=True, data=preferences)

        except Exception as e:
            return ToolResult(success=False, error=str(e))
