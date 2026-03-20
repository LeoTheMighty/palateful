"""SSE endpoint for sending a message to the AI chat agent."""

import json

from api.v1.chat.agent_loop import run_chat_agent
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from utils.models.thread import Thread


class SendMessageParams(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    recipe_context: str | None = Field(None, max_length=5_000)


async def send_message_stream(
    thread_id: str,
    params: SendMessageParams,
    user,
    database,
) -> StreamingResponse:
    """Validate ownership and return an SSE StreamingResponse."""
    thread = database.find_by(Thread, id=thread_id)
    if not thread or str(thread.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Thread not found")

    async def event_generator():
        try:
            async for event in run_chat_agent(
                thread_id=thread_id,
                user_message=params.message,
                user=user,
                database=database,
                recipe_context=params.recipe_context,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
