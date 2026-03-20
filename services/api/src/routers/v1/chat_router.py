"""Chat router — AI conversation threads and streaming messages."""

from api.v1.chat import (
    CreateThread,
    DeleteThread,
    GetThread,
    ListThreads,
    SendMessageParams,
    send_message_stream,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

chat_router = APIRouter(tags=["chat"])


@chat_router.post("/chat/threads", status_code=201)
async def create_thread(
    params: CreateThread.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new AI conversation thread."""
    return CreateThread.call(params=params, user=user, database=database)


@chat_router.get("/chat/threads")
async def list_threads(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all conversation threads for the current user."""
    return ListThreads.call(limit=limit, offset=offset, user=user, database=database)


@chat_router.get("/chat/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a thread with all its messages."""
    return GetThread.call(thread_id=thread_id, user=user, database=database)


@chat_router.delete("/chat/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Soft-delete a conversation thread."""
    return DeleteThread.call(thread_id=thread_id, user=user, database=database)


@chat_router.post("/chat/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    params: SendMessageParams,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Send a message and receive an SSE stream of the AI response."""
    return await send_message_stream(thread_id, params, user, database)
