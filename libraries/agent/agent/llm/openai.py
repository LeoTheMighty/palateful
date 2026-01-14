"""OpenAI LLM provider implementation."""

from openai import OpenAI

from agent.config import settings
from agent.llm.provider import LLMProvider, LLMResponse, Message, Tool


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation using the OpenAI Python SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the OpenAI provider."""
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.agent_model
        self.client = OpenAI(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to OpenAI."""
        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            message_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                message_dict["name"] = msg.name
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            openai_messages.append(message_dict)

        # Build request kwargs
        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        # Convert tools to OpenAI format
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]

        # Make request
        response = self.client.chat.completions.create(**kwargs)

        # Extract tool calls if any
        tool_calls = []
        if response.choices[0].message.tool_calls:
            for tc in response.choices[0].message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
            raw_response=response,
        )

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embeddings using OpenAI's embedding model."""
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=384,  # Match our vector dimensions
        )
        return response.data[0].embedding
