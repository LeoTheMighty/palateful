"""Base tool class for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from agent.llm.provider import Tool


@dataclass
class ToolResult:
    """Result from executing a tool."""

    success: bool
    data: Any = None
    error: str | None = None

    def to_message(self) -> str:
        """Convert the result to a message string for the LLM."""
        if not self.success:
            return f"Error: {self.error}"

        if isinstance(self.data, str):
            return self.data
        elif isinstance(self.data, dict):
            import json
            return json.dumps(self.data, indent=2, default=str)
        elif isinstance(self.data, list):
            import json
            return json.dumps(self.data, indent=2, default=str)
        else:
            return str(self.data)


class BaseTool(ABC):
    """Abstract base class for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for function calling."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool parameters."""
        pass

    @abstractmethod
    def execute(
        self,
        db: Session,
        user_id: str,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute the tool.

        Args:
            db: Database session
            user_id: ID of the user making the request
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with the execution result
        """
        pass

    def to_langchain_tool(self) -> Tool:
        """Convert to a LangChain/LangGraph compatible tool definition."""
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )
