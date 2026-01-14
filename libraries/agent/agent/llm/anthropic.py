"""Anthropic LLM provider implementation."""

from anthropic import Anthropic

from agent.config import settings
from agent.llm.provider import LLMProvider, LLMResponse, Message, Tool


class AnthropicProvider(LLMProvider):
    """Anthropic provider implementation using the Anthropic Python SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the Anthropic provider."""
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or "claude-3-5-sonnet-20241022"
        self.client = Anthropic(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Anthropic."""
        # Extract system message if present
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            elif msg.role == "tool":
                # Anthropic uses a different format for tool results
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        # Build request kwargs
        kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }

        if system_message:
            kwargs["system"] = system_message

        # Convert tools to Anthropic format
        if tools:
            kwargs["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in tools
            ]

        # Make request
        response = self.client.messages.create(**kwargs)

        # Extract content and tool uses
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": str(block.input),
                    },
                })

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "end_turn",
            raw_response=response,
        )

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embeddings.

        Note: Anthropic doesn't have a native embedding API, so we use
        sentence-transformers locally instead.
        """
        from sentence_transformers import SentenceTransformer

        # Use local model for embeddings
        model = SentenceTransformer(settings.embedding_model)
        embedding = model.encode(text)
        return embedding.tolist()
