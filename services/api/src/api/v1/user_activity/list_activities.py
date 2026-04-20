"""List user activities endpoint."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_activity import NOTIFICATION_TAB_TYPES, UserActivity

_ACTIVITY_RETENTION_DAYS = 30


class ListActivities(Endpoint):
    """List activities for the current user."""

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
        include_system_types: bool = False,
    ):
        user: User = self.user
        # abi-1: admin-gate the debug flag. The default path (no flag)
        # stays open to every user; only the escape hatch that returns
        # system-type rows is admin-only.
        if include_system_types and not user.is_admin:
            raise APIException(
                status_code=403,
                detail="Admin access required",
                code=ErrorCode.FORBIDDEN,
            )
        cutoff = datetime.now(UTC) - timedelta(days=_ACTIVITY_RETENTION_DAYS)

        query = self.db.query(UserActivity).filter(
            UserActivity.user_id == user.id,
            UserActivity.created_at >= cutoff,
        )
        if not include_archived:
            query = query.filter(UserActivity.archived_at.is_(None))
        if not include_system_types:
            # abi-1: default path returns only types on the Notifications
            # allow-list. Admin callers opt in via ?include_system_types=
            # true for debug (router enforces the admin gate).
            query = query.filter(UserActivity.type.in_(NOTIFICATION_TAB_TYPES))

        query = query.order_by(UserActivity.created_at.desc())

        total = query.count()
        results = query.offset(offset).limit(limit).all()

        items = [
            ListActivities.ActivityItem(
                id=str(a.id),
                type=a.type,
                title=a.title,
                subtitle=a.subtitle,
                metadata=a.metadata_json,
                read=a.read,
                action_url=a.action_url,
                created_at=a.created_at,
                archived_at=a.archived_at,
            )
            for a in results
        ]

        return success(
            data=ListActivities.Response(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )
        )

    class ActivityItem(BaseModel):
        id: str
        type: str
        title: str
        subtitle: str | None = None
        metadata: dict | None = None
        read: bool = False
        action_url: str | None = None
        created_at: datetime
        archived_at: datetime | None = None

    class Response(BaseModel):
        items: list["ListActivities.ActivityItem"]
        total: int
        limit: int
        offset: int
