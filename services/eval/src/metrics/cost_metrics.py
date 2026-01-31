"""Cost and performance metrics for AI operations."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CostMetrics:
    """Tracks cost and performance metrics across evaluations."""

    total_cost_cents: int = 0
    total_tokens: int = 0
    total_requests: int = 0
    total_duration_ms: float = 0.0

    # Breakdown by operation type
    cost_by_operation: dict[str, int] = field(default_factory=dict)
    tokens_by_operation: dict[str, int] = field(default_factory=dict)
    duration_by_operation: dict[str, float] = field(default_factory=dict)

    def add_operation(
        self,
        operation: str,
        cost_cents: int = 0,
        tokens: int = 0,
        duration_ms: float = 0.0,
    ) -> None:
        """Record metrics for an operation.

        Args:
            operation: Name of the operation (e.g., "ai_extraction", "ocr").
            cost_cents: Cost in cents.
            tokens: Number of tokens used.
            duration_ms: Duration in milliseconds.
        """
        self.total_cost_cents += cost_cents
        self.total_tokens += tokens
        self.total_requests += 1
        self.total_duration_ms += duration_ms

        self.cost_by_operation[operation] = self.cost_by_operation.get(operation, 0) + cost_cents
        self.tokens_by_operation[operation] = self.tokens_by_operation.get(operation, 0) + tokens
        self.duration_by_operation[operation] = self.duration_by_operation.get(operation, 0) + duration_ms

    @property
    def average_cost_cents(self) -> float:
        """Average cost per request in cents."""
        return self.total_cost_cents / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def average_duration_ms(self) -> float:
        """Average duration per request in milliseconds."""
        return self.total_duration_ms / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def total_cost_dollars(self) -> float:
        """Total cost in dollars."""
        return self.total_cost_cents / 100.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_cost_cents": self.total_cost_cents,
            "total_cost_dollars": self.total_cost_dollars,
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "total_duration_ms": self.total_duration_ms,
            "average_cost_cents": self.average_cost_cents,
            "average_duration_ms": self.average_duration_ms,
            "cost_by_operation": self.cost_by_operation,
            "tokens_by_operation": self.tokens_by_operation,
            "duration_by_operation": self.duration_by_operation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CostMetrics":
        """Create from dictionary."""
        return cls(
            total_cost_cents=data.get("total_cost_cents", 0),
            total_tokens=data.get("total_tokens", 0),
            total_requests=data.get("total_requests", 0),
            total_duration_ms=data.get("total_duration_ms", 0.0),
            cost_by_operation=data.get("cost_by_operation", {}),
            tokens_by_operation=data.get("tokens_by_operation", {}),
            duration_by_operation=data.get("duration_by_operation", {}),
        )

    @staticmethod
    def estimate_openai_cost(
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4o-mini",
    ) -> int:
        """Estimate OpenAI API cost in cents.

        Args:
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
            model: Model name.

        Returns:
            Estimated cost in cents.
        """
        # Pricing as of 2024 (per 1K tokens)
        pricing = {
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        }

        rates = pricing.get(model, pricing["gpt-4o-mini"])
        cost_dollars = (
            (prompt_tokens / 1000) * rates["input"] +
            (completion_tokens / 1000) * rates["output"]
        )
        return max(1, int(cost_dollars * 100))  # Minimum 1 cent

    def merge(self, other: "CostMetrics") -> "CostMetrics":
        """Merge another CostMetrics instance into this one.

        Args:
            other: Another CostMetrics instance.

        Returns:
            Self, for chaining.
        """
        self.total_cost_cents += other.total_cost_cents
        self.total_tokens += other.total_tokens
        self.total_requests += other.total_requests
        self.total_duration_ms += other.total_duration_ms

        for op, cost in other.cost_by_operation.items():
            self.cost_by_operation[op] = self.cost_by_operation.get(op, 0) + cost
        for op, tokens in other.tokens_by_operation.items():
            self.tokens_by_operation[op] = self.tokens_by_operation.get(op, 0) + tokens
        for op, duration in other.duration_by_operation.items():
            self.duration_by_operation[op] = self.duration_by_operation.get(op, 0) + duration

        return self
