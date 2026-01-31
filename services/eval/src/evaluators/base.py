"""Base evaluator class and common data structures."""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.config import EvalConfig


@dataclass
class EvalCase:
    """A single evaluation test case."""

    id: str
    input_path: Path | None = None
    input_data: Any = None
    expected_path: Path | None = None
    expected_data: Any = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_cache_key(self) -> str:
        """Generate a cache key based on input content."""
        if self.input_path and self.input_path.exists():
            content = self.input_path.read_bytes()
        elif self.input_data:
            content = json.dumps(self.input_data, sort_keys=True).encode()
        else:
            content = self.id.encode()
        return hashlib.sha256(content).hexdigest()[:16]


@dataclass
class EvalResult:
    """Result of evaluating a single test case."""

    case_id: str
    passed: bool = False
    skipped: bool = False
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    actual_output: Any = None
    expected_output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    cost_cents: int = 0
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "skipped": self.skipped,
            "metrics": self.metrics,
            "actual_output": str(self.actual_output)[:1000] if self.actual_output else None,
            "expected_output": str(self.expected_output)[:1000] if self.expected_output else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "cost_cents": self.cost_cents,
            "cache_hit": self.cache_hit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalResult":
        return cls(
            case_id=data["case_id"],
            passed=data["passed"],
            skipped=data.get("skipped", False),
            metrics=data.get("metrics", {}),
            actual_output=data.get("actual_output"),
            expected_output=data.get("expected_output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0),
            cost_cents=data.get("cost_cents", 0),
            cache_hit=data.get("cache_hit", False),
        )


class BaseEvaluator(ABC):
    """Abstract base class for evaluators."""

    name: str = "base"

    def __init__(self, config: EvalConfig):
        self.config = config
        self._cache_dir: Path | None = None

    @property
    def cache_dir(self) -> Path:
        """Get cache directory for this evaluator."""
        if self._cache_dir is None:
            self._cache_dir = self.config.dataset_dir / self.name / "cache"
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir

    @property
    def suite_dir(self) -> Path:
        """Get suite directory for this evaluator."""
        return self.config.dataset_dir / self.name

    @abstractmethod
    def load_cases(self) -> list[EvalCase]:
        """Load test cases from the dataset.

        Returns:
            List of EvalCase objects to evaluate.
        """

    @abstractmethod
    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate a single test case.

        Args:
            case: The test case to evaluate.

        Returns:
            EvalResult with metrics and pass/fail status.
        """

    def load_manifest(self) -> dict[str, Any]:
        """Load the manifest.yaml file for this suite."""
        manifest_path = self.suite_dir / "manifest.yaml"
        if not manifest_path.exists():
            return {"cases": [], "config": {}}

        with open(manifest_path) as f:
            return yaml.safe_load(f) or {"cases": [], "config": {}}

    def get_cached_response(self, cache_key: str) -> Any | None:
        """Get cached response if available and mock mode is enabled."""
        if not self.config.mock_ai:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return None

    def save_cached_response(self, cache_key: str, response: Any) -> None:
        """Save response to cache if caching is enabled."""
        if not self.config.cache_responses:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w") as f:
            json.dump(response, f, indent=2, default=str)

    def timed_execution(self, func, *args, **kwargs) -> tuple[Any, float]:
        """Execute a function and return result with timing.

        Returns:
            Tuple of (result, duration_ms)
        """
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        return result, duration_ms
