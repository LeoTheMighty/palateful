"""POST /v1/meals/{meal_id}/share — generate/reuse a public share token.

Mirrors the shape of `ShareRecipe` (services/api/src/api/v1/recipe/share_recipe.py)
verbatim: same `secrets.token_urlsafe(15)` helper, same `{token, deep_link}`
response, same owner/editor gate. The one behavioural difference is that
this endpoint is idempotent — re-POSTing returns the existing token with a
200 instead of rotating it.
"""

import secrets

from api.v1.meal._access import require_meal_write
from schemas.meal import ShareMealResponse
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User


class ShareMeal(AsyncEndpoint):
    """Generate (or return the existing) public share token for a Meal."""

    async def execute(self, meal_id: str):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)
        if meal.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Meal not found",
                code=ErrorCode.MEAL_NOT_FOUND,
            )

        if meal.share_token is None:
            meal.share_token = secrets.token_urlsafe(15)
            await db.commit()
            await db.refresh(meal)
            status = 201
        else:
            status = 200

        return success(
            data=ShareMealResponse(
                token=meal.share_token,
                deep_link=f"palateful://meal-public/{meal.share_token}",
            ),
            status=status,
        )
