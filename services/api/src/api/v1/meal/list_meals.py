"""GET /v1/meals — flat list across every readable book."""

from api.v1.meal._response import build_meal_summary
from schemas.meal import MealListResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListMeals(AsyncEndpoint):
    """List Meals across every book the user can read.

    md-3 filter extensions:

    * `archived=true` — returns ONLY archived Meals (for the archive view),
      sorted by `archived_at DESC`.
    * `archived=false` or absent — excludes archived (today's behaviour).
    * `scope=home` — optimized defaults for the home grid. Excludes
      archived, sorts by `updated_at DESC`, raises the default limit to
      30 when the caller didn't specify one explicitly.

    `include_archived=true` is preserved for the pre-md-3 call sites. If
    both `archived` and `include_archived` are set, `archived` wins.
    """

    async def execute(
        self,
        limit: int | None = None,
        offset: int = 0,
        include_archived: bool = False,
        archived: bool | None = None,
        scope: str | None = None,
        q: str | None = None,
    ):
        user: User = self.user
        db = self.db

        # md-3: scope=home bumps the default limit to 30 and applies the
        # "exclude archived, updated_at DESC" pair. Explicit limit/archived
        # params still win.
        scope_home = scope == "home"
        effective_limit = limit
        if effective_limit is None:
            effective_limit = 30 if scope_home else 20
        # mcal-5: hard ceiling so an autocomplete caller can't accidentally
        # request a giant page. Keeps the per-request selectinload fan-out
        # bounded even when a misbehaving client passes limit=10000.
        effective_limit = min(effective_limit, 50)

        # md-3: archived=true returns only-archived; archived=false returns
        # only-active. include_archived=true (pre-md-3) is preserved.
        archived_only = archived is True
        if archived is False:
            include_archived = False
        elif archived is True:
            include_archived = True  # lets the query include archived rows
        if scope_home and archived is None:
            # scope=home implies archived=false; do not leak archived Meals.
            include_archived = False
            archived_only = False

        # pbq-2: fetch the readable-books set once and reuse it both to
        # scope the Meal list and to hydrate component availability.
        # Before: 1 subquery here + 1 per meal (30 for a home page).
        # After: 1 query total, regardless of page size.
        readable_result = await db.execute(
            select(RecipeBookUser.recipe_book_id).where(
                RecipeBookUser.user_id == user.id,
                RecipeBookUser.archived_at.is_(None),
            )
        )
        readable_book_ids = {
            str(row[0]) for row in readable_result.all()
        }

        conditions = [Meal.recipe_book_id.in_(readable_book_ids)]
        if archived_only:
            conditions.append(Meal.archived_at.is_not(None))
        elif not include_archived:
            conditions.append(Meal.archived_at.is_(None))

        # mcal-5: text autocomplete. Ignore blank-after-strip to avoid
        # filtering on `%%` which would match every row.
        if q is not None and q.strip():
            needle = f"%{q.strip()}%"
            conditions.append(
                or_(Meal.name.ilike(needle), Meal.description.ilike(needle))
            )

        count_stmt = (
            select(func.count()).select_from(Meal).where(*conditions)
        )
        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar_one())

        order_clause = (
            Meal.archived_at.desc()
            if archived_only
            else Meal.updated_at.desc()
        )
        meals_stmt = (
            select(Meal)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .where(*conditions)
            .order_by(order_clause)
            .offset(offset)
            .limit(effective_limit)
        )
        meals_result = await db.execute(meals_stmt)
        meals = list(meals_result.scalars().all())

        items = [
            await build_meal_summary(
                m, db=db, user_id=user.id, readable_book_ids=readable_book_ids
            )
            for m in meals
        ]
        return success(data=MealListResponse(items=items, total=total))
