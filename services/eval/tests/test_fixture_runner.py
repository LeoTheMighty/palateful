"""Tests for the fixture runner module."""

import json
import os
from pathlib import Path

import pytest

from src.fixture_runner import (
    _aggregate_scores,
    _discover_fixtures,
)


@pytest.fixture
def tmp_fixtures(tmp_path):
    """Create a temporary fixtures directory with a sample pair."""
    text_dir = tmp_path / "text"
    expected_dir = tmp_path / "expected"
    images_dir = tmp_path / "images"
    urls_dir = tmp_path / "urls"

    text_dir.mkdir()
    expected_dir.mkdir()
    images_dir.mkdir()
    urls_dir.mkdir()

    # Create a text fixture
    (text_dir / "sample_recipe.txt").write_text("Sample Recipe\nIngredients:\n1 cup flour")

    # Create matching expected JSON
    expected_data = {
        "name": "Sample Recipe",
        "ingredients": [
            {"name": "flour", "quantity": 1, "unit": "cup", "text": "1 cup flour"}
        ],
    }
    (expected_dir / "sample_recipe.json").write_text(json.dumps(expected_data))

    return tmp_path


class TestDiscoverFixtures:
    def test_finds_text_fixture(self, tmp_fixtures):
        fixtures = _discover_fixtures(tmp_fixtures)
        assert len(fixtures) == 1
        assert fixtures[0]["id"] == "sample_recipe"
        assert fixtures[0]["input_type"] == "text"

    def test_no_expected_dir(self, tmp_path):
        fixtures = _discover_fixtures(tmp_path)
        assert fixtures == []

    def test_unmatched_input_skipped(self, tmp_fixtures):
        # Add a text file without a matching expected JSON
        (tmp_fixtures / "text" / "no_match.txt").write_text("hello")
        fixtures = _discover_fixtures(tmp_fixtures)
        assert len(fixtures) == 1  # Only the matched one

    def test_filter_by_input_type(self, tmp_fixtures):
        # Only look for image fixtures — should find none
        fixtures = _discover_fixtures(tmp_fixtures, input_types=["image"])
        assert len(fixtures) == 0

    def test_gitkeep_ignored(self, tmp_fixtures):
        (tmp_fixtures / "text" / ".gitkeep").write_text("")
        fixtures = _discover_fixtures(tmp_fixtures)
        assert all(f["id"] != ".gitkeep" for f in fixtures)


class TestAggregateScores:
    def test_aggregate_single(self):
        results = [
            {
                "id": "test",
                "scores": {
                    "ingredients_precision": 0.8,
                    "ingredients_recall": 0.9,
                    "amounts_accuracy": 0.7,
                    "steps_completeness": 0.85,
                    "metadata_accuracy": 1.0,
                    "overall_f1": 0.85,
                },
            }
        ]
        agg = _aggregate_scores(results)
        assert agg["overall_f1_avg"] == 0.85
        assert agg["total_fixtures"] == 1.0

    def test_aggregate_with_errors(self):
        results = [
            {"id": "ok", "scores": {"overall_f1": 0.9}},
            {"id": "err", "error": "something broke", "scores": {}},
        ]
        agg = _aggregate_scores(results)
        assert agg["overall_f1_avg"] == 0.9
        assert agg["fixtures_with_errors"] == 1.0

    def test_aggregate_empty(self):
        agg = _aggregate_scores([])
        assert agg["total_fixtures"] == 0.0
