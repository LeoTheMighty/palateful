"""List AI chat threads for the current user."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.thread import Thread
from utils.models.user import User


class ListThreads(AsyncEndpoint):
    """List all non-archived threads for the current user."""

    async def execute(self, limit: int = 20, offset: int = 0):
        user: User = self.user
        db = self.database.db

        query = (
            select(Thread)
            .options(selectinload(Thread.chats))
            .where(Thread.user_id == user.id)
            .where(Thread.archived_at.is_(None))
            .order_by(Thread.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        threads = result.scalars().all()

        items = []
        for thread in threads:
            last_message = None
            if thread.chats:
                last_chat = thread.chats[-1]
                last_message = (last_chat.content or "")[:120]
            items.append(
                ListThreads.ThreadSummary(
                    id=str(thread.id),
                    title=thread.title,
                    created_at=thread.created_at,
                    message_count=len(thread.chats),
                    last_message=last_message,
                )
            )

        return success(data=ListThreads.Response(items=items, total=len(items)))

    class ThreadSummary(BaseModel):
        id: str
        title: str | None
        created_at: datetime
        message_count: int
        last_message: str | None

    class Response(BaseModel):
        items: list["ListThreads.ThreadSummary"]
        total: int
