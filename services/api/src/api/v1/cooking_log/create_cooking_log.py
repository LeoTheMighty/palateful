"""POST /v1/cooking-logs — record a cook from a meal_event or directly.

Three target shapes (matching the `ck_cooking_logs_target` CHECK):

  * Recipe event → 1 row, `recipe_id` set, `meal_id` NULL.
  * Meal event   → 1 parent row (`meal_id` set, `recipe_id` NULL) +
                   N child rows (`recipe_id` set, `parent_meal_log_id`
                   pointing to the parent). Children preserve recipe-
                   level `last_cooked_at` history while the parent row
                   shows up on the Meal detail surface.
  * Direct recipe — caller passes `recipe_id` without `meal_event_id`
                   for a freeform "I cooked this" log entry.

Caller supplies `meal_event_id` XOR `recipe_id`. Both-set is a 422.
"""

from datetime import datetime
from decimal import Decimal

from api.v1.calendar.dependencies import require_calendar_access_async
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.cooking_log import CookingLog
from utils.models.meal import Meal
from utils.models.meal_event import MealEvent
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe


class CreateCookingLog(AsyncEndpoint):
    """Mark a meal_event as cooked (or log a recipe directly)."""

    async def execute(self, params: "CreateCookingLog.Params"):
        user = self.user

        if params.meal_event_id and params.recipe_id:
            raise APIException(
                status_code=422,
                detail="meal_event_id and recipe_id are mutually exclusive",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if not params.meal_event_id and not params.recipe_id:
            raise APIException(
                status_code=422,
                detail="meal_event_id or recipe_id is required",
                code=ErrorCode.VALIDATION_ERROR,
            )

        cooked_at = params.cooked_at or datetime.utcnow()
        scale = params.scale_factor if params.scale_factor is not None else Decimal("1.0")

        if params.meal_event_id:
            event = await self.database.find_by(
                MealEvent, id=params.meal_event_id
            )
            if not event:
                raise APIException(
                    status_code=404,
                    detail=f"Meal event with ID '{params.meal_event_id}' not found",
                    code=ErrorCode.MEAL_EVENT_NOT_FOUND,
                )
            await require_calendar_access_async(
                str(event.calendar_id), user, self.database
            )

            if event.meal_id is not None:
                # Meal-event fan-out: 1 parent + N children. Eager-load
                # `meal.components -> recipe` so the children loop walks
                # the mapping without triggering MissingGreenlet.
                # Lazy-load audit: access chain is `meal.components[i].recipe`
                # — covered by `selectinload(Meal.components).selectinload(
                # MealRecipe.recipe)` (Meal.components is a list of
                # MealRecipe rows — the model name tracks the join
                # table, not the UX term "component").
                meal_stmt = (
                    select(Meal)
                    .options(
                        selectinload(Meal.components).selectinload(
                            MealRecipe.recipe
                        )
                    )
                    .where(Meal.id == event.meal_id)
                )
                meal_result = await self.db.execute(meal_stmt)
                meal = meal_result.scalars().first()

                parent = CookingLog(
                    meal_id=event.meal_id,
                    recipe_id=None,
                    parent_meal_log_id=None,
                    cooked_at=cooked_at,
                    scale_factor=scale,
                    notes=params.notes,
                )
                await self.database.create(parent)

                children: list[CookingLog] = []
                if meal is not None:
                    for component in meal.components:
                        recipe = component.recipe
                        if recipe is None or recipe.archived_at is not None:
                            continue
                        child = CookingLog(
                            recipe_id=recipe.id,
                            meal_id=None,
                            parent_meal_log_id=parent.id,
                            cooked_at=cooked_at,
                            scale_factor=scale,
                            notes=None,
                        )
                        await self.database.create(child)
                        children.append(child)

                await self.database.db.commit()
                return success(
                    data=CreateCookingLog.Response(
                        parent_log_id=str(parent.id),
                        child_log_ids=[str(c.id) for c in children],
                        cooked_at=parent.cooked_at,
                        meal_id=str(event.meal_id),
                        recipe_id=None,
                    ),
                    status=201,
                )

            if event.recipe_id is None:
                raise APIException(
                    status_code=422,
                    detail="Free-text events cannot be marked cooked",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            log = CookingLog(
                recipe_id=event.recipe_id,
                meal_id=None,
                parent_meal_log_id=None,
                cooked_at=cooked_at,
                scale_factor=scale,
                notes=params.notes,
            )
            await self.database.create(log)
            await self.database.db.commit()
            return success(
                data=CreateCookingLog.Response(
                    parent_log_id=str(log.id),
                    child_log_ids=[],
                    cooked_at=log.cooked_at,
                    meal_id=None,
                    recipe_id=str(event.recipe_id),
                ),
                status=201,
            )

        # Direct recipe path (no event).
        recipe = await self.database.find_by(Recipe, id=params.recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{params.recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        log = CookingLog(
            recipe_id=recipe.id,
            meal_id=None,
            parent_meal_log_id=None,
            cooked_at=cooked_at,
            scale_factor=scale,
            notes=params.notes,
        )
        await self.database.create(log)
        await self.database.db.commit()
        return success(
            data=CreateCookingLog.Response(
                parent_log_id=str(log.id),
                child_log_ids=[],
                cooked_at=log.cooked_at,
                meal_id=None,
                recipe_id=str(recipe.id),
            ),
            status=201,
        )

    class Params(BaseModel):
        meal_event_id: str | None = None
        recipe_id: str | None = None
        scale_factor: Decimal | None = None
        notes: str | None = None
        cooked_at: datetime | None = None

    class Response(BaseModel):
        parent_log_id: str
        # Empty for recipe-only logs; populated for Meal-level fan-out.
        child_log_ids: list[str]
        cooked_at: datetime
        meal_id: str | None = None
        recipe_id: str | None = None
