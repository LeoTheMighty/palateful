"""User endpoint implementations."""

from api.v1.user.check_username import CheckUsername
from api.v1.user.complete_onboarding import CompleteOnboarding
from api.v1.user.export_recipes import ExportRecipes
from api.v1.user.get_me import GetMe
from api.v1.user.push_tokens import (
    GetNotificationPreferences,
    RegisterPushToken,
    UnregisterPushToken,
    UpdateNotificationPreferences,
)
from api.v1.user.search_users import SearchUsers
from api.v1.user.set_default_recipe_book import SetDefaultRecipeBook
from api.v1.user.set_default_shopping_list import SetDefaultShoppingList
from api.v1.user.set_username import SetUsername
from api.v1.user.update_me import UpdateMe

__all__ = [
    "GetMe",
    "CompleteOnboarding",
    "ExportRecipes",
    "RegisterPushToken",
    "UnregisterPushToken",
    "UpdateNotificationPreferences",
    "GetNotificationPreferences",
    "SetDefaultRecipeBook",
    "SetDefaultShoppingList",
    "SetUsername",
    "CheckUsername",
    "SearchUsers",
    "UpdateMe",
]
