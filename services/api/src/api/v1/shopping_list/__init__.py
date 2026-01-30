"""Shopping list endpoints."""

from .add_item import AddShoppingListItem
from .assign_item import AssignItem, BulkAssignItems
from .create_shopping_list import CreateShoppingList
from .delete_item import DeleteShoppingListItem
from .delete_shopping_list import DeleteShoppingList
from .generate_from_meal_event import GenerateFromMealEvent
from .get_deadlines import GetShoppingListDeadlines
from .get_events import GetShoppingListEvents
from .get_shopping_list import GetShoppingList
from .invite_member import InviteShoppingListMember
from .join_shopping_list import JoinShoppingList
from .list_members import ListShoppingListMembers
from .list_shopping_lists import ListShoppingLists
from .organize_by_store import GetStoreSections, OrganizeByStore
from .populate_from_calendar import PopulateFromCalendar
from .remove_member import RemoveShoppingListMember
from .share_shopping_list import ShareShoppingList
from .update_item import UpdateShoppingListItem
from .update_member import UpdateShoppingListMember
from .update_shopping_list import UpdateShoppingList
from .websocket import broadcast_event_to_list, shopping_list_websocket_handler

__all__ = [
    # Core CRUD
    "CreateShoppingList",
    "GetShoppingList",
    "ListShoppingLists",
    "UpdateShoppingList",
    "DeleteShoppingList",
    # Item operations
    "AddShoppingListItem",
    "UpdateShoppingListItem",
    "DeleteShoppingListItem",
    "GenerateFromMealEvent",
    "AssignItem",
    "BulkAssignItems",
    # Sharing endpoints
    "ShareShoppingList",
    "JoinShoppingList",
    "InviteShoppingListMember",
    "ListShoppingListMembers",
    "UpdateShoppingListMember",
    "RemoveShoppingListMember",
    # Deadline system
    "PopulateFromCalendar",
    "GetShoppingListDeadlines",
    # Store organization
    "OrganizeByStore",
    "GetStoreSections",
    # Real-time sync
    "GetShoppingListEvents",
    "shopping_list_websocket_handler",
    "broadcast_event_to_list",
]
