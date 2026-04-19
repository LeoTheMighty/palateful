"""Update a recurrence rule with scope semantics.

scope="all"                 — patch the rule row in place and regenerate
                              future materialized meal_events.
scope="this_and_following"  — end the old rule the day before the chosen
                              occurrence_date and spin up a new rule
                              starting on that date with the supplied
                              field overrides. Gap-free / overlap-free
                              thanks to the unique
                              (recurrence_rule_id, scheduled_at) index on
                              meal_events.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from api.v1.calendar.dependencies import require_calendar_access
from api.v1.meal_event._meal_binding import (
    require_meal_available,
    validate_recipe_meal_xor,
)
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal as MealModel
from utils.models.meal_event import MealEvent
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.recurrence.materializer import (
    WEEKDAY_NAMES,
    _expected_dates,
)

from ._access import (
    validate_recurrence_fields,
    validate_tz_name,
)
from .create_recurrence_rule import (
    MATERIALIZATION_WINDOW_WEEKS,
    _rule_to_response,
)


def _load_meal_for_hydration(db, meal_id):
    """Load a Meal with components eager-loaded for response hydration."""
    if meal_id is None:
        return None
    return (
        db.query(MealModel)
        .options(
            selectinload(MealModel.components).selectinload(MealRecipe.recipe)
        )
        .filter(MealModel.id == meal_id)
        .first()
    )


class UpdateRecurrenceRule(Endpoint):
    def execute(self, rule_id: str, params: UpdateRecurrenceRule.Params):
        user: User = self.user

        rule = self.database.find_by(MealRecurrenceRule, id=rule_id)
        if not rule or rule.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Recurrence rule with ID '{rule_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )
        # Calendar membership is the sole edit-authorization gate.
        require_calendar_access(str(rule.calendar_id), user, self.database)

        if params.scope == "all":
            return self._apply_all(rule, params)
        if params.scope == "this_and_following":
            return self._apply_split(rule, params)

        raise APIException(
            status_code=400,
            detail=f"Invalid scope: '{params.scope}'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    # ------------------------------------------------------------------
    # scope == "all"

    def _apply_all(
        self, rule: MealRecurrenceRule, params: UpdateRecurrenceRule.Params
    ):
        # Resolve effective fields (patch semantics: None means "leave alone").
        title = params.title if params.title is not None else rule.title
        # Mode-switch semantics match update_meal_event: supplying only
        # one side implicitly clears the other so the XOR invariant
        # holds post-patch.
        if params.recipe_id is not None and params.meal_id is None:
            recipe_id = params.recipe_id
            meal_id = None
        elif params.meal_id is not None and params.recipe_id is None:
            recipe_id = None
            meal_id = params.meal_id
        else:
            recipe_id = (
                params.recipe_id
                if params.recipe_id is not None
                else rule.recipe_id
            )
            meal_id = (
                params.meal_id if params.meal_id is not None else rule.meal_id
            )
        meal_type = params.meal_type or rule.meal_type
        weekdays = params.weekdays if params.weekdays is not None else list(rule.weekdays or [])
        interval = params.interval or rule.interval
        monthly_nth = (
            params.monthly_nth
            if params.monthly_nth is not None
            else rule.monthly_nth
        )
        start_date = rule.start_date
        end_date = params.end_date if params.end_date is not None else rule.end_date
        tz_name = params.tz_name or rule.tz_name
        is_shared = (
            params.is_shared if params.is_shared is not None else rule.is_shared
        )

        if interval != "monthly":
            monthly_nth = None

        validate_recipe_meal_xor(
            str(recipe_id) if recipe_id else None,
            str(meal_id) if meal_id else None,
        )

        validate_tz_name(tz_name)
        validate_recurrence_fields(
            title=title,
            recipe_id=str(recipe_id) if recipe_id else None,
            meal_id=str(meal_id) if meal_id else None,
            meal_type=meal_type,
            weekdays=weekdays,
            interval=interval,
            monthly_nth=monthly_nth,
            start_date=start_date,
            end_date=end_date,
            tz_name=tz_name,
        )

        if recipe_id is not None:
            recipe = self.database.find_by(Recipe, id=str(recipe_id))
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )
        if meal_id is not None and params.meal_id is not None:
            # Only re-check access when the caller is actively setting meal_id.
            require_meal_available(self.database.db, str(meal_id), self.user)
        if recipe_id is not None or meal_id is not None:
            title_to_store = None
        else:
            title_to_store = (title or "").strip() or None

        rule.title = title_to_store
        rule.recipe_id = recipe_id
        rule.meal_id = meal_id
        rule.meal_type = meal_type
        rule.weekdays = weekdays
        rule.interval = interval
        rule.monthly_nth = monthly_nth
        rule.end_date = end_date
        rule.tz_name = tz_name
        rule.is_shared = is_shared

        # Move-to-calendar: optional calendar_id move on scope=all.
        # Cascades to future materialized meal_events joined on the rule.
        # Past materialized rows stay on the old calendar to preserve
        # historical attribution.
        #
        # Known gap: detached per-occurrence overrides (meal_events where
        # `recurrence_rule_id = NULL` from `_delete_single_occurrence`)
        # are orphaned from the cascade and remain on the old calendar.
        # Leo can move them individually via Move-to-calendar on the
        # detail sheet (cal-found-5). A dedicated "move all detached
        # children" sweep is deferred — the expected cardinality is low.
        if (
            params.calendar_id is not None
            and str(params.calendar_id) != str(rule.calendar_id)
        ):
            require_calendar_access(
                str(params.calendar_id), self.user, self.database
            )
            rule.calendar_id = params.calendar_id
            self.database.db.query(MealEvent).filter(
                MealEvent.recurrence_rule_id == rule.id,
                MealEvent.scheduled_at >= datetime.now(UTC),
            ).update(
                {MealEvent.calendar_id: params.calendar_id},
                synchronize_session=False,
            )

        from utils.recurrence.materializer import materialize

        through = rule.materialized_through or (
            date.today() + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)
        )
        materialize(rule, through, self.database.db)

        self.database.db.commit()
        self.database.db.refresh(rule)
        meal = _load_meal_for_hydration(self.database.db, rule.meal_id)
        return success(
            data={"rule": _rule_to_response(rule, meal=meal).model_dump(mode="json")}
        )

    # ------------------------------------------------------------------
    # scope == "this_and_following"

    def _apply_split(
        self, rule: MealRecurrenceRule, params: UpdateRecurrenceRule.Params
    ):
        occurrence_date = params.occurrence_date
        if occurrence_date is None:
            raise APIException(
                status_code=400,
                detail="occurrence_date is required for this_and_following scope",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if occurrence_date <= date.today():
            raise APIException(
                status_code=400,
                detail="occurrence_date must be in the future",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if occurrence_date < rule.start_date:
            raise APIException(
                status_code=400,
                detail="occurrence_date predates the rule's start_date",
                code=ErrorCode.VALIDATION_ERROR,
            )

        split_end = occurrence_date - timedelta(days=1)

        # Idempotent split detection: if the rule already ends the day
        # before and a sibling rule starting on occurrence_date exists with
        # identical owner, return both as a no-op. Do this BEFORE the
        # end-date bounds check since a resubmitted split legitimately has
        # end_date == split_end.
        if rule.end_date == split_end:
            existing_new = (
                self.database.db.query(MealRecurrenceRule)
                .filter(MealRecurrenceRule.owner_id == rule.owner_id)
                .filter(MealRecurrenceRule.start_date == occurrence_date)
                .filter(MealRecurrenceRule.archived_at.is_(None))
                .first()
            )
            if existing_new is not None:
                old_meal = _load_meal_for_hydration(
                    self.database.db, rule.meal_id
                )
                new_meal = _load_meal_for_hydration(
                    self.database.db, existing_new.meal_id
                )
                return success(
                    data={
                        "rule": _rule_to_response(rule, meal=old_meal).model_dump(
                            mode="json"
                        ),
                        "new_rule": _rule_to_response(
                            existing_new, meal=new_meal
                        ).model_dump(mode="json"),
                    }
                )

        if rule.end_date is not None and occurrence_date > rule.end_date:
            raise APIException(
                status_code=400,
                detail="occurrence_date is after the rule's end_date",
                code=ErrorCode.VALIDATION_ERROR,
            )
        # Occurrence must land on a valid rule-day.
        if not _date_is_on_rule(rule, occurrence_date):
            raise APIException(
                status_code=400,
                detail="occurrence_date does not fall on a scheduled rule day",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Build the new rule's fields (patch from old + overrides).
        title = params.title if params.title is not None else rule.title
        if params.recipe_id is not None and params.meal_id is None:
            recipe_id = params.recipe_id
            meal_id = None
        elif params.meal_id is not None and params.recipe_id is None:
            recipe_id = None
            meal_id = params.meal_id
        else:
            recipe_id = (
                params.recipe_id
                if params.recipe_id is not None
                else rule.recipe_id
            )
            meal_id = (
                params.meal_id if params.meal_id is not None else rule.meal_id
            )
        meal_type = params.meal_type or rule.meal_type
        weekdays = params.weekdays if params.weekdays is not None else list(rule.weekdays or [])
        interval = params.interval or rule.interval
        monthly_nth = (
            params.monthly_nth
            if params.monthly_nth is not None
            else rule.monthly_nth
        )
        tz_name = params.tz_name or rule.tz_name
        is_shared = (
            params.is_shared if params.is_shared is not None else rule.is_shared
        )
        new_end_date = params.end_date if params.end_date is not None else None

        if interval != "monthly":
            monthly_nth = None

        validate_recipe_meal_xor(
            str(recipe_id) if recipe_id else None,
            str(meal_id) if meal_id else None,
        )

        validate_tz_name(tz_name)
        validate_recurrence_fields(
            title=title,
            recipe_id=str(recipe_id) if recipe_id else None,
            meal_id=str(meal_id) if meal_id else None,
            meal_type=meal_type,
            weekdays=weekdays,
            interval=interval,
            monthly_nth=monthly_nth,
            start_date=occurrence_date,
            end_date=new_end_date,
            tz_name=tz_name,
        )

        if recipe_id is not None:
            recipe = self.database.find_by(Recipe, id=str(recipe_id))
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )
        if meal_id is not None and params.meal_id is not None:
            require_meal_available(self.database.db, str(meal_id), self.user)
        if recipe_id is not None or meal_id is not None:
            title_to_store = None
        else:
            title_to_store = (title or "").strip() or None

        from utils.recurrence.materializer import materialize

        # Shorten the old rule first and regenerate so its tail is cleared.
        rule.end_date = split_end
        old_through = rule.materialized_through or (
            date.today() + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)
        )
        materialize(rule, old_through, self.database.db)

        # Create the new rule and materialize forward. The new rule
        # inherits the source rule's calendar_id — move-to-calendar on a
        # split is not supported in this story (would require two
        # require_calendar_access checks and an explicit UX choice; defer
        # to if/when a user requests it).
        new_rule = MealRecurrenceRule(
            owner_id=rule.owner_id,
            calendar_id=rule.calendar_id,
            title=title_to_store,
            recipe_id=recipe_id,
            meal_id=meal_id,
            meal_type=meal_type,
            weekdays=weekdays,
            interval=interval,
            monthly_nth=monthly_nth,
            start_date=occurrence_date,
            end_date=new_end_date,
            tz_name=tz_name,
            is_shared=is_shared,
        )
        self.database.db.add(new_rule)
        self.database.db.flush()

        new_through = date.today() + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)
        materialize(new_rule, new_through, self.database.db)

        self.database.db.commit()
        self.database.db.refresh(rule)
        self.database.db.refresh(new_rule)
        old_meal = _load_meal_for_hydration(self.database.db, rule.meal_id)
        new_meal = _load_meal_for_hydration(self.database.db, new_rule.meal_id)
        return success(
            data={
                "rule": _rule_to_response(rule, meal=old_meal).model_dump(
                    mode="json"
                ),
                "new_rule": _rule_to_response(new_rule, meal=new_meal).model_dump(
                    mode="json"
                ),
            }
        )

    class Params(BaseModel):
        scope: str  # "all" | "this_and_following"
        occurrence_date: date | None = None

        # Patch fields — None means "leave alone" on scope=all.
        title: str | None = None
        recipe_id: str | None = None
        meal_id: str | None = None
        # Move-to-calendar (scope=all only). Must be a calendar where
        # the user has editor access. Cascades to future materialized
        # meal_events. On scope=this_and_following, the new rule
        # inherits the source rule's calendar_id.
        calendar_id: str | None = None
        meal_type: str | None = None
        weekdays: list[str] | None = None
        interval: str | None = None
        monthly_nth: str | None = None
        end_date: date | None = None
        tz_name: str | None = None
        is_shared: bool | None = None


def _date_is_on_rule(rule: MealRecurrenceRule, candidate: date) -> bool:
    """Check if candidate matches the rule's weekday + interval + nth spec."""
    if candidate.weekday() >= len(WEEKDAY_NAMES):  # pragma: no cover
        return False
    weekday_name = WEEKDAY_NAMES[candidate.weekday()]
    if weekday_name not in (rule.weekdays or []):
        return False
    # Reuse the materializer's expected-date computation for the rule's
    # interval kind, over a tight window around `candidate`.
    window_start = candidate
    window_end = candidate + timedelta(days=1)
    expected = _expected_dates(rule, window_start, window_end)
    return candidate in expected
