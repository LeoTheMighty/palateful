"""Eval gate for CI -- fails if accuracy drops below thresholds."""

from __future__ import annotations

import sys

from src.fixture_runner import run_eval

THRESHOLDS = {
    "text": 0.80,  # 80% overall F1 for text inputs
    "image": 0.70,  # 70% for images (more lenient)
    "url": 0.85,  # 85% for URLs
}


def run_gate(fixtures_dir: str, strategy: str = "text_extractor") -> bool:
    """Run eval and check against thresholds. Returns True if passing."""
    results = run_eval(fixtures_dir, strategy)

    # The aggregate dict uses '<metric>_avg' keys (see fixture_runner._aggregate_scores)
    avg_f1 = results.get("aggregate", {}).get("overall_f1_avg", 0)
    threshold = THRESHOLDS.get("text", 0.80)

    passed = avg_f1 >= threshold

    if not passed:
        print(f"EVAL GATE FAILED: F1 {avg_f1:.2f} < threshold {threshold:.2f}")
    else:
        print(f"EVAL GATE PASSED: F1 {avg_f1:.2f} >= threshold {threshold:.2f}")

    return passed


if __name__ == "__main__":
    fixtures_path = "fixtures"
    if len(sys.argv) > 1:
        fixtures_path = sys.argv[1]

    strategy = "text_extractor"
    if len(sys.argv) > 2:
        strategy = sys.argv[2]

    passed = run_gate(fixtures_path, strategy)
    sys.exit(0 if passed else 1)
