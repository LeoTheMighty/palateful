"""Tests for the fixture runner module."""

import json
from pathlib import Path

import pytest

from src.fixture_runner import (
    _aggregate_scores,
    _discover_fixtures,
    _evaluate_fixture,
    expected_recipe_count,
    unwrap_expected_recipe,
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


class TestUnwrapExpectedRecipe:
    """irrd-3a — the {"recipes": [...]} envelope has to be unwrapped
    before scoring, or multi-recipe fixtures score near zero for a reason
    unrelated to extraction quality."""

    def test_bare_recipe_passes_through(self):
        recipe = {"name": "Simple Pasta", "ingredients": []}
        assert unwrap_expected_recipe(recipe) is recipe
        assert expected_recipe_count(recipe) == 1

    def test_envelope_yields_the_first_recipe(self):
        payload = {"recipes": [{"name": "First"}, {"name": "Second"}]}
        assert unwrap_expected_recipe(payload)["name"] == "First"
        assert expected_recipe_count(payload) == 2

    def test_empty_envelope_falls_back_to_the_payload(self):
        payload = {"recipes": []}
        assert unwrap_expected_recipe(payload) == payload
        assert expected_recipe_count(payload) == 0

    def test_non_dict_payloads_are_safe(self):
        assert unwrap_expected_recipe(None) == {}
        assert unwrap_expected_recipe([1, 2]) == {}
        assert expected_recipe_count(None) == 0

    def test_checked_in_multi_recipe_fixtures_unwrap_to_a_titled_recipe(self):
        fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "expected"
        multi = sorted(fixtures_dir.glob("multi_recipe_*.json"))
        assert multi, "no multi-recipe fixtures found"
        for path in multi:
            payload = json.loads(path.read_text())
            assert expected_recipe_count(payload) > 1, path.name
            assert unwrap_expected_recipe(payload).get("name"), path.name


class TestEvaluateFixturePayloads:
    @pytest.fixture
    def stub_strategy(self, monkeypatch):
        """Replace the extractor with a deterministic stub — no network."""
        extracted = {
            "name": "First",
            "ingredients": [{"name": "flour", "quantity": 1, "unit": "cup"}],
            "steps": [{"instruction": "mix"}],
            "confidence_score": 0.75,
            "confidence_source": "model",
        }
        monkeypatch.setattr(
            "src.fixture_runner.get_strategy_function",
            lambda _strategy: (lambda _input: extracted),
        )
        return extracted

    def _fixture(self, tmp_path, expected_payload):
        (tmp_path / "text").mkdir()
        (tmp_path / "expected").mkdir()
        input_path = tmp_path / "text" / "sample.txt"
        input_path.write_text("First\n1 cup flour\nmix")
        expected_path = tmp_path / "expected" / "sample.json"
        expected_path.write_text(json.dumps(expected_payload))
        return {
            "id": "sample",
            "input_path": input_path,
            "expected_path": expected_path,
            "input_type": "text",
        }

    def test_payloads_are_omitted_by_default(self, tmp_path, stub_strategy):
        fixture = self._fixture(tmp_path, {"name": "First", "ingredients": []})
        result = _evaluate_fixture(fixture, "text_extractor")
        assert result["error"] is None
        assert "extracted" not in result
        assert "expected" not in result

    def test_payloads_are_attached_on_request(self, tmp_path, stub_strategy):
        fixture = self._fixture(tmp_path, {"name": "First", "ingredients": []})
        result = _evaluate_fixture(fixture, "text_extractor", include_payloads=True)
        assert result["extracted"]["confidence_score"] == 0.75
        assert result["expected"]["name"] == "First"

    def test_multi_recipe_expected_is_scored_against_the_first_recipe(
        self, tmp_path, stub_strategy
    ):
        envelope = {
            "recipes": [
                {
                    "name": "First",
                    "ingredients": [{"name": "flour", "quantity": 1, "unit": "cup"}],
                    "steps": [{"instruction": "mix"}],
                },
                {"name": "Second", "ingredients": []},
            ]
        }
        fixture = self._fixture(tmp_path, envelope)
        result = _evaluate_fixture(fixture, "text_extractor", include_payloads=True)
        assert result["expected_recipe_count"] == 2
        assert result["expected"]["name"] == "First"
        # Scoring against the envelope instead would have found no
        # ingredients at all and reported a near-zero F1.
        assert result["scores"]["ingredients_recall"] == 1.0
        assert result["scores"]["overall_f1"] > 0.5
