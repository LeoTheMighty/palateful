"""SQLAlchemy models."""

from utils.models.active_timer import ActiveTimer
from utils.models.activity import Activity
from utils.models.base import Base
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.chat import Chat
from utils.models.cooking_log import CookingLog
from utils.models.error_log import ErrorLog
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.ingredient import Ingredient
from utils.models.ingredient_match import IngredientMatch
from utils.models.ingredient_substitution import IngredientSubstitution
from utils.models.invitation import Invitation
from utils.models.invite_link import InviteLink
from utils.models.joins_base import JoinsBase
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.notification import Notification
from utils.models.pantry import Pantry
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.pantry_ingredient_event import PantryIngredientEvent
from utils.models.pantry_user import PantryUser
from utils.models.parser_batch import ParserBatch
from utils.models.parser_job import ParserJob
from utils.models.prep_step import PrepStep
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_note import RecipeNote
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_event import ShoppingListEvent
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.suggestion import Suggestion
from utils.models.thread import Thread
from utils.models.unit import Unit
from utils.models.user import User
from utils.models.user_activity import UserActivity
from utils.models.user_favorite import UserFavorite

__all__ = [
    # Base classes
    "Base",
    "JoinsBase",
    # Core
    "User",
    # Collaboration
    "Invitation",
    "InviteLink",
    "Activity",
    # Social/Friends
    "FriendRequest",
    "Friendship",
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
    "PantryIngredientEvent",
    # Recipe Book
    "RecipeBook",
    "RecipeBookUser",
    # Recipe
    "Recipe",
    "RecipeIngredient",
    "RecipeNote",
    "RecipeStep",
    "RecipeVersion",
    # Ingredient
    "Ingredient",
    "IngredientSubstitution",
    "IngredientMatch",
    # Units
    "Unit",
    # Logs
    "CookingLog",
    "ErrorLog",
    # Calendar/Meal Planning
    "Calendar",
    "CalendarUser",
    "MealEvent",
    "MealEventParticipant",
    "MealRecurrenceRule",
    "PrepStep",
    "ShoppingList",
    "ShoppingListItem",
    "ShoppingListUser",
    "ShoppingListEvent",
    "ActiveTimer",
    # Import System
    "ImportJob",
    "ImportItem",
    # Parser System
    "ParserBatch",
    "ParserJob",
    # Favorites
    "UserActivity",
    "UserFavorite",
]
