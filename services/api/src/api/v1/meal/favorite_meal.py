"""POST/DELETE /v1/meals/{meal_id}/favorite — toggle per-user favorite.

Two endpoints (Favorite / Unfavorite) rather than a single toggle so the
client can drive optimistic UI without read-back roundtrips. Both are
idempotent (double-favorite / double-unfavorite is a no-op).
"""

from api.v1.meal._access import require_meal_read
from schemas.meal import MealFavoriteResponse
from utils.api.endpoint import Endpoint, success
from utils.models.user import User
from utils.services.meal_service import MealService


class FavoriteMeal(Endpoint):
    def execute(self, meal_id: str):
        user: User = self.user
        db = self.db

        require_meal_read(db, meal_id, user)
        MealService(db).set_favorite(
            user_id=user.id, meal_id=meal_id, favorite=True
        )
        db.commit()
        return success(
            data=MealFavoriteResponse(is_favorite=True), status=201
        )


class UnfavoriteMeal(Endpoint):
    def execute(self, meal_id: str):
        user: User = self.user
        db = self.db

        require_meal_read(db, meal_id, user)
        MealService(db).set_favorite(
            user_id=user.id, meal_id=meal_id, favorite=False
        )
        db.commit()
        return success(data=MealFavoriteResponse(is_favorite=False))
