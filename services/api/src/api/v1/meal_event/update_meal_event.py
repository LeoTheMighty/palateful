"""Update meal event endpoint."""

import logging
from datetime import date, datetime, time
from typing import Optional

from api.v1.calendar.dependencies import require_calendar_access
from api.v1.meal_event._meal_binding import (
    MealSummary,
    build_meal_summary,
    require_meal_available,
    validate_recipe_meal_xor,
)
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.events import MealEventCompleted, dispatch
from utils.models.meal_event import MealEvent
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.services.meal_event_notifications import notify_meal_event_updated

logger = logging.getLogger(__name__)

VALID_STATUSES = ["planned", "shopping", "prepping", "cooking", "completed", "skipped"]
VALID_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

# Fields whose mutation should trigger MEAL_EVENT_UPDATED. Intentionally
# narrower than the full PATCH surface — edits to `description`,
# notification offsets, etc. shouldn't wake co-cooks.
_NOTIFY_TRIGGER_FIELDS: frozenset[str] = frozenset(
    {"title", "scheduled_at", "recipe_id", "meal_id", "meal_reminder_time"}
)


def _compute_changed_fields(
    before: dict, meal_event: MealEvent
) -> list[str]:
    """Diff the pre-commit snapshot against the refreshed row; return
    the subset of `_NOTIFY_TRIGGER_FIELDS` whose value changed."""
    changed: list[str] = []
    after_map = {
        "title": meal_event.title,
        "scheduled_at": meal_event.scheduled_at,
        "recipe_id": meal_event.recipe_id,
        "meal_id": meal_event.meal_id,
        "meal_reminder_time": meal_event.meal_reminder_time,
    }
    for key in _NOTIFY_TRIGGER_FIELDS:
        if before.get(key) != after_map.get(key):
            changed.append(key)
    return changed


def _format_new_time(scheduled_at: datetime) -> str:
    """Human-friendly 12h time for the "moved to X" notification title.
    Uses UTC (server tz) — recipient tz localization happens on-device
    when the deep-link opens the detail screen. For the body text
    that's fine; the precise wall-clock is in the detail view."""
    hour24 = scheduled_at.hour
    hour12 = 12 if hour24 == 0 else (hour24 - 12 if hour24 > 12 else hour24)
    ampm = "AM" if hour24 < 12 else "PM"
    minute_str = f"{scheduled_at.minute:02d}"
    return f"{hour12}:{minute_str} {ampm}"


class UpdateMealEvent(Endpoint):
    """Update a meal event."""

    def execute(self, event_id: str, params: "UpdateMealEvent.Params"):
        """
        Update a meal event.

        Args:
            event_id: The meal event's ID
            params: Update parameters

        Returns:
            Updated meal event data
        """
        user: User = self.user

        # Find meal event
        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Calendar membership gates edit authorization; host/cohost/guest
        # participants are NOT consulted. Non-member → 403 (PATCH is a
        # write — existence leak is less concerning than GET, and 403
        # signals "you can't do this" more usefully here).
        require_calendar_access(
            str(meal_event.calendar_id), user, self.database
        )

        # Move-to-calendar: optional field on PATCH. Different calendar →
        # verify editor on destination, then flip calendar_id. Same
        # calendar is a silent no-op. Empty string is treated as "no
        # calendar_id supplied" via the calendar-required error so older
        # clients that send "" don't land in a membership query with an
        # empty UUID.
        if params.calendar_id == "":
            raise APIException(
                status_code=400,
                detail="calendar_id must not be empty",
                code=ErrorCode.MEAL_EVENT_CALENDAR_REQUIRED,
            )
        if (
            params.calendar_id is not None
            and params.calendar_id != str(meal_event.calendar_id)
        ):
            require_calendar_access(params.calendar_id, user, self.database)
            meal_event.calendar_id = params.calendar_id

        # Validate status if provided
        if params.status and params.status not in VALID_STATUSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
                code=ErrorCode.MEAL_EVENT_INVALID_STATUS,
            )

        # Validate meal type if provided
        if params.meal_type and params.meal_type not in VALID_MEAL_TYPES:
            raise APIException(
                status_code=400,
                detail=f"Invalid meal type. Must be one of: {', '.join(VALID_MEAL_TYPES)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Mode-switch gate: callers supplying both ids get rejected. The
        # effective post-patch state must honor the XOR invariant too —
        # if the client only supplies `meal_id`, clear the prior
        # `recipe_id` to avoid a both-set row; same for the reverse.
        resolved_recipe_id = (
            params.recipe_id
            if params.recipe_id is not None
            else (str(meal_event.recipe_id) if meal_event.recipe_id else None)
        )
        resolved_meal_id = (
            params.meal_id
            if params.meal_id is not None
            else (str(meal_event.meal_id) if meal_event.meal_id else None)
        )
        # Client may set one FK and clear the other implicitly by supplying
        # only the one they want. We reject cases where the client explicitly
        # sets both; but if they set only meal_id and the row already has a
        # recipe_id, we interpret that as a mode switch and clear the recipe.
        if params.recipe_id is not None and params.meal_id is None:
            resolved_meal_id = None
        if params.meal_id is not None and params.recipe_id is None:
            resolved_recipe_id = None
        validate_recipe_meal_xor(resolved_recipe_id, resolved_meal_id)

        # Verify recipe exists if updating
        if params.recipe_id:
            recipe = self.database.find_by(Recipe, id=params.recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{params.recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )

        # Verify meal exists + readable + not archived if switching modes.
        if params.meal_id:
            require_meal_available(self.database.db, params.meal_id, user)

        # Capture pre-update state for pantry-4 event dispatch.
        previous_status = meal_event.status
        # Capture pre-update state for meal-4 MEAL_EVENT_UPDATED
        # dispatch. We diff the request payload against these snapshots
        # AFTER commit to decide which recipients (if any) should be
        # notified. Holding primitives, not the loaded row, avoids any
        # subtle "was this column re-bound?" issues.
        before = {
            "title": meal_event.title,
            "scheduled_at": meal_event.scheduled_at,
            "recipe_id": meal_event.recipe_id,
            "meal_id": meal_event.meal_id,
            "meal_reminder_time": meal_event.meal_reminder_time,
        }
        was_shared = bool(meal_event.is_shared)

        # Update fields
        if params.title is not None:
            meal_event.title = params.title
        if params.description is not None:
            meal_event.description = params.description
        if params.scheduled_at is not None:
            meal_event.scheduled_at = params.scheduled_at
        if params.meal_type is not None:
            meal_event.meal_type = params.meal_type
        if params.status is not None:
            meal_event.status = params.status
        if params.recipe_id is not None:
            meal_event.recipe_id = params.recipe_id
            # Mode-switch: setting recipe_id clears meal_id.
            meal_event.meal_id = None
        if params.meal_id is not None:
            meal_event.meal_id = params.meal_id
            # Mode-switch: setting meal_id clears recipe_id.
            meal_event.recipe_id = None
        if params.pantry_id is not None:
            meal_event.pantry_id = params.pantry_id
        if params.notify_prep_start is not None:
            meal_event.notify_prep_start = params.notify_prep_start
        if params.prep_start_offset_minutes is not None:
            meal_event.prep_start_offset_minutes = params.prep_start_offset_minutes
        if params.notify_cook_start is not None:
            meal_event.notify_cook_start = params.notify_cook_start
        if params.cook_start_offset_minutes is not None:
            meal_event.cook_start_offset_minutes = params.cook_start_offset_minutes
        # `meal_reminder_time` needs field-presence semantics, not null-
        # means-leave-alone: sending `null` explicitly is how the client
        # clears a per-meal override back to the slot default. Use
        # model_fields_set to distinguish "omitted" from "sent as null".
        if "meal_reminder_time" in params.model_fields_set:
            meal_event.meal_reminder_time = params.meal_reminder_time
        if params.is_shared is not None:
            meal_event.is_shared = params.is_shared
        if params.is_recurring is not None:
            meal_event.is_recurring = params.is_recurring
        if params.recurrence_rule is not None:
            meal_event.recurrence_rule = params.recurrence_rule
        if params.recurrence_end_date is not None:
            meal_event.recurrence_end_date = params.recurrence_end_date

        self.database.db.commit()
        self.database.db.refresh(meal_event)

        # meal-4: fan MEAL_EVENT_UPDATED to accepted participants when a
        # SHARED event's user-visible fields changed. We skip when the
        # event wasn't shared before AND isn't shared now — the
        # notification only makes sense between co-cooks. Per-recipient
        # prefs + quiet hours apply inside the notify function.
        changed_fields = _compute_changed_fields(before, meal_event)
        should_notify_update = (
            (was_shared or meal_event.is_shared)
            and bool(changed_fields)
        )
        if should_notify_update:
            try:
                new_time_display = (
                    _format_new_time(meal_event.scheduled_at)
                    if "scheduled_at" in changed_fields
                    else None
                )
                notify_meal_event_updated(
                    meal_event,
                    user,
                    changed_fields=changed_fields,
                    new_time=new_time_display,
                    db_session=self.database.db,
                )
            except Exception:
                # Best-effort — a push-fanout failure must never 500 the
                # PATCH (the user's edit already committed).
                logger.exception(
                    "meal_event_updated_fanout_failed meal_event_id=%s",
                    meal_event.id,
                )

        # Pantry decrement hook (pantry-4). Only fires on the transition
        # into "completed" — re-submitting completed→completed is a no-op
        # and skipped→completed still triggers (a skipped meal that later
        # flips to cooked should consume the pantry).
        if (
            meal_event.status == "completed"
            and previous_status != "completed"
            and meal_event.recipe_id is not None
        ):
            try:
                dispatch(
                    "MealEventCompleted",
                    MealEventCompleted(
                        user_id=user.id,
                        meal_event_id=meal_event.id,
                        recipe_id=meal_event.recipe_id,
                        servings=None,
                    ),
                )
            except Exception:
                # Best-effort: never block the mark-as-cooked action.
                logger.exception(
                    "meal_event_completed_dispatch_failed meal_event_id=%s",
                    meal_event.id,
                )

        # Build recipe summary if present
        recipe_summary = None
        if meal_event.recipe:
            recipe_summary = UpdateMealEvent.RecipeSummary(
                id=str(meal_event.recipe.id),
                name=meal_event.recipe.name,
                description=meal_event.recipe.description,
                prep_time=meal_event.recipe.prep_time,
                cook_time=meal_event.recipe.cook_time,
                image_url=meal_event.recipe.image_url,
            )

        meal_summary = (
            build_meal_summary(meal_event.meal) if meal_event.meal else None
        )

        # Build participants list
        participants = []
        for p in meal_event.participants:
            participants.append(
                UpdateMealEvent.ParticipantResponse(
                    user_id=str(p.user_id),
                    user_email=p.user.email if p.user else None,
                    user_name=p.user.name if p.user else None,
                    status=p.status,
                    role=p.role,
                    assigned_tasks=p.assigned_tasks or [],
                    created_at=p.created_at,
                )
            )

        return success(
            data=UpdateMealEvent.Response(
                id=str(meal_event.id),
                title=meal_event.title,
                description=meal_event.description,
                scheduled_at=meal_event.scheduled_at,
                meal_type=meal_event.meal_type,
                status=meal_event.status,
                notify_prep_start=meal_event.notify_prep_start,
                prep_start_offset_minutes=meal_event.prep_start_offset_minutes,
                notify_cook_start=meal_event.notify_cook_start,
                cook_start_offset_minutes=meal_event.cook_start_offset_minutes,
                meal_reminder_time=meal_event.meal_reminder_time,
                reminder_time=meal_event.reminder_time,
                is_shared=meal_event.is_shared,
                is_recurring=meal_event.is_recurring,
                recurrence_rule=meal_event.recurrence_rule,
                recurrence_end_date=meal_event.recurrence_end_date,
                parent_event_id=(
                    str(meal_event.parent_event_id)
                    if meal_event.parent_event_id
                    else None
                ),
                recipe=recipe_summary,
                meal_id=str(meal_event.meal_id) if meal_event.meal_id else None,
                meal_summary=meal_summary,
                pantry_id=str(meal_event.pantry_id) if meal_event.pantry_id else None,
                owner_id=str(meal_event.owner_id),
                calendar_id=str(meal_event.calendar_id),
                participants=participants,
                created_at=meal_event.created_at,
                updated_at=meal_event.updated_at,
            )
        )

    class Params(BaseModel):
        title: str | None = None
        description: str | None = None
        scheduled_at: datetime | None = None
        meal_type: str | None = None
        status: str | None = None
        recipe_id: str | None = None
        meal_id: str | None = None
        pantry_id: str | None = None
        # Move-to-calendar: set to a different calendar to move the meal.
        # Must be a calendar the user has editor access on.
        calendar_id: str | None = None
        notify_prep_start: bool | None = None
        prep_start_offset_minutes: int | None = None
        notify_cook_start: bool | None = None
        cook_start_offset_minutes: int | None = None
        # Per-meal wall-clock reminder override. Semantics:
        #   - key omitted  → leave unchanged
        #   - key = "HH:MM" → persist the override
        #   - key = null   → clear the override (revert to slot default)
        # The endpoint uses `model_fields_set` to distinguish omit from
        # explicit-null (standard None-means-skip pattern can't clear).
        meal_reminder_time: time | None = None
        is_shared: bool | None = None
        is_recurring: bool | None = None
        recurrence_rule: str | None = None
        recurrence_end_date: date | None = None

    class RecipeSummary(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None

    class ParticipantResponse(BaseModel):
        user_id: str
        user_email: str | None = None
        user_name: str | None = None
        status: str
        role: str
        assigned_tasks: list[str] = []
        created_at: datetime

    class Response(BaseModel):
        id: str
        title: str
        description: str | None = None
        scheduled_at: datetime
        meal_type: str
        status: str
        notify_prep_start: bool
        prep_start_offset_minutes: int
        notify_cook_start: bool
        cook_start_offset_minutes: int
        # User's per-meal override (may be null). `reminder_time` is the
        # resolved value the scheduler fires at — always populated,
        # falls back to slot default when override is null.
        meal_reminder_time: time | None = None
        reminder_time: time
        is_shared: bool
        is_recurring: bool
        recurrence_rule: str | None = None
        recurrence_end_date: date | None = None
        parent_event_id: str | None = None
        recipe: Optional["UpdateMealEvent.RecipeSummary"] = None
        meal_id: str | None = None
        meal_summary: MealSummary | None = None
        pantry_id: str | None = None
        owner_id: str
        calendar_id: str
        participants: list["UpdateMealEvent.ParticipantResponse"] = []
        created_at: datetime
        updated_at: datetime
