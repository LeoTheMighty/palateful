"""Get a single AI chat thread with all messages."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.thread import Thread
from utils.models.user import User


class GetThread(Endpoint):
    """Get a thread with all its chat messages."""

    def execute(self, thread_id: str):
        user: User = self.user
        thread = self.database.find_by(Thread, id=thread_id)
        if not thread or str(thread.user_id) != str(user.id):
            raise APIException(
                status_code=404,
                detail="Thread not found",
                code=ErrorCode.THREAD_NOT_FOUND,
            )

        messages = [
            GetThread.ChatMessage(
                id=str(chat.id),
                role=chat.role,
                content=chat.content,
                tool_calls=chat.tool_calls,
                tool_call_id=chat.tool_call_id,
                tool_name=chat.tool_name,
                prompt_tokens=chat.prompt_tokens,
                completion_tokens=chat.completion_tokens,
                model=chat.model,
                created_at=chat.created_at,
            )
            for chat in thread.chats
        ]

        return success(
            data=GetThread.Response(
                id=str(thread.id),
                title=thread.title,
                created_at=thread.created_at,
                messages=messages,
            )
        )

    class ChatMessage(BaseModel):
        id: str
        role: str
        content: str | None
        tool_calls: Any | None
        tool_call_id: str | None
        tool_name: str | None
        prompt_tokens: int | None
        completion_tokens: int | None
        model: str | None
        created_at: datetime

    class Response(BaseModel):
        id: str
        title: str | None
        created_at: datetime
        messages: list["GetThread.ChatMessage"]
