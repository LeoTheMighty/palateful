"""Meal endpoint implementations."""

from api.v1.meal.archive_meal import ArchiveMeal
from api.v1.meal.create_meal import CreateMeal
from api.v1.meal.get_meal import GetMeal
from api.v1.meal.list_meals import ListMeals
from api.v1.meal.list_meals_in_book import ListMealsInBook
from api.v1.meal.restore_meal import RestoreMeal
from api.v1.meal.update_meal import UpdateMeal

__all__ = [
    "ArchiveMeal",
    "CreateMeal",
    "GetMeal",
    "ListMeals",
    "ListMealsInBook",
    "RestoreMeal",
    "UpdateMeal",
]
