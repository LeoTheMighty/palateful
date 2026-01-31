"""Friends endpoints router."""

from api.v1.friends import (
    AcceptFriendRequest,
    CancelFriendRequest,
    DeclineFriendRequest,
    GetFriend,
    ListFriendRequests,
    ListFriends,
    RemoveFriend,
    SendFriendRequest,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

friends_router = APIRouter(prefix="/friends", tags=["friends"])


# ============================================================
# Friend Requests (defined first to avoid route conflicts)
# ============================================================


@friends_router.get("/requests")
async def list_friend_requests(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all pending friend requests (sent and received)."""
    return ListFriendRequests.call(user=user, database=database)


# ============================================================
# Friends List
# ============================================================


@friends_router.get("")
async def list_friends(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all friends."""
    return ListFriends.call(user=user, database=database)


@friends_router.get("/{friend_id}")
async def get_friend(
    friend_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a friend's profile."""
    return GetFriend.call(friend_id=friend_id, user=user, database=database)


@friends_router.delete("/{friend_id}")
async def remove_friend(
    friend_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Remove a friend."""
    return RemoveFriend.call(friend_id=friend_id, user=user, database=database)


@friends_router.post("/requests")
async def send_friend_request(
    params: SendFriendRequest.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Send a friend request."""
    return SendFriendRequest.call(params=params, user=user, database=database)


@friends_router.post("/requests/{request_id}/accept")
async def accept_friend_request(
    request_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Accept a friend request."""
    return AcceptFriendRequest.call(request_id=request_id, user=user, database=database)


@friends_router.post("/requests/{request_id}/decline")
async def decline_friend_request(
    request_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Decline a friend request."""
    return DeclineFriendRequest.call(
        request_id=request_id, user=user, database=database
    )


@friends_router.delete("/requests/{request_id}")
async def cancel_friend_request(
    request_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Cancel a sent friend request."""
    return CancelFriendRequest.call(
        request_id=request_id, user=user, database=database
    )
