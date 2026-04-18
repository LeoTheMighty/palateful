"""Shared validation helpers for recurrence rules.

Authorization used to live here (user_can_read_rule, user_can_write_rule,
shares_pantry) but was replaced by calendar-membership gating via
`api.v1.calendar.dependencies.require_calendar_access` in cal-found-2.
Only the stateless field validators remain.
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode

VALID_INTERVALS = {"weekly", "biweekly", "monthly"}
VALID_WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
VALID_MONTHLY_NTH = {"first", "second", "third", "fourth", "last"}


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
