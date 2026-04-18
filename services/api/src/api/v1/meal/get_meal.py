"""GET /v1/meals/{meal_id}."""

from api.v1.meal._access import require_meal_read
from api.v1.meal._response import build_meal_response
from utils.api.endpoint import Endpoint, success
from utils.models.user import User


class GetMeal(Endpoint):
    """Return a Meal with hydrated components (with availability marking)."""

    def execute(self, meal_id: str):
        user: User = self.user
        db = self.db

        meal = require_meal_read(db, meal_id, user)
        return success(data=build_meal_response(meal, db=db, user_id=user.id))
