"""Shared Meal auth helpers.

Kept inside `api/v1/meal/` (not `services/api/src/dependencies.py`) so
the access checks are co-located with the handlers that use them. The
existing `dependencies.py` is a flat module, not a package, so splitting
a `dependencies/meal_access.py` out would fight the import layout.
"""

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.services.meal_service import MealService


def require_meal_read(db, meal_id: str, user) -> Meal:
    """Load a Meal and assert the user has read membership on its book."""
    service = MealService(db)
    meal = service.get_with_components(meal_id)
    if meal is None:
        raise APIException(
            status_code=404,
            detail="Meal not found",
            code=ErrorCode.MEAL_NOT_FOUND,
        )
    if not service.user_has_book_read(user.id, meal.recipe_book_id):
        raise APIException(
            status_code=403,
            detail="You don't have access to this meal",
            code=ErrorCode.MEAL_ACCESS_DENIED,
        )
    return meal


def require_meal_write(db, meal_id: str, user) -> Meal:
    """Load a Meal and assert write-level (owner/editor) membership."""
    service = MealService(db)
    meal = service.get_with_components(meal_id)
    if meal is None:
        raise APIException(
            status_code=404,
            detail="Meal not found",
            code=ErrorCode.MEAL_NOT_FOUND,
        )
    if not service.user_has_book_write(user.id, meal.recipe_book_id):
        raise APIException(
            status_code=403,
            detail="You don't have permission to modify this meal",
            code=ErrorCode.MEAL_ACCESS_DENIED,
        )
    return meal


def require_book_write(db, book_id: str, user) -> None:
    """Assert write-level membership on a recipe_book (for create)."""
    service = MealService(db)
    if not service.user_has_book_write(user.id, book_id):
        raise APIException(
            status_code=403,
            detail="You don't have permission to modify this recipe book",
            code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
        )
