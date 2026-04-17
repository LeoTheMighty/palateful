"""Rolling-window materializer for meal recurrence rules.

Expands a rule into concrete meal_events rows bounded by `through_date`.
Idempotent: re-running on the same rule + through_date converges on the
expected set (inserts missing rows, deletes extraneous ones).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.recipe import Recipe

logger = logging.getLogger(__name__)

# Canonical weekday strings used in MealRecurrenceRule.weekdays.
# Index matches datetime.weekday() (Mon=0 ... Sun=6).
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Per-meal-type local default time — mirrors Flutter's _mealDefaultTime.
SLOT_LOCAL_TIMES: dict[str, time] = {
    "breakfast": time(8, 0),
    "lunch": time(12, 0),
    "dinner": time(18, 0),
    "snack": time(15, 0),
}

_NTH_TO_INDEX = {"first": 0, "second": 1, "third": 2, "fourth": 3}


def _expected_dates(rule: MealRecurrenceRule, from_date: date, to_date: date) -> list[date]:
    """Compute dates in [from_date, to_date) that match the rule's grammar."""
    if from_date >= to_date:
        return []

    allowed = {WEEKDAY_NAMES.index(d) for d in rule.weekdays if d in WEEKDAY_NAMES}
    if not allowed:
        return []

    if rule.interval == "monthly":
        return _expected_monthly(rule, from_date, to_date, allowed)

    return _expected_weekly(rule, from_date, to_date, allowed)


def _expected_weekly(
    rule: MealRecurrenceRule,
    from_date: date,
    to_date: date,
    allowed: set[int],
) -> list[date]:
    biweekly = rule.interval == "biweekly"
    # Anchor week parity to the Monday of the rule's start week so biweekly
    # stays stable across year boundaries without depending on ISO week math.
    anchor_monday = rule.start_date - timedelta(days=rule.start_date.weekday())

    results: list[date] = []
    current = from_date
    while current < to_date:
        if current.weekday() in allowed and current >= rule.start_date:
            if biweekly:
                current_monday = current - timedelta(days=current.weekday())
                weeks_since_anchor = (current_monday - anchor_monday).days // 7
                if weeks_since_anchor % 2 != 0:
                    current += timedelta(days=1)
                    continue
            results.append(current)
        current += timedelta(days=1)
    return results


def _expected_monthly(
    rule: MealRecurrenceRule,
    from_date: date,
    to_date: date,
    allowed: set[int],
) -> list[date]:
    nth = rule.monthly_nth
    if nth is None or not allowed:
        return []
    weekday = next(iter(allowed))

    results: list[date] = []
    cursor = date(from_date.year, from_date.month, 1)
    while cursor < to_date:
        # Find all instances of weekday in this calendar month.
        first_day = cursor
        # Next month's first day:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)

        days_in_month = []
        d = first_day
        while d < next_month:
            if d.weekday() == weekday:
                days_in_month.append(d)
            d += timedelta(days=1)

        candidate: date | None
        if nth == "last":
            candidate = days_in_month[-1] if days_in_month else None
        else:
            idx = _NTH_TO_INDEX.get(nth)
            candidate = (
                days_in_month[idx]
                if idx is not None and idx < len(days_in_month)
                else None
            )

        if (
            candidate is not None
            and from_date <= candidate < to_date
            and candidate >= rule.start_date
        ):
            results.append(candidate)

        cursor = next_month
    return results


def _scheduled_at_utc(d: date, rule: MealRecurrenceRule) -> datetime:
    local_time = SLOT_LOCAL_TIMES.get(rule.meal_type, time(12, 0))
    tz = ZoneInfo(rule.tz_name)
    local_dt = datetime.combine(d, local_time, tzinfo=tz)
    return local_dt.astimezone(ZoneInfo("UTC"))


def _resolve_title(rule: MealRecurrenceRule, db: Session) -> str:
    if rule.recipe_id is not None:
        recipe = db.query(Recipe).filter(Recipe.id == rule.recipe_id).first()
        if recipe is not None:
            return recipe.name
    return rule.title or "Meal"


def materialize(
    rule: MealRecurrenceRule,
    through_date: date,
    db: Session,
) -> list[MealEvent]:
    """Materialize `rule` into concrete meal_events up to `through_date`.

    Runs within the caller's transaction. Idempotent under concurrency via
    the unique partial index on (recurrence_rule_id, scheduled_at).

    Returns the list of MealEvent rows currently attached to this rule
    within the window [today, through_date).
    """
    today = date.today()
    from_date = max(rule.start_date, today)

    # Respect rule.end_date if bounded.
    effective_through = through_date
    if rule.end_date is not None:
        # through is exclusive in our semantics; end_date is inclusive.
        effective_through = min(through_date, rule.end_date + timedelta(days=1))

    expected_dates = _expected_dates(rule, from_date, effective_through)
    expected_utc = {_scheduled_at_utc(d, rule) for d in expected_dates}

    # Existing rows attached to this rule in the window [today, through_date).
    tz = ZoneInfo(rule.tz_name)
    today_utc = datetime.combine(today, time.min, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    through_utc = datetime.combine(
        through_date, time.min, tzinfo=tz
    ).astimezone(ZoneInfo("UTC"))

    existing = (
        db.query(MealEvent)
        .filter(MealEvent.recurrence_rule_id == rule.id)
        .filter(MealEvent.scheduled_at >= today_utc)
        .filter(MealEvent.scheduled_at < through_utc)
        .all()
    )
    existing_by_ts = {e.scheduled_at: e for e in existing}

    # Delete extras (dates no longer in expected set).
    for ts, event in existing_by_ts.items():
        if ts not in expected_utc:
            db.delete(event)

    title = _resolve_title(rule, db)

    # Update title on existing rows that remain (recipe-rename propagation).
    for ts, event in existing_by_ts.items():
        if ts in expected_utc and event.title != title:
            event.title = title

    # Insert missing rows using INSERT ... ON CONFLICT DO NOTHING to stay
    # idempotent under concurrent materialize() calls.
    missing = sorted(expected_utc - set(existing_by_ts.keys()))
    if missing:
        insert_values = [
            {
                "title": title,
                "scheduled_at": ts,
                "meal_type": rule.meal_type,
                "owner_id": rule.owner_id,
                "recipe_id": rule.recipe_id,
                "is_shared": rule.is_shared,
                "recurrence_rule_id": rule.id,
                "status": "planned",
            }
            for ts in missing
        ]
        stmt = pg_insert(MealEvent.__table__).values(insert_values)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["recurrence_rule_id", "scheduled_at"],
        )
        db.execute(stmt)

    rule.materialized_through = through_date

    # Return the updated set.
    refreshed = (
        db.query(MealEvent)
        .filter(MealEvent.recurrence_rule_id == rule.id)
        .filter(MealEvent.scheduled_at >= today_utc)
        .filter(MealEvent.scheduled_at < through_utc)
        .all()
    )
    return refreshed
