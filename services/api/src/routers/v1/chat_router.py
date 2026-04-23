"""Chat router — AI conversation threads and streaming messages.

aam-21 partial flip: `create/list/get/delete` thread endpoints now use
the async DB + auth deps. `send_message` stays sync — the agent loop
calls sync `provider.chat(...)` (openai), sync `tool.execute(...)`, and
manipulates a sync Database from within the SSE generator. Converting
it is blocked on aam-7 (openai async) + agent-tool async rewrite and
is left to a follow-up story.
"""

from api.v1.chat import (
    CreateThread,
    DeleteThread,
    GetThread,
    ListThreads,
    SendMessageParams,
    send_message_stream,
)
from dependencies import (
    get_async_database,
    get_current_user,
    get_current_user_async,
    get_database,
)
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
from utils.services.database import Database

chat_router = APIRouter(tags=["chat"])


@chat_router.post("/chat/threads", status_code=201)
async def create_thread(
    params: CreateThread.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Create a new AI conversation thread."""
    return await CreateThread.call(params=params, user=user, database=database)


@chat_router.get("/chat/threads")
async def list_threads(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List all conversation threads for the current user."""
    return await ListThreads.call(
        limit=limit, offset=offset, user=user, database=database
    )


@chat_router.get("/chat/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get a thread with all its messages."""
    return await GetThread.call(
        thread_id=thread_id, user=user, database=database
    )


@chat_router.delete("/chat/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Soft-delete a conversation thread."""
    return await DeleteThread.call(
        thread_id=thread_id, user=user, database=database
    )


@chat_router.post("/chat/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    params: SendMessageParams,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Send a message and receive an SSE stream of the AI response.

    Intentionally sync — SSE generator chains sync OpenAI + sync agent
    tool.execute calls. Follow-up story converts this alongside aam-7
    (openai async) and the agent-tool async rewrite.
    """
    return await send_message_stream(thread_id, params, user, database)
