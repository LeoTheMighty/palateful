"""Shared access-control and validation helpers for recurrence rules."""

from __future__ import annotations

import uuid
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.pantry_user import PantryUser
from utils.models.user import User

VALID_INTERVALS = {"weekly", "biweekly", "monthly"}
VALID_WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
VALID_MONTHLY_NTH = {"first", "second", "third", "fourth", "last"}


def shares_pantry(database, user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> bool:
    """Return True if users share at least one pantry membership.

    Pantry membership is the app's proxy for household — meal-plan sharing
    already flows through it, so co-edit on shared rules symmetrically
    follows pantry co-membership.
    """
    if user_a_id == user_b_id:  # pragma: no cover - defensive short-circuit
        return True
    b_pantry_ids = [
        r.pantry_id
        for r in database.db.query(PantryUser)
        .filter(PantryUser.user_id == user_b_id)
        .all()
    ]
    if not b_pantry_ids:
        return False
    row = (
        database.db.query(PantryUser)
        .filter(PantryUser.user_id == user_a_id)
        .filter(PantryUser.pantry_id.in_(b_pantry_ids))
        .first()
    )
    return row is not None


def user_can_read_rule(
    database, rule: MealRecurrenceRule, user: User
) -> bool:
    if rule.owner_id == user.id:
        return True
    return bool(
        rule.is_shared and shares_pantry(database, user.id, rule.owner_id)
    )


def user_can_write_rule(
    database, rule: MealRecurrenceRule, user: User
) -> bool:
    """Co-edit: shared rules are writable by any pantry-mate of the owner."""
    if rule.owner_id == user.id:
        return True
    return bool(
        rule.is_shared and shares_pantry(database, user.id, rule.owner_id)
    )


def validate_tz_name(tz_name: str | None) -> ZoneInfo:
    if not tz_name:
        raise APIException(
            status_code=400,
            detail="tz_name is required",
            code=ErrorCode.VALIDATION_ERROR,
        )
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise APIException(
            status_code=400,
            detail=f"Invalid IANA tz_name: '{tz_name}'",
            code=ErrorCode.VALIDATION_ERROR,
        ) from exc


def validate_recurrence_fields(
    *,
    title: str | None,
    recipe_id: str | None,
    meal_type: str,
    weekdays: list[str],
    interval: str,
    monthly_nth: str | None,
    start_date: date,
    end_date: date | None,
    tz_name: str | None,
) -> None:
    """Raise APIException(400) on invalid combinations. tz_name presence is
    validated separately via validate_tz_name so the caller can reuse the
    parsed ZoneInfo."""
    if meal_type not in VALID_MEAL_TYPES:
        raise APIException(
            status_code=400,
            detail=f"Invalid meal_type: '{meal_type}'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if interval not in VALID_INTERVALS:
        raise APIException(
            status_code=400,
            detail=f"Invalid interval: '{interval}'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if not weekdays:
        raise APIException(
            status_code=400,
            detail="weekdays must contain at least one day",
            code=ErrorCode.VALIDATION_ERROR,
        )

    unknown = [d for d in weekdays if d not in VALID_WEEKDAYS]
    if unknown:
        raise APIException(
            status_code=400,
            detail=f"Unknown weekday(s): {unknown}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if interval == "monthly":
        if not monthly_nth or monthly_nth not in VALID_MONTHLY_NTH:
            raise APIException(
                status_code=400,
                detail="monthly_nth must be one of first/second/third/fourth/last when interval=='monthly'",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if len(weekdays) != 1:
            raise APIException(
                status_code=400,
                detail="monthly interval requires exactly one weekday",
                code=ErrorCode.VALIDATION_ERROR,
            )
    elif monthly_nth is not None:
        raise APIException(
            status_code=400,
            detail="monthly_nth is only valid when interval=='monthly'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if end_date is not None and start_date > end_date:
        raise APIException(
            status_code=400,
            detail="start_date must be on or before end_date",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if recipe_id is None and (title is None or not title.strip()):
        raise APIException(
            status_code=400,
            detail="title is required when recipe_id is not set",
            code=ErrorCode.VALIDATION_ERROR,
        )
