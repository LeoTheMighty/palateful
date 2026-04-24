"""Utility for creating user-facing activity feed entries."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from utils.models.user_activity import UserActivity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
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


async def create_activity_async(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    activity_type: str,
    title: str,
    subtitle: str | None = None,
    metadata: dict | None = None,
    action_url: str | None = None,
) -> UserActivity:
    """Async twin of `create_activity` for callers on an `AsyncSession`.

    aam-16: mirrors the sync function method-for-method (same kwargs,
    same return type). Exists so async-converted endpoints can create
    activity rows without reaching for the sync Session. Sync callers
    (worker tasks, not-yet-converted domains) continue to use
    `create_activity` until their domain flips to async.
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
    await db.flush()
    return activity
