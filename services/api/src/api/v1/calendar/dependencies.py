"""Calendar-scoped authorization helpers.

Every meal_event and recurrence_rule handler routes permission checks
through `require_calendar_access`. Inline `SELECT FROM calendar_users`
is forbidden — centralizing the lookup here keeps role semantics in one
place for the sharing epic's future extensions.
"""

from collections.abc import Iterable

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.calendar_user import CalendarUser
from utils.models.user import User

DEFAULT_WRITE_ROLES: frozenset[str] = frozenset({"owner", "editor"})


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
