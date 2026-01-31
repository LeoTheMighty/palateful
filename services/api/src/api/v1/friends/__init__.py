"""Friends API endpoints."""

from api.v1.friends.accept_request import AcceptFriendRequest
from api.v1.friends.cancel_request import CancelFriendRequest
from api.v1.friends.decline_request import DeclineFriendRequest
from api.v1.friends.get_friend import GetFriend
from api.v1.friends.list_friends import ListFriends
from api.v1.friends.list_requests import ListFriendRequests
from api.v1.friends.remove_friend import RemoveFriend
from api.v1.friends.send_request import SendFriendRequest

__all__ = [
    "SendFriendRequest",
    "ListFriendRequests",
    "AcceptFriendRequest",
    "DeclineFriendRequest",
    "CancelFriendRequest",
    "ListFriends",
    "RemoveFriend",
    "GetFriend",
]
