"""SQLAlchemy models."""

from utils.models.base import Base
from utils.models.joins_base import JoinsBase
from utils.models.active_timer import ActiveTimer
from utils.models.chat import Chat
from utils.models.cooking_log import CookingLog
from utils.models.ingredient import Ingredient
from utils.models.ingredient_substitution import IngredientSubstitution
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.notification import Notification
from utils.models.pantry import Pantry
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.pantry_user import PantryUser
from utils.models.prep_step import PrepStep
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.suggestion import Suggestion
from utils.models.thread import Thread
from utils.models.unit import Unit
from utils.models.user import User

__all__ = [
    # Base classes
    "Base",
    "JoinsBase",
    # Core
    "User",
    # Chat/AI
    "Thread",
    "Chat",
    # Agent
    "Suggestion",
    "Notification",
    # Pantry
    "Pantry",
    "PantryUser",
    "PantryIngredient",
    # Recipe Book
    "RecipeBook",
    "RecipeBookUser",
    # Recipe
    "Recipe",
    "RecipeIngredient",
    "RecipeStep",
    # Ingredient
    "Ingredient",
    "IngredientSubstitution",
    # Units
    "Unit",
    # Logs
    "CookingLog",
    # Calendar/Meal Planning
    "MealEvent",
    "MealEventParticipant",
    "PrepStep",
    "ShoppingList",
    "ShoppingListItem",
    "ActiveTimer",
]
