"""Search users by username endpoint."""

from pydantic import BaseModel
from sqlalchemy import or_, select
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.user import User


class SearchUsers(Endpoint):
    """Search for users by username or name."""

    def execute(self, q: str, limit: int = 20):
        """
        Search users by username (with or without @ prefix).
        Returns matching users with their friendship status relative to current user.
        """
        user: User = self.user

        # Clean up search query
        query = q.strip()
        if not query:
            raise APIException(
                status_code=400,
                detail="Search query is required",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Remove @ prefix if present
        if query.startswith("@"):
            query = query[1:]

        query = query.lower()

        # Limit results
        limit = min(limit, 50)

        # Search by username (exact prefix match) or name (contains)
        search_results = self.db.execute(
            select(User)
            .where(
                User.id != user.id,  # Exclude current user
                User.username.isnot(None),  # Only users with usernames
                or_(
                    User.username.startswith(query),
                    User.name.ilike(f"%{query}%"),
                ),
            )
            .order_by(
                # Prioritize exact username matches
                (User.username == query).desc(),
                # Then prefix matches
                User.username.startswith(query).desc(),
                User.username,
            )
            .limit(limit)
        ).scalars().all()

        # Get friendship status for all results
        user_ids = [u.id for u in search_results]

        # Get existing friendships
        friendships = set(
            self.db.execute(
                select(Friendship.friend_id).where(
                    Friendship.user_id == user.id,
                    Friendship.friend_id.in_(user_ids),
                )
            ).scalars().all()
        )

        # Get pending friend requests (both sent and received)
        sent_requests = {
            r.to_user_id: r.id
            for r in self.db.execute(
                select(FriendRequest).where(
                    FriendRequest.from_user_id == user.id,
                    FriendRequest.to_user_id.in_(user_ids),
                    FriendRequest.status == "pending",
                )
            ).scalars().all()
        }

        received_requests = {
            r.from_user_id: r.id
            for r in self.db.execute(
                select(FriendRequest).where(
                    FriendRequest.to_user_id == user.id,
                    FriendRequest.from_user_id.in_(user_ids),
                    FriendRequest.status == "pending",
                )
            ).scalars().all()
        }

        # Build response
        results = []
        for u in search_results:
            # Determine friendship status
            if u.id in friendships:
                status = "friends"
                request_id = None
            elif u.id in sent_requests:
                status = "request_sent"
                request_id = str(sent_requests[u.id])
            elif u.id in received_requests:
                status = "request_received"
                request_id = str(received_requests[u.id])
            else:
                status = "none"
                request_id = None

            results.append(
                SearchUsers.UserResult(
                    id=str(u.id),
                    username=u.username,
                    name=u.name,
                    picture=u.picture,
                    friendship_status=status,
                    friend_request_id=request_id,
                )
            )

        return success(
            data=SearchUsers.Response(
                results=results,
                count=len(results),
            )
        )

    class UserResult(BaseModel):
        """A single user result."""

        id: str
        username: str | None
        name: str | None
        picture: str | None
        friendship_status: str  # "none", "friends", "request_sent", "request_received"
        friend_request_id: str | None = None

    class Response(BaseModel):
        """Response model."""

        results: list["SearchUsers.UserResult"]
        count: int
