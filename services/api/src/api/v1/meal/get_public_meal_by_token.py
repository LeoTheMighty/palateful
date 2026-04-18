"""GET /v1/meals/public/{token} — unauthenticated read view of a shared Meal.

Privacy invariant: the response MUST NOT leak `recipe_id` / `order_index` /
`book_id` for components. A stranger holding the public Meal link should only
see structure (name, thumbnail, whether the component is itself publicly
shared) — never internal UUIDs they could probe. See
`test_get_public_meal.py::test_privacy_invariant_no_recipe_id_in_json`.
"""

from schemas.meal import PublicMealComponent, PublicMealResponse
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook


class GetPublicMealByToken(Endpoint):
    """Load a Meal by its share token. No auth required."""

    def execute(self, token: str):
        db = self.db

        meal = (
            db.query(Meal)
            .options(
                selectinload(Meal.components).selectinload(MealRecipe.recipe)
            )
            .filter(Meal.share_token == token)
            .filter(Meal.archived_at.is_(None))
            .first()
        )
        if meal is None:
            raise APIException(
                status_code=404,
                detail="Meal not found",
                code=ErrorCode.MEAL_NOT_FOUND,
            )

        book = (
            db.query(RecipeBook).filter(RecipeBook.id == meal.recipe_book_id).first()
        )

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
