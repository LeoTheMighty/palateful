"""Bridge module for running production code in eval context.

Provides per-trial runners for two evaluation modes:
1. Parser eval: Runs recipe extraction against HTML/URL inputs
2. Chat eval: Runs the chat agent loop against mocked dependencies
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

from src.config import get_config


@dataclass
class TrialResult:
    """Result of a single eval trial."""

    output: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0


def run_parser_trial(
    input_type: str,
    input_html: str | None = None,
    input_url: str | None = None,
) -> TrialResult:
    """Run a parser eval trial.

    For URL inputs, we mock HTTP fetch and return the provided HTML fixture.
    For HTML inputs, we pass directly to the extraction pipeline.

    Args:
        input_type: "url" or "html".
        input_html: HTML content (fixture for URL mode, or direct input).
        input_url: URL to simulate fetching from.

    Returns:
        TrialResult with extracted recipe data.
    """
    config = get_config()
    result = TrialResult()
    start = time.perf_counter()

    try:
        if config.mock_ai:
            result.error = "Parser eval requires live AI (mock_ai=false)"
            return result

        from utils.services.recipe_extractors.ai_extractor import AIExtractor
        from utils.services.recipe_extractors.json_ld import JsonLdExtractor

        html = input_html or ""

        if input_type == "url" and input_url and not input_html:
            # Fetch real HTML from URL
            import httpx
            resp = httpx.get(input_url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text

        # Try JSON-LD extraction first
        json_ld = JsonLdExtractor()
        extraction = json_ld.extract(html, input_url)

        if not extraction.success or not extraction.recipe:
            # Fall back to AI extraction
            ai_extractor = AIExtractor()
            extraction = ai_extractor.extract(html, input_url)

        if extraction.success and extraction.recipe:
            recipe = extraction.recipe
            result.output = {
                "name": getattr(recipe, "name", None),
                "prep_time": getattr(recipe, "prep_time", None),
                "cook_time": getattr(recipe, "cook_time", None),
                "servings": getattr(recipe, "servings", None),
                "ingredient_count": len(getattr(recipe, "ingredients", []) or []),
                "step_count": len(getattr(recipe, "instructions", []) or []),
                "description": getattr(recipe, "description", None),
            }
        else:
            result.error = f"Extraction failed: {extraction.error if hasattr(extraction, 'error') else 'unknown'}"

    except Exception as e:
        result.error = str(e)
    finally:
        result.duration_ms = (time.perf_counter() - start) * 1000

    return result


def run_chat_trial(
    query: str,
    recipe_context: str | None = None,
    model: str | None = None,
) -> TrialResult:
    """Run a chat agent eval trial.

    Creates mocked database and user objects, then runs the production
    agent loop and collects the response.

    Args:
        query: User message to send.
        recipe_context: Optional recipe context for the conversation.
        model: Optional LLM model override.

    Returns:
        TrialResult with the agent's response and tool calls.
    """
    config = get_config()
    result = TrialResult()
    start = time.perf_counter()

    try:
        # Build mock database
        mock_db = _build_mock_db()
        mock_user = _build_mock_user()
        thread_id = "eval-thread-00000000-0000-0000-0000-000000000000"

        # Patch settings to avoid token cap issues in eval
        settings_patch = {
            "ai_chat_monthly_token_cap": 999_999_999,
        }

        # Collect events from the async generator
        events = asyncio.get_event_loop().run_until_complete(
            _collect_agent_events(
                thread_id=thread_id,
                query=query,
                user=mock_user,
                database=mock_db,
                recipe_context=recipe_context,
                model=model,
                settings_overrides=settings_patch,
            )
        )

        # Extract the final answer and tool calls
        full_answer = ""
        tool_calls = []
        for event in events:
            if event.get("type") == "token":
                full_answer += event.get("content", "")
            elif event.get("type") == "tool_call":
                tool_calls.append({
                    "name": event.get("name"),
                    "args": event.get("args"),
                })
            elif event.get("type") == "error":
                result.error = event.get("message", "Unknown error")
            elif event.get("type") == "done":
                result.tokens_used = event.get("usage", {}).get("total_tokens", 0)

        result.output = full_answer
        result.tool_calls = tool_calls

    except Exception as e:
        result.error = str(e)
    finally:
        result.duration_ms = (time.perf_counter() - start) * 1000

    return result


async def _collect_agent_events(
    thread_id: str,
    query: str,
    user: Any,
    database: Any,
    recipe_context: str | None,
    model: str | None,
    settings_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run the agent loop and collect all SSE events."""
    from api.v1.chat.agent_loop import run_chat_agent

    # Optionally override settings
    patches = []
    if settings_overrides:
        for key, value in settings_overrides.items():
            patches.append(
                patch(f"api.v1.chat.agent_loop.settings.{key}", value, create=True)
            )

    if model:
        patches.append(
            patch("agent.config.settings.agent_model", model)
        )

    events = []
    for p in patches:
        p.start()
    try:
        async for event in run_chat_agent(
            thread_id=thread_id,
            user_message=query,
            user=user,
            database=database,
            recipe_context=recipe_context,
        ):
            events.append(event)
    finally:
        for p in patches:
            p.stop()

    return events


def _build_mock_db() -> Any:
    """Build a mock database object that satisfies the agent loop interface."""
    mock = MagicMock()

    # Mock db session — return 0 for token usage queries
    mock.db.execute.return_value.scalar.return_value = 0

    # Mock thread with empty chat history
    mock_thread = MagicMock()
    mock_thread.chats = []
    mock.db.get.return_value = mock_thread

    # Mock create to just accept objects
    mock.create.return_value = None
    mock.db.flush.return_value = None
    mock.db.commit.return_value = None

    return mock


def _build_mock_user() -> Any:
    """Build a mock user object for the agent loop."""
    mock = MagicMock()
    mock.id = "eval-user-00000000-0000-0000-0000-000000000000"
    return mock
