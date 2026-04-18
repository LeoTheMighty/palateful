"""Meal endpoint implementations (mcv-2 + mcv-3)."""

from api.v1.meal.add_recipe_to_meal import AddRecipeToMeal
from api.v1.meal.archive_meal import ArchiveMeal
from api.v1.meal.create_meal import CreateMeal
from api.v1.meal.favorite_meal import FavoriteMeal, UnfavoriteMeal
from api.v1.meal.get_meal import GetMeal
from api.v1.meal.list_meals import ListMeals
from api.v1.meal.list_meals_in_book import ListMealsInBook
from api.v1.meal.remove_recipe_from_meal import RemoveRecipeFromMeal
from api.v1.meal.reorder_meal_components import ReorderMealComponents
from api.v1.meal.restore_meal import RestoreMeal
from api.v1.meal.update_meal import UpdateMeal

__all__ = [
    "AddRecipeToMeal",
    "ArchiveMeal",
    "CreateMeal",
    "FavoriteMeal",
    "UnfavoriteMeal",
    "GetMeal",
    "ListMeals",
    "ListMealsInBook",
    "RemoveRecipeFromMeal",
    "ReorderMealComponents",
    "RestoreMeal",
    "UpdateMeal",
]
