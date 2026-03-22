"""Utility for creating user-facing activity feed entries."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from utils.models.user_activity import UserActivity

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def create_activity(
    db: Session,
    *,
    user_id: uuid.UUID,
    activity_type: str,
    title: str,
    subtitle: str | None = None,
    metadata: dict | None = None,
    action_url: str | None = None,
) -> UserActivity:
    """Create a user-facing activity feed entry.

    Args:
        db: SQLAlchemy session.
        user_id: The user who should see this activity.
        activity_type: Category (import_started, partner_action, meal_reminder, etc.)
        title: Primary display text.
        subtitle: Secondary display text.
        metadata: Flexible JSONB payload.
        action_url: Deep link path for tap navigation.
    """
    activity = UserActivity(
        user_id=user_id,
        type=activity_type,
        title=title,
        subtitle=subtitle,
        metadata_json=metadata,
        action_url=action_url,
    )
    db.add(activity)
    db.flush()
    return activity
