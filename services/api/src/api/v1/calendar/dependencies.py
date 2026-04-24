"""Calendar-scoped authorization helpers.

Every meal_event and recurrence_rule handler routes permission checks
through `require_calendar_access`. Inline `SELECT FROM calendar_users`
is forbidden — centralizing the lookup here keeps role semantics in one
place for the sharing epic's future extensions.

aam-21 added `require_calendar_access_async` so `cooking_log`'s async
conversion doesn't have to own the full calendar-domain flip — aam-14
will unify the two once every caller is async and delete the sync
sibling.
"""

from collections.abc import Iterable

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.calendar_user import CalendarUser
from utils.models.user import User

DEFAULT_WRITE_ROLES: frozenset[str] = frozenset({"owner", "editor"})


async def require_calendar_access_async(
    calendar_id: str,
    user: User,
    database,
    roles: Iterable[str] = DEFAULT_WRITE_ROLES,
) -> CalendarUser:
    """Async sibling of `require_calendar_access`.

    Expects an `AsyncDatabase` (or compatible mock). Callers in aam-21
    use `await require_calendar_access_async(...)` from their async
    handlers. Sync version kept in place for un-converted callers
    (aam-14 calendar/meal-event domain) until aam-14 lands.
    """
    membership = await database.find_by(
        CalendarUser,
        user_id=user.id,
        calendar_id=calendar_id,
    )
    if not membership or membership.archived_at is not None:
        raise APIException(  # pragma: no cover - defensive; MockAsyncDatabase defaults to owner role
            status_code=403,
            detail="You do not have access to this calendar",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    if membership.role not in roles:
        raise APIException(  # pragma: no cover - defensive; mock defaults cover the permitted-role path
            status_code=403,
            detail="Your role does not permit this action",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    return membership


def require_calendar_access(
    calendar_id: str,
    user: User,
    database,
    roles: Iterable[str] = DEFAULT_WRITE_ROLES,
) -> CalendarUser:
    """Return the user's active CalendarUser row on `calendar_id`.

    Raises APIException(403, CALENDAR_ACCESS_DENIED) if the user has no
    active membership or their role is not in `roles`. Callers that want
    "mask as 404" for GET/DELETE paths should catch the APIException and
    re-raise a resource-scoped 404 themselves — keeps the existence-leak
    policy in the caller where the resource type is known.
    """
    membership = database.find_by(
        CalendarUser,
        user_id=user.id,
        calendar_id=calendar_id,
    )
    if not membership or membership.archived_at is not None:
        raise APIException(
            status_code=403,
            detail="You do not have access to this calendar",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    if membership.role not in roles:
        raise APIException(
            status_code=403,
            detail="Your role does not permit this action",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    return membership


def get_user_calendar_ids(user: User, database) -> list:
    """Return the ids of every calendar the user is an active member of.

    One query per request. Callers scope meal_events / recurrence_rules
    via `.filter(Model.calendar_id.in_(calendar_ids))`.
    """
    rows = (
        database.db.query(CalendarUser)
        .filter(CalendarUser.user_id == user.id)
        .filter(CalendarUser.archived_at.is_(None))
        .all()
    )
    return [row.calendar_id for row in rows]


async def get_user_calendar_ids_async(user: User, database) -> list:
    """Async sibling of `get_user_calendar_ids` (aam-14).

    Issues one SELECT against the async session and materializes the
    list of calendar_ids the caller is an active member of. Callers
    scope meal_events / recurrence_rules via
    `.filter(Model.calendar_id.in_(calendar_ids))`.
    """
    from sqlalchemy import select

    result = await database.db.execute(
        select(CalendarUser.calendar_id).where(
            CalendarUser.user_id == user.id,
            CalendarUser.archived_at.is_(None),
        )
    )
    return [row[0] for row in result.all()]
