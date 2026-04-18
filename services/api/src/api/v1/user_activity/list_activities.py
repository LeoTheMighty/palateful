"""List user activities endpoint."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.user import User
from utils.models.user_activity import UserActivity

_ACTIVITY_RETENTION_DAYS = 30


class ListActivities(Endpoint):
    """List activities for the current user."""

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
    ):
        user: User = self.user
        cutoff = datetime.now(UTC) - timedelta(days=_ACTIVITY_RETENTION_DAYS)

        query = self.db.query(UserActivity).filter(
            UserActivity.user_id == user.id,
            UserActivity.created_at >= cutoff,
        )
        if not include_archived:
            query = query.filter(UserActivity.archived_at.is_(None))

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
