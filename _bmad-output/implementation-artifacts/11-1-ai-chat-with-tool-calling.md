# Story 11.1: AI Chat with Tool Calling

Status: ready-for-dev

## Story

As a user,
I want to interact with an AI assistant via text that performs real actions through tool calling,
so that I can manage my recipes conversationally instead of navigating menus.

## Acceptance Criteria

1. **SSE streaming** — Sending a message returns an SSE stream; the first token appears within 2 seconds. The response streams progressively until complete.
2. **Tool calling** — The AI can execute tool calls (at minimum: `search_recipes`) and act on the user's behalf, not just chat.
3. **Permission model** — Tool calls execute scoped to the authenticated user's data (no privilege escalation). The AI can only access what the user can access.
4. **Provider-agnostic** — The chat system uses the existing `LLMProvider` abstraction (`get_llm_provider()`) so providers can be swapped without user-facing changes.
5. **Cost tracking** — Token usage is tracked per user per Chat message (`prompt_tokens`, `completion_tokens` on the `Chat` model). A configurable per-user monthly token cap is enforced; requests exceeding the cap return a 402 error.
6. **Persistent threads** — Conversations are persisted as `Thread` + `Chat` records. The user can create threads, list threads, retrieve thread history, and delete threads via REST endpoints.
7. **Flutter chat UI** — A chat screen shows the conversation with streaming response display. The user can type a message and see the AI's response stream in. Tool call activity is indicated. The screen is accessible via a chat FAB or button on the home/recipes screen.
8. **Tests** — Backend: unit tests for chat endpoints (create thread, list threads, send message flow). Flutter: widget tests for the chat screen.

## Tasks / Subtasks

- [ ] Task 1: DB migration for threads and chats tables (AC: 6)
  - [ ] Create migration `20260320000002_add_chat_threads.py` using Alembic
  - [ ] `threads` table: id, created_at, updated_at, archived_at, title (nullable), user_id FK
  - [ ] `chats` table: id, created_at, updated_at, archived_at, role, content, tool_calls (JSONB), tool_call_id, tool_name, prompt_tokens, completion_tokens, model, thread_id FK
  - [ ] Indexes: `ix_threads_user_id`, `ix_chats_thread_id`
  - [ ] Run migration and verify: `npx nx run migrator:migrate`

- [ ] Task 2: Chat endpoint classes — CRUD for threads (AC: 6)
  - [ ] `services/api/src/api/v1/chat/create_thread.py` — `CreateThread(Endpoint)`, POST → Thread record + empty chats
  - [ ] `services/api/src/api/v1/chat/list_threads.py` — `ListThreads(Endpoint)`, GET → paginated list with last_message preview
  - [ ] `services/api/src/api/v1/chat/get_thread.py` — `GetThread(Endpoint)`, GET → full thread with all Chat messages
  - [ ] `services/api/src/api/v1/chat/delete_thread.py` — `DeleteThread(Endpoint)`, DELETE → soft-delete (set archived_at)
  - [ ] `services/api/src/api/v1/chat/__init__.py` — export all endpoint classes

- [ ] Task 3: Chat agent loop with SSE streaming (AC: 1, 2, 3, 4, 5)
  - [ ] `services/api/src/api/v1/chat/agent_loop.py` — `run_chat_agent()` async generator
  - [ ] Persist user `Chat` message to DB before calling LLM
  - [ ] Load thread history from DB and convert to `List[Message]`
  - [ ] Check per-user monthly token cap; yield `{"type": "error", "code": "token_cap_exceeded"}` + raise if exceeded
  - [ ] Round 1 (tool resolution): call `llm.chat()` synchronously with `SearchRecipesTool` defined; if `finish_reason == "tool_calls"` execute tools scoped to user_id, persist tool messages to DB, yield `{"type": "tool_call", ...}` and `{"type": "tool_result", ...}` events
  - [ ] Round 2 (final answer): call `llm.stream_chat()` (streaming) with full context including tool results; yield `{"type": "token", "content": "..."}` for each streamed chunk
  - [ ] Persist assistant `Chat` message to DB with token usage; yield `{"type": "done", "message_id": "...", "usage": {...}}`
  - [ ] Add `stream_chat()` method to `LLMProvider` base class and implement in `OpenAIProvider` using `stream=True`

- [ ] Task 4: SendMessage SSE endpoint (AC: 1, 2, 3)
  - [ ] `services/api/src/api/v1/chat/send_message.py` — NOT an `Endpoint` subclass; standalone async function returning `StreamingResponse`
  - [ ] Validate thread ownership (user must own thread_id)
  - [ ] Call `run_chat_agent()` and yield SSE events
  - [ ] SSE format: `data: {json}\n\n` with events: `token`, `tool_call`, `tool_result`, `done`, `error`
  - [ ] On stream error: yield `{"type": "error", "message": "..."}` event and close

- [ ] Task 5: Chat router and v1 registration (AC: 6)
  - [ ] `services/api/src/routers/v1/chat_router.py` — define all 5 routes (create, list, get, delete thread; send message)
  - [ ] Update `services/api/src/routers/v1_router.py` — import and include `chat_router`

- [ ] Task 6: Per-user token cap setting (AC: 5)
  - [ ] Add `ai_chat_monthly_token_cap: int = 500_000` to API service config (`services/api/src/config.py`)
  - [ ] `get_user_monthly_tokens(db, user_id)` helper: sum `prompt_tokens + completion_tokens` across `Chat` records for user in current calendar month

- [ ] Task 7: Backend tests (AC: 8)
  - [ ] `services/api/unittests/v1/test_chat.py` — test create thread, list threads, get thread, delete thread, token cap enforcement
  - [ ] Mock LLM provider for tests (avoid real API calls)
  - [ ] Run via `npx nx run api:test`

- [ ] Task 8: Flutter chat service — SSE client (AC: 7)
  - [ ] `app/lib/features/chat/chat_service.dart` — `ChatService` class using `dio` with `ResponseType.stream`
  - [ ] Parse SSE lines: split by `\n\n`, extract `data:` prefix, JSON-decode payload
  - [ ] Methods: `createThread()`, `listThreads()`, `getThread(threadId)`, `deleteThread(threadId)`, `sendMessage(threadId, text)` → `Stream<ChatEvent>`
  - [ ] `ChatEvent` sealed class: `TokenEvent(content)`, `ToolCallEvent(name)`, `ToolResultEvent(name)`, `DoneEvent(messageId)`, `ErrorEvent(message)`

- [ ] Task 9: Flutter chat Riverpod providers (AC: 7)
  - [ ] `app/lib/features/chat/chat_provider.dart` — `ThreadListNotifier`, `ThreadDetailNotifier`, `ActiveChatNotifier`
  - [ ] `ThreadListNotifier` (AsyncNotifier): load/create/delete threads
  - [ ] `ActiveChatNotifier` (AsyncNotifier): holds current thread messages; `sendMessage()` adds user message optimistically, streams and appends AI tokens to last message

- [ ] Task 10: Flutter chat screen UI (AC: 7)
  - [ ] `app/lib/features/chat/chat_screen.dart` — main chat view
  - [ ] Message list: `MessageBubble` widget for user (right-aligned) and assistant (left-aligned)
  - [ ] Streaming state: assistant bubble shows typing indicator until first token, then streams text
  - [ ] Tool call activity: show a brief "Searching recipes…" indicator between tool_call and tool_result events
  - [ ] Text input bar with send button; disabled while streaming
  - [ ] `app/lib/features/chat/widgets/message_bubble.dart` — reusable bubble widget

- [ ] Task 11: Chat entry point and routing (AC: 7)
  - [ ] Add chat route `/chat/:threadId?` to go_router config
  - [ ] Add chat FAB or toolbar action on the home screen (recipes screen) — do NOT add a 6th navigation destination to avoid breaking existing 5-destination nav tests
  - [ ] On FAB tap: auto-create a thread if none exists, navigate to chat screen

- [ ] Task 12: Flutter tests (AC: 8)
  - [ ] `app/test/features/chat/chat_screen_test.dart` — widget test: renders message bubbles, input bar, send button disabled state
  - [ ] Run full Flutter test suite to confirm no regressions: `flutter test`

## Dev Notes

### Architecture: What Exists vs What to Build

**Models — ALREADY EXIST (do not recreate):**
- `Thread` model: `libraries/utils/utils/models/thread.py` — fields: `id`, `created_at`, `updated_at`, `archived_at`, `title` (nullable), `user_id` (FK→users), `user` rel, `chats` rel
- `Chat` model: `libraries/utils/utils/models/chat.py` — fields: `role`, `content`, `tool_calls` (JSONB), `tool_call_id`, `tool_name`, `prompt_tokens`, `completion_tokens`, `model`, `thread_id` (FK→chats)
- Both models are exported from `libraries/utils/utils/models/__init__.py`

**Agent library — ALREADY EXISTS:**
- `LLMProvider` abstract class: `libraries/agent/agent/llm/provider.py`
  - `chat(messages, tools, temperature, max_tokens) → LLMResponse`
  - `generate_embedding(text) → list[float]`
- `OpenAIProvider`: `libraries/agent/agent/llm/openai.py` — uses OpenAI SDK
- `AnthropicProvider`: `libraries/agent/agent/llm/anthropic.py` — uses Anthropic SDK
- `get_llm_provider(provider_name?) → LLMProvider` factory — defaults to `settings.agent_default_provider`
- `SearchRecipesTool`: `libraries/agent/agent/tools/recipes.py` — `search_recipes` with semantic search via pgvector
- `BaseTool`: `libraries/agent/agent/tools/base.py` — `execute(db, user_id, **kwargs) → ToolResult`
- `AgentSettings`: `agent_default_provider`, `agent_model`, `agent_temperature`, `openai_api_key`, `anthropic_api_key`

**What does NOT exist yet:**
- `stream_chat()` on `LLMProvider` — need to add
- Any chat API endpoints — need to create from scratch
- `chat_router.py` — need to create
- DB migration for threads/chats tables — need to create
- Any Flutter chat UI — need to create from scratch
- No SSE/streaming anywhere in the codebase

### Backend: Endpoint Pattern

All non-SSE endpoints use this pattern:
```python
# services/api/src/api/v1/chat/create_thread.py
from datetime import datetime
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.thread import Thread
from utils.models.user import User

class CreateThread(Endpoint):
    def execute(self, params: "CreateThread.Params"):
        user: User = self.user
        thread = Thread(user_id=user.id, title=params.title)
        self.database.create(thread)
        self.database.db.refresh(thread)
        return success(data=CreateThread.Response(
            id=str(thread.id),
            title=thread.title,
            created_at=thread.created_at,
            message_count=0,
        ))

    class Params(BaseModel):
        title: str | None = None

    class Response(BaseModel):
        id: str
        title: str | None
        created_at: datetime
        message_count: int
```

Router pattern:
```python
# services/api/src/routers/v1/chat_router.py
from fastapi import APIRouter, Depends
from api.v1.chat import CreateThread, ListThreads, GetThread, DeleteThread
from dependencies import get_current_user, get_database
from utils.models.user import User
from utils.services.database import Database

chat_router = APIRouter(tags=["chat"])

@chat_router.post("/chat/threads")
async def create_thread(
    params: CreateThread.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    return CreateThread.call(params=params, user=user, database=database)
```

### Backend: SSE SendMessage Endpoint (NOT using Endpoint class)

The SSE endpoint CANNOT use `Endpoint.call()` because it returns `StreamingResponse`, not `CustomJSONResponse`. Define it as a standalone async function:

```python
# services/api/src/api/v1/chat/send_message.py
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
from pydantic import BaseModel
import json

class SendMessageParams(BaseModel):
    message: str

async def send_message_stream(
    thread_id: str,
    params: SendMessageParams,
    user,
    database,
):
    """Returns a StreamingResponse with SSE events for the AI chat."""
    # Validate ownership
    from utils.models.thread import Thread
    thread = database.find_by(Thread, id=thread_id)
    if not thread or str(thread.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Thread not found")

    async def event_generator():
        async for event in run_chat_agent(
            thread_id=thread_id,
            user_message=params.message,
            user=user,
            database=database,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

In the router:
```python
@chat_router.post("/chat/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    params: SendMessageParams,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    return await send_message_stream(thread_id, params, user, database)
```

### Backend: Agent Loop Design

```python
# services/api/src/api/v1/chat/agent_loop.py
import json
from typing import AsyncGenerator, Any
from agent.llm.provider import get_llm_provider, Message, Tool
from agent.tools.recipes import SearchRecipesTool
from utils.models.chat import Chat
from utils.models.thread import Thread

SYSTEM_PROMPT = """You are a helpful cooking assistant for Palateful.
You help users manage their recipes, find ingredients, and plan meals.
You have access to the user's recipe collection via tool calls.
Always be conversational and helpful. When searching recipes, use the search_recipes tool."""

async def run_chat_agent(
    thread_id: str,
    user_message: str,
    user,
    database,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator yielding SSE event dicts."""

    # 1. Check token cap
    monthly_tokens = get_user_monthly_tokens(database.db, user.id)
    from config import settings
    if monthly_tokens >= settings.ai_chat_monthly_token_cap:
        yield {"type": "error", "code": "token_cap_exceeded",
               "message": "Monthly AI usage limit reached."}
        return

    # 2. Persist user message
    user_chat = Chat(
        thread_id=thread_id, role="user", content=user_message
    )
    database.create(user_chat)
    database.db.flush()

    # 3. Load thread history → LLM messages
    thread = database.db.get(Thread, thread_id)
    messages = [Message(role="system", content=SYSTEM_PROMPT)]
    for chat in thread.chats:
        if chat.role == "tool":
            messages.append(Message(
                role="tool",
                content=chat.content,
                tool_call_id=chat.tool_call_id,
                name=chat.tool_name,
            ))
        else:
            messages.append(Message(role=chat.role, content=chat.content or ""))

    # 4. Define available tools
    tools_registry = [SearchRecipesTool()]
    tool_defs = [t.to_langchain_tool() for t in tools_registry]

    # 5. Tool resolution round (synchronous, no streaming)
    provider = get_llm_provider()
    response = provider.chat(messages, tools=tool_defs, temperature=0.7)

    while response.finish_reason == "tool_calls" and response.tool_calls:
        # Persist assistant message with tool_calls
        assistant_chat = Chat(
            thread_id=thread_id, role="assistant", content=response.content,
            tool_calls=response.tool_calls,
            model=response.model,
            prompt_tokens=response.usage.get("prompt_tokens"),
            completion_tokens=response.usage.get("completion_tokens"),
        )
        database.create(assistant_chat)
        database.db.flush()

        # Append assistant message with tool_calls to history
        messages.append(Message(role="assistant", content=response.content or ""))

        # Execute each tool call
        for tc in response.tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])
            yield {"type": "tool_call", "id": tc["id"], "name": tool_name, "args": tool_args}

            # Find and execute tool
            tool = next((t for t in tools_registry if t.name == tool_name), None)
            if tool:
                result = tool.execute(db=database.db, user_id=str(user.id), **tool_args)
                tool_content = result.to_message()
            else:
                tool_content = f"Error: unknown tool '{tool_name}'"

            yield {"type": "tool_result", "id": tc["id"], "name": tool_name,
                   "content": tool_content[:500]}  # truncate for SSE event

            # Persist tool result message
            tool_chat = Chat(
                thread_id=thread_id, role="tool", content=tool_content,
                tool_call_id=tc["id"], tool_name=tool_name,
            )
            database.create(tool_chat)
            database.db.flush()

            # Append to LLM messages
            messages.append(Message(
                role="tool", content=tool_content,
                tool_call_id=tc["id"], name=tool_name,
            ))

        # Next round
        response = provider.chat(messages, tools=tool_defs, temperature=0.7)

    # 6. Stream final text response
    full_content = ""
    async for token in provider.stream_chat(messages, temperature=0.7):
        full_content += token
        yield {"type": "token", "content": token}

    # 7. Persist final assistant message
    final_chat = Chat(
        thread_id=thread_id, role="assistant", content=full_content,
        model=response.model,
        prompt_tokens=response.usage.get("prompt_tokens"),
        completion_tokens=response.usage.get("completion_tokens"),
    )
    database.create(final_chat)
    database.db.commit()

    yield {"type": "done", "message_id": str(final_chat.id),
           "usage": response.usage}
```

### Backend: Add `stream_chat()` to LLMProvider

```python
# In libraries/agent/agent/llm/provider.py — add to LLMProvider ABC:
@abstractmethod
async def stream_chat(
    self,
    messages: list[Message],
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat completion tokens."""
    pass

# In libraries/agent/agent/llm/openai.py — implement:
async def stream_chat(self, messages, temperature=0.7, max_tokens=None):
    openai_messages = [...]  # same conversion as in chat()
    stream = self.client.chat.completions.create(
        model=self.model, messages=openai_messages,
        temperature=temperature, stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

For `AnthropicProvider`, implement similarly using `anthropic.messages.stream()`.
For `OllamaProvider`, implement using Ollama's streaming API.

### Backend: Token Cap Helper

```python
# services/api/src/api/v1/chat/agent_loop.py
from datetime import datetime, timezone
from sqlalchemy import func, select
from utils.models.chat import Chat
from utils.models.thread import Thread

def get_user_monthly_tokens(db, user_id) -> int:
    """Sum all tokens used by user in current calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = db.execute(
        select(func.coalesce(
            func.sum(Chat.prompt_tokens + Chat.completion_tokens), 0
        ))
        .join(Thread, Chat.thread_id == Thread.id)
        .where(Thread.user_id == user_id)
        .where(Chat.created_at >= month_start)
        .where(Chat.prompt_tokens.is_not(None))
    )
    return result.scalar() or 0
```

### Backend: Migration Template

Follow existing migration style. Reference: `20260320000001_add_recipe_share_token.py` as a model for the file structure.

```python
# services/migrator/migrations/versions/20260320000002_add_chat_threads.py
"""Add chat threads and messages tables."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
import alembic.op as op

revision = '20260320000002'
down_revision = '20260320000001'  # last migration
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'threads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, ...),
        sa.Column('created_at', sa.DateTime(timezone=True), ...),
        sa.Column('updated_at', sa.DateTime(timezone=True), ...),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.String, nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_index('ix_threads_user_id', 'threads', ['user_id'])

    op.create_table(
        'chats',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, ...),
        sa.Column('created_at', ...),
        sa.Column('updated_at', ...),
        sa.Column('archived_at', ..., nullable=True),
        sa.Column('role', sa.String, nullable=False),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('tool_calls', JSONB, nullable=True),
        sa.Column('tool_call_id', sa.String, nullable=True),
        sa.Column('tool_name', sa.String, nullable=True),
        sa.Column('prompt_tokens', sa.Integer, nullable=True),
        sa.Column('completion_tokens', sa.Integer, nullable=True),
        sa.Column('model', sa.String, nullable=True),
        sa.Column('thread_id', UUID(as_uuid=True), sa.ForeignKey('threads.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_index('ix_chats_thread_id', 'chats', ['thread_id'])

def downgrade() -> None:
    op.drop_index('ix_chats_thread_id', 'chats')
    op.drop_table('chats')
    op.drop_index('ix_threads_user_id', 'threads')
    op.drop_table('threads')
```

Look at an existing migration for the exact `Base.id`, `Base.created_at` column patterns used in this project.

### Flutter: SSE Client Pattern

Use `dio` with `ResponseType.stream`:

```dart
// app/lib/features/chat/chat_service.dart
import 'dart:convert';
import 'package:dio/dio.dart';

sealed class ChatEvent {}
class TokenEvent extends ChatEvent { final String content; TokenEvent(this.content); }
class ToolCallEvent extends ChatEvent { final String name; ToolCallEvent(this.name); }
class ToolResultEvent extends ChatEvent { final String name; ToolResultEvent(this.name); }
class DoneEvent extends ChatEvent { final String messageId; DoneEvent(this.messageId); }
class ErrorEvent extends ChatEvent { final String message; ErrorEvent(this.message); }

class ChatService {
  final Dio _dio;
  ChatService(this._dio);

  Stream<ChatEvent> sendMessage(String threadId, String text) async* {
    final response = await _dio.post(
      '/v1/chat/threads/$threadId/messages',
      data: {'message': text},
      options: Options(responseType: ResponseType.stream),
    );

    final stream = response.data.stream as Stream<List<int>>;
    final buffer = StringBuffer();

    await for (final chunk in stream) {
      buffer.write(utf8.decode(chunk));
      final raw = buffer.toString();
      buffer.clear();

      // Split on SSE double newline delimiter
      final events = raw.split('\n\n');
      for (final event in events) {
        if (!event.startsWith('data: ')) continue;
        final jsonStr = event.substring(6).trim();
        if (jsonStr.isEmpty) continue;
        final data = jsonDecode(jsonStr) as Map<String, dynamic>;

        switch (data['type'] as String?) {
          case 'token':
            yield TokenEvent(data['content'] as String);
          case 'tool_call':
            yield ToolCallEvent(data['name'] as String);
          case 'tool_result':
            yield ToolResultEvent(data['name'] as String);
          case 'done':
            yield DoneEvent(data['message_id'] as String);
          case 'error':
            yield ErrorEvent(data['message'] as String? ?? 'Unknown error');
        }
      }
    }
  }
}
```

### Flutter: Project Structure

Follow existing patterns from `app/lib/features/`:
- `features/chat/` directory structure:
  - `chat_screen.dart` — main screen
  - `chat_provider.dart` — Riverpod providers
  - `chat_service.dart` — HTTP/SSE client
  - `widgets/message_bubble.dart` — message display

State pattern (follow existing features):
```dart
// Riverpod AsyncNotifier pattern (from architecture)
@riverpod
class ActiveChatNotifier extends _$ActiveChatNotifier {
  // Use AsyncValue<T> for all server data
  // Provider naming: activeChatProvider
  // Mutations through notifier methods
}
```

### Flutter: Navigation (Do NOT Add 6th Nav Destination)

The navigation has exactly 5 destinations (verified in `widget_test.dart`). Do NOT add a 6th. Instead, add a chat entry point as:
- A `FloatingActionButton` on the home screen / recipe books list screen
- OR an icon button in the AppBar when on a relevant screen

Read `app/lib/shared/widgets/scaffold_with_bottom_nav.dart` and the main routing config to understand the current layout before implementing.

The chat route: add `/chat` and `/chat/:threadId` to the go_router config.

### Existing Tests Pattern

```
services/api/unittests/v1/test_recipe.py  ← follow this pattern
services/api/unittests/conftest.py         ← fixtures (db, client, user)
```

For mocking the LLM in tests:
```python
from unittest.mock import patch, MagicMock
from agent.llm.provider import LLMResponse

mock_response = LLMResponse(
    content="Here are some recipes!",
    model="gpt-4o-mini",
    usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    tool_calls=[],
    finish_reason="stop",
)

with patch('api.v1.chat.agent_loop.get_llm_provider') as mock:
    mock.return_value.chat.return_value = mock_response
    # test the endpoint
```

### ErrorCode

The project uses `ErrorCode` enum from `utils.classes.error_code`. When adding new errors for chat:
- Check what codes exist: `libraries/utils/utils/classes/error_code.py`
- If `THREAD_NOT_FOUND`, `TOKEN_CAP_EXCEEDED` don't exist, add them OR use existing generic codes

### Key Dependencies

- `libraries/agent` is imported in `services/api` via pyproject.toml workspace dependency
- Check `services/api/pyproject.toml` to confirm `agent` library is listed; if not, add it
- The `Thread` and `Chat` models are in `libraries/utils` which IS a dependency of `services/api`

### Do NOT Touch

- `app/lib/shared/widgets/scaffold_with_bottom_nav.dart` — do not add 6th nav destination
- `app/test/widget_test.dart` — existing nav destination count tests should still pass
- Existing `agent/` library suggestion runner and graph code — don't break `DailySuggestionsTask`
- Existing `LLMProvider.chat()` synchronous method — add `stream_chat()` as a NEW method; don't change existing signature

### References

- Thread/Chat models [Source: libraries/utils/utils/models/thread.py, chat.py]
- LLMProvider interface [Source: libraries/agent/agent/llm/provider.py]
- OpenAIProvider [Source: libraries/agent/agent/llm/openai.py]
- SearchRecipesTool [Source: libraries/agent/agent/tools/recipes.py]
- Endpoint base class [Source: libraries/utils/utils/api/endpoint.py]
- Router aggregator [Source: services/api/src/routers/v1_router.py]
- Auth dependency [Source: services/api/src/dependencies.py]
- AgentSettings [Source: libraries/agent/agent/config.py]
- Architecture: SSE chat streaming [Source: _bmad-output/planning-artifacts/architecture.md#AI Chat Streaming]
- Epic 11 story context [Source: _bmad-output/planning-artifacts/epics.md#Epic 11]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
