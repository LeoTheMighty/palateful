"""Unread activity count endpoint — structured payload for the bell badge.

The bell badge = `notifications + imports_actionable`. The two count
queries execute back-to-back on the same async SQLAlchemy session
(no `asyncio.gather`) — single-request session + shared pool make
parallel gather false economy here. Both counts are cheap enough that
dispatching them serially beats paying two session-acquisition costs.

The `count` field is a backward-compat wrapper (= sum of the other
two). It keeps pinned old clients rendering the bell during the abi-1
→ abi-3 rollout window. Remove after `epic-activity-full-history` ships.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.import_item import ACTIONABLE_IMPORT_STATUSES, ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User
from utils.models.user_activity import NOTIFICATION_TAB_TYPES, UserActivity

_NOTIFICATION_RETENTION_DAYS = 30


class UnreadCount(AsyncEndpoint):
    """Get unread activity count for badge display."""

    async def execute(self):
        user: User = self.user
        cutoff = datetime.now(UTC) - timedelta(days=_NOTIFICATION_RETENTION_DAYS)

        notifications_result = await self.db.execute(
            select(func.count())
            .select_from(UserActivity)
            .where(
                UserActivity.user_id == user.id,
                UserActivity.read.is_(False),
                UserActivity.archived_at.is_(None),
                UserActivity.type.in_(NOTIFICATION_TAB_TYPES),
                UserActivity.created_at >= cutoff,
            )
        )
        notifications = int(notifications_result.scalar_one())

        imports_actionable_result = await self.db.execute(
            select(func.count())
            .select_from(ImportItem)
            .join(ImportJob, ImportItem.import_job_id == ImportJob.id)
            .where(
                ImportJob.user_id == user.id,
                ImportItem.archived_at.is_(None),
                ImportItem.dismissed_at.is_(None),
                ImportItem.status.in_(ACTIONABLE_IMPORT_STATUSES),
            )
        )
        imports_actionable = int(imports_actionable_result.scalar_one())

        return success(
            data=UnreadCount.Response(
                notifications=notifications,
                imports_actionable=imports_actionable,
                count=notifications + imports_actionable,
            )
        )

    class Response(BaseModel):
        notifications: int
        imports_actionable: int
        count: int = Field(
            deprecated=True,
            description=(
                "DEPRECATED — equals `notifications + imports_actionable`. "
                "Kept for pinned old clients during the abi-1 → abi-3 "
                "rollout window; remove after epic-activity-full-history "
                "ships."
            ),
        )
