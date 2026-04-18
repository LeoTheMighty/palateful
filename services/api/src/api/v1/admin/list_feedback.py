"""GET /v1/admin/feedback — admin inbox listing.

Paginated listing of user feedback rows joined with users for display_name
and email. Default filter is `unread` (matches the inbox default). No
cursor pagination — offset/limit is fine at expected scale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_feedback import UserFeedback

MAX_LIMIT = 100
DEFAULT_LIMIT = 25

_VALID_STATUS_FILTERS = ("unread", "read", "archived", "all")


class ListFeedback(Endpoint):
    """List feedback entries for the admin inbox."""

    def execute(
        self,
        status: str = "unread",
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ):
        if status not in _VALID_STATUS_FILTERS:
            raise APIException(
                status_code=400,
                detail=f"Invalid status filter: {status!r}",
                code=ErrorCode.VALIDATION_ERROR,
            )

        bounded_limit = min(max(limit, 1), MAX_LIMIT)
        bounded_offset = max(offset, 0)

        count_stmt = select(func.count()).select_from(UserFeedback)
        list_stmt = (
            select(UserFeedback, User)
            .join(User, UserFeedback.user_id == User.id)
            .order_by(UserFeedback.created_at.desc())
        )
        if status != "all":
            count_stmt = count_stmt.where(UserFeedback.status == status)
            list_stmt = list_stmt.where(UserFeedback.status == status)

        total = self.db.execute(count_stmt).scalar() or 0

        rows = self.db.execute(
            list_stmt.offset(bounded_offset).limit(bounded_limit)
        ).all()

        items = [
            ListFeedback.FeedbackItem(
                id=str(fb.id),
                user_id=str(fb.user_id),
                user_display_name=_display_name(u),
                user_email=u.email,
                body=fb.body,
                category=fb.category,
                status=fb.status,
                context=fb.context,
                created_at=_iso(fb.created_at),
                updated_at=_iso(fb.updated_at),
            )
            for fb, u in rows
        ]

        return success(
            data=ListFeedback.Response(
                items=items,
                total=total,
                status=status,
                offset=bounded_offset,
                limit=bounded_limit,
            )
        )

    class FeedbackItem(BaseModel):
        id: str
        user_id: str
        user_display_name: str | None = None
        user_email: str | None = None
        body: str
        category: str | None = None
        status: Literal["unread", "read", "archived"]
        context: dict | None = None
        created_at: str | None = None
        updated_at: str | None = None

    class Response(BaseModel):
        items: list[ListFeedback.FeedbackItem]
        total: int
        status: str
        offset: int
        limit: int


def _display_name(user: User) -> str | None:
    return user.name or user.username or user.email


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
