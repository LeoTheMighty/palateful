"""Ollama LLM provider implementation for local models."""

import json

import httpx

from agent.config import settings
from agent.llm.provider import LLMProvider, LLMResponse, Message, Tool


class OllamaProvider(LLMProvider):
    """Ollama provider for running local LLMs."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        """Initialize the Ollama provider."""
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or "llama3.2"

    @property
    def provider_name(self) -> str:
        return "ollama"

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Ollama."""
        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Build request payload
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Convert tools to Ollama format (if supported by the model)
        if tools:
            payload["tools"] = [
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
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # Extract tool calls if any
        tool_calls = []
        if "tool_calls" in data.get("message", {}):
            for tc in data["message"]["tool_calls"]:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"]),
                    },
                })

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": (
                    data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                ),
            },
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason", "stop"),
            raw_response=data,
        )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=None):
        """Stream chat completion tokens from Ollama (non-blocking async)."""
        ollama_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embeddings using Ollama's embedding endpoint."""
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",  # Common embedding model for Ollama
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()

        embedding = data.get("embedding", [])

        # Pad or truncate to 384 dimensions to match our schema
        if len(embedding) < 384:
            embedding.extend([0.0] * (384 - len(embedding)))
        elif len(embedding) > 384:
            embedding = embedding[:384]

        return embedding
