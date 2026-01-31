"""JSON reporter for evaluation results."""

import json
from pathlib import Path

from src.runner import EvalResults


class JSONReporter:
    """Reports evaluation results as JSON."""

    def save(self, results: EvalResults, output_path: Path) -> None:
        """Save evaluation results to a JSON file.

        Args:
            results: Evaluation results to save.
            output_path: Path to output JSON file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results.to_dict(), f, indent=2, default=str)

    def load(self, input_path: Path) -> EvalResults:
        """Load evaluation results from a JSON file.

        Args:
            input_path: Path to input JSON file.

        Returns:
            Loaded EvalResults object.
        """
        with open(input_path) as f:
            data = json.load(f)

        return EvalResults.from_dict(data)

    def to_string(self, results: EvalResults, indent: int = 2) -> str:
        """Convert evaluation results to JSON string.

        Args:
            results: Evaluation results to convert.
            indent: JSON indentation level.

        Returns:
            JSON string representation.
        """
        return json.dumps(results.to_dict(), indent=indent, default=str)
