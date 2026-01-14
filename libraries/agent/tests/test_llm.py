"""Tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.llm.provider import LLMProvider, LLMResponse, Message, Tool, get_llm_provider


class TestLLMResponse:
    """Tests for LLMResponse."""

    def test_create_response(self):
        """Test creating an LLM response."""
        response = LLMResponse(
            content="Hello, world!",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

        assert response.content == "Hello, world!"
        assert response.model == "gpt-4o-mini"
        assert response.usage["prompt_tokens"] == 10

    def test_response_with_tool_calls(self):
        """Test response with tool calls."""
        response = LLMResponse(
            content="",
            model="gpt-4o-mini",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "get_pantry", "arguments": "{}"},
                }
            ],
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "get_pantry"


class TestMessage:
    """Tests for Message."""

    def test_create_user_message(self):
        """Test creating a user message."""
        message = Message(role="user", content="Hello")

        assert message.role == "user"
        assert message.content == "Hello"

    def test_create_tool_message(self):
        """Test creating a tool message."""
        message = Message(
            role="tool",
            content='{"items": []}',
            tool_call_id="call_123",
        )

        assert message.role == "tool"
        assert message.tool_call_id == "call_123"


class TestTool:
    """Tests for Tool."""

    def test_create_tool(self):
        """Test creating a tool definition."""
        tool = Tool(
            name="get_pantry",
            description="Get user's pantry items",
            parameters={
                "type": "object",
                "properties": {},
            },
        )

        assert tool.name == "get_pantry"
        assert "properties" in tool.parameters


class TestGetLLMProvider:
    """Tests for get_llm_provider factory."""

    def test_get_openai_provider(self):
        """Test getting OpenAI provider."""
        with patch("agent.llm.provider.settings") as mock_settings:
            mock_settings.agent_default_provider = "openai"
            mock_settings.openai_api_key = "test-key"
            mock_settings.agent_model = "gpt-4o-mini"

            provider = get_llm_provider("openai")

            assert provider.provider_name == "openai"

    def test_get_anthropic_provider(self):
        """Test getting Anthropic provider."""
        with patch("agent.llm.provider.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"

            provider = get_llm_provider("anthropic")

            assert provider.provider_name == "anthropic"

    def test_get_ollama_provider(self):
        """Test getting Ollama provider."""
        with patch("agent.llm.provider.settings") as mock_settings:
            mock_settings.ollama_base_url = "http://localhost:11434"

            provider = get_llm_provider("ollama")

            assert provider.provider_name == "ollama"

    def test_invalid_provider(self):
        """Test error for invalid provider."""
        with pytest.raises(ValueError) as exc_info:
            get_llm_provider("invalid_provider")

        assert "Unknown provider" in str(exc_info.value)


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test chat completion."""
        from agent.llm.openai import OpenAIProvider

        with patch("agent.llm.openai.AsyncOpenAI") as mock_client:
            # Mock the response
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(
                    message=MagicMock(content="Test response", tool_calls=None),
                    finish_reason="stop",
                )
            ]
            mock_response.model = "gpt-4o-mini"
            mock_response.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            )

            mock_client.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )

            provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
            response = await provider.chat([Message(role="user", content="Hello")])

            assert response.content == "Test response"
            assert response.model == "gpt-4o-mini"


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    def test_provider_name(self):
        """Test provider name."""
        from agent.llm.anthropic import AnthropicProvider

        with patch("agent.llm.anthropic.AsyncAnthropic"):
            provider = AnthropicProvider(api_key="test-key")
            assert provider.provider_name == "anthropic"


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_provider_name(self):
        """Test provider name."""
        from agent.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434")
        assert provider.provider_name == "ollama"
