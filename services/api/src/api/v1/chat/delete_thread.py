"""Soft-delete an AI chat thread."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.thread import Thread
from utils.models.user import User


class DeleteThread(AsyncEndpoint):
    """Soft-delete a thread by setting archived_at."""

    async def execute(self, thread_id: str):
        user: User = self.user
        thread = await self.database.find_by(Thread, id=thread_id)
        if not thread or str(thread.user_id) != str(user.id):
            raise APIException(
                status_code=404,
                detail="Thread not found",
                code=ErrorCode.THREAD_NOT_FOUND,
            )

        thread.archived_at = datetime.now(UTC)
        await self.database.db.commit()
        return success(data=DeleteThread.Response(deleted=True))

    class Response(BaseModel):
        deleted: bool
