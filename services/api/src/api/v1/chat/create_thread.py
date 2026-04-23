"""Create a new AI chat thread."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.thread import Thread
from utils.models.user import User


class CreateThread(AsyncEndpoint):
    """Create a new conversation thread."""

    async def execute(self, params: "CreateThread.Params"):
        user: User = self.user
        thread = Thread(user_id=user.id, title=params.title)
        await self.database.create(thread)
        return success(
            data=CreateThread.Response(
                id=str(thread.id),
                title=thread.title,
                created_at=thread.created_at,
                message_count=0,
            ),
            status=201,
        )

    class Params(BaseModel):
        title: str | None = None

    class Response(BaseModel):
        id: str
        title: str | None
        created_at: datetime
        message_count: int
