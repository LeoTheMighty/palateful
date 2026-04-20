"""See-all count endpoint for the Notifications tab (afh-2).

Returns the counts that back the footer label "See all (N) ›" on the
Notifications tab without fetching rows.

``archived`` — rows that have been explicitly archived.
``read_and_older`` — rows that are read AND older than 30 days AND not
archived (they've "aged out" of the active list but aren't deleted).
``total`` — the sum.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.user import User
from utils.models.user_activity import NOTIFICATION_TAB_TYPES, UserActivity

_OLDER_THAN_DAYS = 30


class SeeAllCount(Endpoint):
    """Notifications See-all triple (archived, read_and_older, total)."""

    def execute(self):
        user: User = self.user
        cutoff = datetime.now(UTC) - timedelta(days=_OLDER_THAN_DAYS)

        archived = (
            self.db.query(UserActivity)
            .filter(
                UserActivity.user_id == user.id,
                UserActivity.archived_at.isnot(None),
                UserActivity.type.in_(NOTIFICATION_TAB_TYPES),
            )
            .count()
        )

        read_and_older = (
            self.db.query(UserActivity)
            .filter(
                UserActivity.user_id == user.id,
                UserActivity.archived_at.is_(None),
                UserActivity.read.is_(True),
                UserActivity.created_at < cutoff,
                UserActivity.type.in_(NOTIFICATION_TAB_TYPES),
            )
            .count()
        )

        return success(
            data=SeeAllCount.Response(
                archived=archived,
                read_and_older=read_and_older,
                total=archived + read_and_older,
            )
        )

    class Response(BaseModel):
        archived: int
        read_and_older: int
        total: int
