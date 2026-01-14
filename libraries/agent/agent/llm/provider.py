"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agent.config import settings


@dataclass
class LLMResponse:
    """Standard response from an LLM provider."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    raw_response: Any = None


@dataclass
class Message:
    """Standard message format for LLM conversations."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class Tool:
    """Tool definition for function calling."""

    name: str
    description: str
    parameters: dict[str, Any]


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available for function calling
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """
    Factory function to get an LLM provider instance.

    Args:
        provider_name: Name of the provider ("openai", "anthropic", "ollama")
                      If None, uses the default from settings.

    Returns:
        An LLMProvider instance
    """
    from agent.llm.openai import OpenAIProvider
    from agent.llm.anthropic import AnthropicProvider
    from agent.llm.ollama import OllamaProvider

    name = provider_name or settings.agent_default_provider

    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    if name not in providers:
        raise ValueError(
            f"Unknown provider: {name}. Available: {list(providers.keys())}"
        )

    return providers[name]()
