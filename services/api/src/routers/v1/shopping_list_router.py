"""Shopping list endpoints router."""


from api.v1.shopping_list import (
    AddShoppingListItem,
    CreateShoppingList,
    DeleteShoppingList,
    DeleteShoppingListItem,
    GenerateFromMealEvent,
    GetShoppingList,
    ListShoppingLists,
    UpdateShoppingList,
    UpdateShoppingListItem,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

shopping_list_router = APIRouter(tags=["shopping-lists"])


@shopping_list_router.get("/shopping-lists")
async def list_shopping_lists(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List shopping lists for the current user."""
    return ListShoppingLists.call(
        limit=limit,
        offset=offset,
        status=status,
        user=user,
        database=database,
    )


@shopping_list_router.post("/shopping-lists")
async def create_shopping_list(
    params: CreateShoppingList.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new shopping list."""
    return CreateShoppingList.call(
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.get("/shopping-lists/{list_id}")
async def get_shopping_list(
    list_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get shopping list details."""
    return GetShoppingList.call(
        list_id=list_id,
        user=user,
        database=database,
    )


@shopping_list_router.put("/shopping-lists/{list_id}")
async def update_shopping_list(
    list_id: str,
    params: UpdateShoppingList.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a shopping list."""
    return UpdateShoppingList.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.delete("/shopping-lists/{list_id}")
async def delete_shopping_list(
    list_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete a shopping list."""
    return DeleteShoppingList.call(
        list_id=list_id,
        user=user,
        database=database,
    )


# Shopping list items
@shopping_list_router.post("/shopping-lists/{list_id}/items")
async def add_shopping_list_item(
    list_id: str,
    params: AddShoppingListItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add an item to a shopping list."""
    return AddShoppingListItem.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.put("/shopping-lists/{list_id}/items/{item_id}")
async def update_shopping_list_item(
    list_id: str,
    item_id: str,
    params: UpdateShoppingListItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a shopping list item."""
    return UpdateShoppingListItem.call(
        list_id=list_id,
        item_id=item_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.delete("/shopping-lists/{list_id}/items/{item_id}")
async def delete_shopping_list_item(
    list_id: str,
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete a shopping list item."""
    return DeleteShoppingListItem.call(
        list_id=list_id,
        item_id=item_id,
        user=user,
        database=database,
    )


# Generate from meal event
@shopping_list_router.post("/meal-events/{event_id}/shopping-list/generate")
async def generate_shopping_list(
    event_id: str,
    params: GenerateFromMealEvent.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate a shopping list from a meal event's recipe."""
    return GenerateFromMealEvent.call(
        event_id=event_id,
        params=params,
        user=user,
        database=database,
    )
