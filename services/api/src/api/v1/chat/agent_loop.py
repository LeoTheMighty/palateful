"""AI chat agent loop with SSE streaming and tool calling."""

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from utils.models.chat import Chat
from utils.models.thread import Thread

SYSTEM_PROMPT = (
    "You are a helpful cooking assistant for Palateful. "
    "You help users manage their recipes, find ingredients, and plan meals. "
    "You have access to the user's recipe collection via tool calls. "
    "Always be conversational and helpful. "
    "When searching recipes, use the search_recipes tool. "
    "When asked to add a note to a recipe, use the add_note_to_recipe tool. "
    "When users ask for recipe suggestions or what to cook, use the search_recipes tool "
    "to find relevant recipes from their collection and present them with your reasoning. "
    "Use suggest_recipe only when the user explicitly wants a brand-new recipe idea "
    "not from their existing collection. "
    "When the user is cooking and asks questions about the current recipe, "
    "use the recipe context provided to answer. Reference specific ingredients, "
    "steps, and quantities. Keep answers concise and practical."
)


def get_user_monthly_tokens(db, user_id) -> int:
    """Sum all tokens used by the user in the current calendar month."""
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = db.execute(
        select(
            func.coalesce(func.sum(Chat.prompt_tokens + Chat.completion_tokens), 0)
        )
        .join(Thread, Chat.thread_id == Thread.id)
        .where(Thread.user_id == user_id)
        .where(Chat.created_at >= month_start)
        .where(Chat.prompt_tokens.is_not(None))
    )
    return result.scalar() or 0


async def run_chat_agent(
    thread_id: str,
    user_message: str,
    user,
    database,
    recipe_context: str | None = None,
) -> AsyncGenerator[dict[str, Any]]:
    """Async generator yielding SSE event dicts for the AI chat agent loop."""
    from agent.llm.provider import Message, get_llm_provider
    from agent.tools.recipes import AddNoteToRecipeTool, SearchRecipesTool, SuggestRecipeTool
    from config import settings

    # E2E test mode: return a canned response without calling OpenAI
    if settings.e2e_test_mode:
        user_chat = Chat(thread_id=thread_id, role="user", content=user_message)
        database.create(user_chat)
        reply = "I'm the E2E test assistant. I can see your recipes and help you cook!"
        assistant_chat = Chat(thread_id=thread_id, role="assistant", content=reply)
        database.create(assistant_chat)
        yield {"type": "text", "content": reply}
        yield {"type": "done"}
        return

    # 1. Check per-user monthly token cap
    monthly_tokens = get_user_monthly_tokens(database.db, user.id)
    if monthly_tokens >= settings.ai_chat_monthly_token_cap:
        yield {
            "type": "error",
            "code": "token_cap_exceeded",
            "message": "Monthly AI usage limit reached.",
        }
        return

    # 2. Persist user message
    user_chat = Chat(thread_id=thread_id, role="user", content=user_message)
    database.create(user_chat)
    database.db.flush()

    # 3. Load thread history → LLM messages
    thread = database.db.get(Thread, thread_id)
    system_content = SYSTEM_PROMPT
    if recipe_context:
        system_content += "\n\n--- Current Recipe Context ---\n" + recipe_context
    messages = [Message(role="system", content=system_content)]
    for chat in thread.chats:
        if chat.role == "tool":
            messages.append(
                Message(
                    role="tool",
                    content=chat.content or "",
                    tool_call_id=chat.tool_call_id,
                    name=chat.tool_name,
                )
            )
        else:
            messages.append(Message(role=chat.role, content=chat.content or ""))

    # 4. Define available tools
    tools_registry = [SearchRecipesTool(), AddNoteToRecipeTool(), SuggestRecipeTool()]
    tool_defs = [t.to_langchain_tool() for t in tools_registry]

    # 5. Tool resolution round (synchronous non-streaming)
    provider = get_llm_provider()
    response = provider.chat(messages, tools=tool_defs, temperature=0.7)

    while response.finish_reason == "tool_calls" and response.tool_calls:
        # Re-check token cap before executing more tool calls
        if get_user_monthly_tokens(database.db, user.id) >= settings.ai_chat_monthly_token_cap:
            yield {"type": "error", "code": "token_cap_exceeded", "message": "Monthly AI usage limit reached."}
            return

        # Persist assistant message with tool_calls
        assistant_chat = Chat(
            thread_id=thread_id,
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
            model=response.model,
            prompt_tokens=response.usage.get("prompt_tokens"),
            completion_tokens=response.usage.get("completion_tokens"),
        )
        database.create(assistant_chat)
        database.db.flush()

        messages.append(Message(
            role="assistant",
            content=response.content or "",
            tool_calls=response.tool_calls if response.tool_calls else None,
        ))

        for tc in response.tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])
            yield {"type": "tool_call", "id": tc["id"], "name": tool_name, "args": tool_args}

            tool = next((t for t in tools_registry if t.name == tool_name), None)
            if tool:
                result = tool.execute(db=database.db, user_id=str(user.id), **tool_args)
                tool_content = result.to_message()
            else:
                tool_content = f"Error: unknown tool '{tool_name}'"

            tool_result_event: dict[str, Any] = {
                "type": "tool_result",
                "id": tc["id"],
                "name": tool_name,
                "content": tool_content[:500],
            }
            if tool and tool_name == "search_recipes" and result.success and isinstance(result.data, dict):
                raw_recipes = result.data.get("recipes", [])
                tool_result_event["recipes"] = [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "recipe_book_name": r.get("recipe_book_name"),
                        "total_time": r.get("total_time"),
                        "relevance_score": r.get("relevance_score"),
                    }
                    for r in raw_recipes
                ]
            yield tool_result_event

            tool_chat = Chat(
                thread_id=thread_id,
                role="tool",
                content=tool_content,
                tool_call_id=tc["id"],
                tool_name=tool_name,
            )
            database.create(tool_chat)
            database.db.flush()

            messages.append(
                Message(
                    role="tool",
                    content=tool_content,
                    tool_call_id=tc["id"],
                    name=tool_name,
                )
            )

        response = provider.chat(messages, tools=tool_defs, temperature=0.7)

    # 6. Stream final text response
    full_content = ""
    async for token in provider.stream_chat(messages, temperature=0.7):
        full_content += token
        yield {"type": "token", "content": token}

    # 7. Persist final assistant message
    final_chat = Chat(
        thread_id=thread_id,
        role="assistant",
        content=full_content,
        model=response.model,
        prompt_tokens=response.usage.get("prompt_tokens"),
        completion_tokens=response.usage.get("completion_tokens"),
    )
    database.create(final_chat)
    database.db.commit()

    yield {
        "type": "done",
        "message_id": str(final_chat.id),
        "usage": response.usage,
    }
