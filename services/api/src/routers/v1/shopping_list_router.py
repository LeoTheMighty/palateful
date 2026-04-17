"""Shopping list endpoints router."""

import json

from api.v1.shopping_list import (
    AddShoppingListItem,
    AssignItem,
    BulkAssignItems,
    CreateShoppingList,
    DeleteShoppingList,
    DeleteShoppingListItem,
    GenerateFromMealEvent,
    GetShoppingList,
    GetShoppingListDeadlines,
    GetShoppingListEvents,
    GetStoreSections,
    InviteShoppingListMember,
    JoinShoppingList,
    ListShoppingListMembers,
    ListShoppingLists,
    OrganizeByStore,
    PopulateFromCalendar,
    PopulateFromRecipe,
    RemoveShoppingListMember,
    ShareShoppingList,
    UpdateShoppingList,
    UpdateShoppingListItem,
    UpdateShoppingListMember,
    broadcast_event_to_list,
    shopping_list_websocket_handler,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, WebSocket
from utils.models.user import User
from utils.services.database import Database

shopping_list_router = APIRouter(tags=["shopping-lists"])


# ============================================================
# Core CRUD Endpoints
# ============================================================


@shopping_list_router.get("/shopping-lists")
async def list_shopping_lists(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List shopping lists for the current user (owned and shared)."""
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
    """Delete a shopping list (owner only)."""
    return DeleteShoppingList.call(
        list_id=list_id,
        user=user,
        database=database,
    )


# ============================================================
# Item Endpoints
# ============================================================


@shopping_list_router.post("/shopping-lists/{list_id}/items")
async def add_shopping_list_item(
    list_id: str,
    params: AddShoppingListItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add an item to a shopping list."""
    result = AddShoppingListItem.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )
    item_data = json.loads(result.body)
    await broadcast_event_to_list(list_id, "item_added", item_data, user_id=str(user.id))
    return result


@shopping_list_router.put("/shopping-lists/{list_id}/items/{item_id}")
async def update_shopping_list_item(
    list_id: str,
    item_id: str,
    params: UpdateShoppingListItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a shopping list item."""
    result = UpdateShoppingListItem.call(
        list_id=list_id,
        item_id=item_id,
        params=params,
        user=user,
        database=database,
    )
    item_data = json.loads(result.body)
    event_type = "item_checked" if params.is_checked is not None else "item_updated"
    await broadcast_event_to_list(list_id, event_type, item_data, user_id=str(user.id))
    return result


@shopping_list_router.delete("/shopping-lists/{list_id}/items/{item_id}")
async def delete_shopping_list_item(
    list_id: str,
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete a shopping list item."""
    result = DeleteShoppingListItem.call(
        list_id=list_id,
        item_id=item_id,
        user=user,
        database=database,
    )
    await broadcast_event_to_list(
        list_id, "item_removed", {"item_id": item_id}, user_id=str(user.id)
    )
    return result


# ============================================================
# Store Organization
# ============================================================


@shopping_list_router.get("/shopping-lists/store-sections")
async def get_store_sections(  # pragma: no cover — route shadowed by /{list_id}
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get available store sections for organizing shopping lists."""
    return GetStoreSections.call(
        user=user,
        database=database,
    )


@shopping_list_router.post("/shopping-lists/{list_id}/organize-by-store")
async def organize_by_store(
    list_id: str,
    params: OrganizeByStore.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Organize shopping list items by store section."""
    return OrganizeByStore.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


# ============================================================
# Item Assignment
# ============================================================


@shopping_list_router.put("/shopping-lists/{list_id}/items/{item_id}/assign")
async def assign_item(
    list_id: str,
    item_id: str,
    params: AssignItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Assign a shopping list item to a specific user."""
    return AssignItem.call(
        list_id=list_id,
        item_id=item_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.post("/shopping-lists/{list_id}/items/bulk-assign")
async def bulk_assign_items(
    list_id: str,
    params: BulkAssignItems.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Bulk assign shopping list items to users."""
    return BulkAssignItems.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


# ============================================================
# Meal Event Integration
# ============================================================


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


@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-recipe")
async def populate_shopping_list_from_recipe(
    list_id: str,
    params: PopulateFromRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add all ingredients from a recipe to an existing shopping list."""
    result = PopulateFromRecipe.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )
    response_data = json.loads(result.body)
    for item in response_data.get("items", []):
        await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
    return result


@shopping_list_router.post("/shopping-lists/{list_id}/populate-from-calendar")
async def populate_from_calendar(
    list_id: str,
    params: PopulateFromCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Populate a shopping list with ingredients from upcoming meal events."""
    result = PopulateFromCalendar.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )
    response_data = json.loads(result.body)
    for item in response_data.get("items", []):
        await broadcast_event_to_list(list_id, "item_added", item, user_id=str(user.id))
    return result


# ============================================================
# Deadline & Urgency Endpoints
# ============================================================


@shopping_list_router.get("/shopping-lists/{list_id}/deadlines")
async def get_shopping_list_deadlines(
    list_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get shopping list items grouped by deadline urgency."""
    return GetShoppingListDeadlines.call(
        list_id=list_id,
        user=user,
        database=database,
    )


# ============================================================
# Sharing Endpoints
# ============================================================


@shopping_list_router.post("/shopping-lists/{list_id}/share")
async def share_shopping_list(
    list_id: str,
    params: ShareShoppingList.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate a share code for a shopping list."""
    return ShareShoppingList.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.post("/shopping-lists/join/{share_code}")
async def join_shopping_list(
    share_code: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Join a shopping list using a share code."""
    return JoinShoppingList.call(
        share_code=share_code,
        user=user,
        database=database,
    )


@shopping_list_router.post("/shopping-lists/{list_id}/members")
async def invite_shopping_list_member(
    list_id: str,
    params: InviteShoppingListMember.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Invite a member to a shopping list by email or user ID."""
    return InviteShoppingListMember.call(
        list_id=list_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.get("/shopping-lists/{list_id}/members")
async def list_shopping_list_members(
    list_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get all members of a shopping list."""
    return ListShoppingListMembers.call(
        list_id=list_id,
        user=user,
        database=database,
    )


@shopping_list_router.put("/shopping-lists/{list_id}/members/{member_user_id}")
async def update_shopping_list_member(
    list_id: str,
    member_user_id: str,
    params: UpdateShoppingListMember.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a member's role or notification settings."""
    return UpdateShoppingListMember.call(
        list_id=list_id,
        member_user_id=member_user_id,
        params=params,
        user=user,
        database=database,
    )


@shopping_list_router.delete("/shopping-lists/{list_id}/members/{member_user_id}")
async def remove_shopping_list_member(
    list_id: str,
    member_user_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Remove a member from a shopping list (or leave)."""
    return RemoveShoppingListMember.call(
        list_id=list_id,
        member_user_id=member_user_id,
        user=user,
        database=database,
    )


# ============================================================
# Real-Time Sync Endpoints
# ============================================================


@shopping_list_router.get("/shopping-lists/{list_id}/events")
async def get_shopping_list_events(
    list_id: str,
    since_sequence: int = 0,
    limit: int = 100,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get shopping list events for sync/catch-up."""
    return GetShoppingListEvents.call(
        list_id=list_id,
        since_sequence=since_sequence,
        limit=limit,
        user=user,
        database=database,
    )


@shopping_list_router.websocket("/ws/shopping-lists/{list_id}")
async def shopping_list_websocket(
    websocket: WebSocket,
    list_id: str,
    database: Database = Depends(get_database),
):
    """
    WebSocket endpoint for real-time shopping list sync.

    Connect with: ws://host/v1/ws/shopping-lists/{list_id}?token=JWT

    Message types from client:
    - presence: {"type": "presence", "status": "shopping"|"viewing"}
    - sync_request: {"type": "sync_request", "since_sequence": 0}
    - ping: {"type": "ping"}

    Message types from server:
    - sync_response: Full state with events
    - item_added/updated/checked/removed: Item changes
    - member_joined/left: Membership changes
    - presence_update: User status changes
    - pong: Response to ping
    """
    # Get token from query params for WebSocket auth
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Validate the JWT against Auth0 the same way HTTP routes do. We can't
    # reuse `get_current_user` directly because it pulls the Authorization
    # header via FastAPI's Depends; the WS handshake carries the token in
    # the query string instead.
    try:  # pragma: no cover — WS auth
        from utils.services.auth0 import get_auth0_verifier

        verifier = get_auth0_verifier()
        payload = await verifier.verify_token(token)
        user = database.find_by(User, auth0_id=payload.get("sub"))
        if not user:
            await websocket.close(code=4001, reason="Invalid user")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Handle WebSocket connection
    await shopping_list_websocket_handler(  # pragma: no cover — WS auth
        websocket=websocket,
        list_id=list_id,
        user=user,
        db=database.db,
    )
