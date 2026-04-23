"""GET /v1/meals/public/{token} — unauthenticated read view of a shared Meal.

Privacy invariant: the response MUST NOT leak `recipe_id` / `order_index` /
`book_id` for components. A stranger holding the public Meal link should only
see structure (name, thumbnail, whether the component is itself publicly
shared) — never internal UUIDs they could probe. See
`test_get_public_meal.py::test_privacy_invariant_no_recipe_id_in_json`.
"""

from schemas.meal import PublicMealComponent, PublicMealResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook


class GetPublicMealByToken(AsyncEndpoint):
    """Load a Meal by its share token. No auth required."""

    async def execute(self, token: str):
        db = self.db

        meal_result = await db.execute(
            select(Meal)
            .options(
                selectinload(Meal.components).selectinload(MealRecipe.recipe)
            )
            .where(Meal.share_token == token)
            .where(Meal.archived_at.is_(None))
        )
        meal = meal_result.scalars().first()
        if meal is None:
            raise APIException(
                status_code=404,
                detail="Meal not found",
                code=ErrorCode.MEAL_NOT_FOUND,
            )

        book_result = await db.execute(
            select(RecipeBook).where(RecipeBook.id == meal.recipe_book_id)
        )
        book = book_result.scalars().first()

        components: list[PublicMealComponent] = []
        for mc in sorted(meal.components, key=lambda c: c.order_index):
            recipe: Recipe | None = mc.recipe
            if recipe is None:
                continue
            if recipe.archived_at is not None:
                continue
            has_token = recipe.share_token is not None
            components.append(
                PublicMealComponent(
                    name=recipe.name,
                    image_url=recipe.image_url,
                    has_public_token=has_token,
                    public_token=recipe.share_token if has_token else None,
                )
            )

        return success(
            data=PublicMealResponse(
                id=str(meal.id),
                name=meal.name,
                description=meal.description,
                recipe_book_name=book.name if book else "",
                components=components,
            )
        )
