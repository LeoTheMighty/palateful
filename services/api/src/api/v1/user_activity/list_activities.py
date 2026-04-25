"""List user activities endpoint."""

import uuid
from datetime import UTC, datetime, timedelta

from pagination import (
    InvalidCursorError,
    datetime_to_ms,
    decode_cursor,
    encode_cursor,
)
from pydantic import BaseModel
from sqlalchemy import func, select, text, tuple_
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.models.user_activity import NOTIFICATION_TAB_TYPES, UserActivity

_DEFAULT_ACTIVITY_RETENTION_DAYS = 30
_MAX_LIMIT = 100
# Sentinel value for row-value comparisons on nullable archived_at.
# Postgres accepts ``'-infinity'`` as a timestamp literal that compares
# less than every real timestamp, giving "NULLS LAST" semantics under
# DESC ordering once we wrap the column in COALESCE.
_NEG_INF = text("'-infinity'::timestamptz")


class ListActivities(AsyncEndpoint):
    """List activities for the current user."""

    async def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
        include_system_types: bool = False,
        include_read: bool = False,
        since_days: int | None = _DEFAULT_ACTIVITY_RETENTION_DAYS,
        cursor: str | None = None,
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

        if cursor is not None and offset:
            raise APIException(
                status_code=400,
                detail="cursor_and_offset_mutually_exclusive",
                code=ErrorCode.VALIDATION_ERROR,
            )

        limit = max(1, min(limit, _MAX_LIMIT))

        # See-all mode: caller wants archived + read + unbounded window.
        # ``since_days is None`` is the explicit opt-in to no retention
        # cutoff. Ordering flips to ``archived_at DESC NULLS LAST, …``
        # so recently-archived rows land at the top.
        see_all_mode = include_archived and include_read and since_days is None

        stmt = select(UserActivity).where(UserActivity.user_id == user.id)
        if since_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=since_days)
            stmt = stmt.where(UserActivity.created_at >= cutoff)
        if not include_archived:
            stmt = stmt.where(UserActivity.archived_at.is_(None))
        if not include_system_types:
            # abi-1: default path returns only types on the Notifications
            # allow-list. Admin callers opt in via ?include_system_types=
            # true for debug (router enforces the admin gate).
            stmt = stmt.where(UserActivity.type.in_(NOTIFICATION_TAB_TYPES))

        if cursor is not None:
            try:
                cur_arch_ms, cur_created_ms, cur_id_str = decode_cursor(cursor)
            except InvalidCursorError as exc:
                raise APIException(
                    status_code=400,
                    detail="invalid_cursor",
                    code=ErrorCode.VALIDATION_ERROR,
                ) from exc
            try:
                cur_id = uuid.UUID(cur_id_str)
            except ValueError as exc:
                raise APIException(
                    status_code=400,
                    detail="invalid_cursor",
                    code=ErrorCode.VALIDATION_ERROR,
                ) from exc
            cur_created = datetime.fromtimestamp(cur_created_ms / 1000, tz=UTC)
            if see_all_mode:
                cur_arch_ts = (
                    _NEG_INF
                    if cur_arch_ms is None
                    else datetime.fromtimestamp(cur_arch_ms / 1000, tz=UTC)
                )
                stmt = stmt.where(
                    tuple_(
                        text(
                            "COALESCE(user_activities.archived_at, "
                            "'-infinity'::timestamptz)"
                        ),
                        UserActivity.created_at,
                        UserActivity.id,
                    )
                    < tuple_(cur_arch_ts, cur_created, cur_id)
                )
            else:
                stmt = stmt.where(
                    tuple_(UserActivity.created_at, UserActivity.id)
                    < tuple_(cur_created, cur_id)
                )

        if see_all_mode:
            stmt = stmt.order_by(
                text(
                    "COALESCE(user_activities.archived_at, '-infinity'::timestamptz) "
                    "DESC"
                ),
                UserActivity.created_at.desc(),
                UserActivity.id.desc(),
            )
        else:
            stmt = stmt.order_by(
                UserActivity.created_at.desc(),
                UserActivity.id.desc(),
            )

        # Fetch limit + 1 to detect a next page without a second count.
        result = await self.db.execute(stmt.limit(limit + 1))
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        results = rows[:limit]

        # pbq-5: `total` is always 0 on cursor-paginated responses. The
        # heavy COUNT(*) is gone — no Flutter consumer reads this field
        # from `/v1/activities` (the see-all footer uses the dedicated
        # `/v1/activities/see-all-count` endpoint). Clients that need a
        # count should call that endpoint; clients that page should use
        # `items.length` and `next_cursor`. Legacy `offset` path still
        # supported for one release.
        total = 0
        if cursor is None and offset:
            results = rows[offset : offset + limit] if len(rows) > offset else []
            has_more = len(rows) > offset + limit

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

        next_cursor: str | None = None
        if has_more and results:
            last = results[-1]
            next_cursor = encode_cursor(
                datetime_to_ms(last.archived_at) if see_all_mode else None,
                datetime_to_ms(last.created_at),
                str(last.id),
            )

        headers = None
        if next_cursor:
            # Router prefix is /v1/activities; build a rel="next" link
            # for well-behaved HTTP clients that follow Link headers.
            headers = {
                "Link": f'</v1/activities?cursor={next_cursor}>; rel="next"'
            }

        # ffm-4: bell-notification unread count snapshot computed in the
        # same transaction as the list query so the notifications tab
        # can drop its follow-up /unread-count round-trip. Uses the bell
        # filters — independent of this request's include_archived /
        # include_read / since_days toggles — so the value is always
        # "count of unread notification-type rows within retention",
        # regardless of which page the caller is viewing. Old clients
        # that don't know about the field ignore it; new clients read
        # it to save one round-trip on mount + every poll tick.
        unread_cutoff = datetime.now(UTC) - timedelta(
            days=_DEFAULT_ACTIVITY_RETENTION_DAYS
        )
        unread_result = await self.db.execute(
            select(func.count())
            .select_from(UserActivity)
            .where(
                UserActivity.user_id == user.id,
                UserActivity.read.is_(False),
                UserActivity.archived_at.is_(None),
                UserActivity.type.in_(NOTIFICATION_TAB_TYPES),
                UserActivity.created_at >= unread_cutoff,
            )
        )
        unread_count = int(unread_result.scalar_one())

        return success(
            data=ListActivities.Response(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
                next_cursor=next_cursor,
                unread_count=unread_count,
            ),
            headers=headers,
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
        """`total` is always 0 (pbq-5 dropped the heavy COUNT). Clients
        that need a count should call `/v1/activities/see-all-count`;
        cursor pagination uses `items.length` + `next_cursor`.

        `unread_count` (ffm-4) is a snapshot of the bell-notification
        unread count — computed in the same transaction as the list
        query so clients don't have to issue a second `/unread-count`
        round-trip. Value is "count accurate as-of this response's
        rows". Optional / null on old backends for back-compat; new
        backends always populate it."""

        items: list["ListActivities.ActivityItem"]
        total: int
        limit: int
        offset: int
        next_cursor: str | None = None
        unread_count: int | None = None
