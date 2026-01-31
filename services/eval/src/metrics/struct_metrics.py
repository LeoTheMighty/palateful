"""Structured data comparison metrics for JSON/dict outputs."""

from typing import Any


class StructMetrics:
    """Collection of structured data comparison metrics."""

    @staticmethod
    def compare_fields(
        actual: dict[str, Any],
        expected: dict[str, Any],
        ignore_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        """Compare fields between two dictionaries.

        Args:
            actual: Actual output dictionary.
            expected: Expected output dictionary.
            ignore_fields: Fields to ignore in comparison.

        Returns:
            Dictionary with comparison results.
        """
        ignore = ignore_fields or {"raw_data", "_cost_cents"}

        expected_keys = {k for k in expected.keys() if k not in ignore}
        actual_keys = {k for k in actual.keys() if k not in ignore}

        correct = 0
        incorrect = 0
        missing = []
        extra = []
        field_details = {}

        # Check expected fields
        for key in expected_keys:
            if key not in actual:
                missing.append(key)
                field_details[key] = {"status": "missing"}
            else:
                if StructMetrics._values_match(actual.get(key), expected.get(key)):
                    correct += 1
                    field_details[key] = {"status": "match"}
                else:
                    incorrect += 1
                    field_details[key] = {
                        "status": "mismatch",
                        "actual": actual.get(key),
                        "expected": expected.get(key),
                    }

        # Check extra fields
        for key in actual_keys - expected_keys:
            extra.append(key)
            field_details[key] = {"status": "extra", "value": actual.get(key)}

        total = len(expected_keys)
        accuracy = correct / total if total > 0 else 1.0

        return {
            "accuracy": accuracy,
            "correct": correct,
            "incorrect": incorrect,
            "total": total,
            "missing": missing,
            "extra": extra,
            "details": field_details,
        }

    @staticmethod
    def _values_match(actual: Any, expected: Any, tolerance: float = 0.01) -> bool:
        """Check if two values match.

        Args:
            actual: Actual value.
            expected: Expected value.
            tolerance: Numeric tolerance for float comparison.

        Returns:
            True if values match.
        """
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False

        # Handle numeric comparison with tolerance
        if isinstance(actual, int | float) and isinstance(expected, int | float):
            if expected == 0:
                return actual == 0
            return abs(actual - expected) / abs(expected) <= tolerance

        # Handle string comparison (case-insensitive, whitespace-normalized)
        if isinstance(actual, str) and isinstance(expected, str):
            return StructMetrics._normalize_string(actual) == StructMetrics._normalize_string(expected)

        # Handle list comparison
        if isinstance(actual, list) and isinstance(expected, list):
            if len(actual) != len(expected):
                return False
            return all(StructMetrics._values_match(a, e) for a, e in zip(actual, expected))

        # Handle dict comparison
        if isinstance(actual, dict) and isinstance(expected, dict):
            result = StructMetrics.compare_fields(actual, expected)
            return result["accuracy"] == 1.0

        # Direct comparison for other types
        return actual == expected

    @staticmethod
    def _normalize_string(s: str) -> str:
        """Normalize string for comparison."""
        return " ".join(s.lower().split())

    @staticmethod
    def list_similarity(
        actual: list[Any],
        expected: list[Any],
        key_field: str | None = None,
    ) -> dict[str, Any]:
        """Compare two lists for similarity.

        Args:
            actual: Actual output list.
            expected: Expected output list.
            key_field: Field to use for matching dict items.

        Returns:
            Dictionary with comparison results.
        """
        if not expected:
            return {
                "accuracy": 1.0 if not actual else 0.0,
                "matched": 0,
                "unmatched": len(actual),
                "missing": 0,
            }

        matched = 0
        unmatched_actual = []
        unmatched_expected = list(range(len(expected)))

        for actual_item in actual:
            found_match = False
            for i in unmatched_expected[:]:
                expected_item = expected[i]
                if StructMetrics._items_match(actual_item, expected_item, key_field):
                    matched += 1
                    unmatched_expected.remove(i)
                    found_match = True
                    break
            if not found_match:
                unmatched_actual.append(actual_item)

        return {
            "accuracy": matched / len(expected),
            "matched": matched,
            "unmatched": len(unmatched_actual),
            "missing": len(unmatched_expected),
            "total_expected": len(expected),
            "total_actual": len(actual),
        }

    @staticmethod
    def _items_match(actual: Any, expected: Any, key_field: str | None = None) -> bool:
        """Check if two list items match."""
        if key_field and isinstance(actual, dict) and isinstance(expected, dict):
            return actual.get(key_field) == expected.get(key_field)
        return StructMetrics._values_match(actual, expected)

    @staticmethod
    def nested_accuracy(
        actual: dict[str, Any],
        expected: dict[str, Any],
        weights: dict[str, float] | None = None,
    ) -> float:
        """Calculate weighted accuracy for nested structures.

        Args:
            actual: Actual output dictionary.
            expected: Expected output dictionary.
            weights: Optional weights for different fields.

        Returns:
            Weighted accuracy score.
        """
        if not weights:
            weights = {}

        total_weight = 0.0
        weighted_score = 0.0

        for key, expected_value in expected.items():
            weight = weights.get(key, 1.0)
            total_weight += weight

            actual_value = actual.get(key)
            if StructMetrics._values_match(actual_value, expected_value):
                weighted_score += weight

        return weighted_score / total_weight if total_weight > 0 else 1.0
