"""SQLAlchemy models."""

from utils.models.base import Base
from utils.models.joins_base import JoinsBase
from utils.models.chat import Chat
from utils.models.cooking_log import CookingLog
from utils.models.ingredient import Ingredient
from utils.models.ingredient_substitution import IngredientSubstitution
from utils.models.notification import Notification
from utils.models.pantry import Pantry
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.pantry_user import PantryUser
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
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
    # Ingredient
    "Ingredient",
    "IngredientSubstitution",
    # Units
    "Unit",
    # Logs
    "CookingLog",
]
