"""Tests for VisionExtractionEvaluator + its gate (bugs-imp-pho-7).

No live API calls: the extractor is monkeypatched everywhere. Anything
that would bill OpenAI is asserted *not* to happen.
"""

import json
from pathlib import Path

import pytest

from src.config import EvalConfig, ThresholdConfig
from src.evaluators.base import EvalCase
from src.evaluators.vision_extraction_evaluator import VisionExtractionEvaluator
from src.runner import EvalRunner

REPO_EVAL_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_EVAL_DIR / "datasets"


def _make_evaluator(**overrides) -> VisionExtractionEvaluator:
    config = EvalConfig(dataset_dir=DATASET_DIR, cache_responses=False, **overrides)
    return VisionExtractionEvaluator(config)


class _FakeIngredient:
    def __init__(self, text: str):
        self.text = text
        self.quantity = None
        self.unit = None
        self.name = text
        self.notes = None
        self.is_optional = False


class _FakeRecipe:
    def __init__(self, name: str, ingredients: int = 0, instructions: str = ""):
        self.name = name
        self.description = None
        self.ingredients = [_FakeIngredient(f"ing {i}") for i in range(ingredients)]
        self.instructions = instructions
        self.servings = None


class _FakeExtraction:
    def __init__(self, recipes, success=True, cost_cents=3):
        self.success = success
        self.recipes = recipes
        self.ai_cost_cents = cost_cents
        self.error_message = None if success else "No recipe found"
        self.error_code = None if success else "AI_NO_RECIPE_FOUND"


def _patch_extractor(monkeypatch, extraction, calls=None):
    """Patch the production vision extractor at its import site."""
    import utils.services.recipe_extractors.vision_extractor as ve

    def _fake(image, openai_client=None):
        if calls is not None:
            calls.append(image)
        return extraction

    monkeypatch.setattr(ve, "extract_recipe_from_image", _fake)


# ---------- load_cases ----------


def test_load_cases_reads_committed_manifest():
    evaluator = _make_evaluator()
    cases = evaluator.load_cases()

    assert {c.id for c in cases} == {
        "banana_bread",
        "simple_pasta",
        "multi_recipe_facing_pages",
        "multi_recipe_side_by_side",
        "multi_recipe_three_panel",
    }


def test_load_cases_resolves_shared_fixture_paths():
    """Manifest paths use `../../fixtures/...` so image cases reuse the
    text suite's expected JSON. They must resolve to real files."""
    evaluator = _make_evaluator()

    for case in evaluator.load_cases():
        assert case.input_path is not None
        assert case.input_path.exists(), case.id
        assert case.input_path.suffix == ".png"
        assert case.expected_path is not None
        assert case.expected_path.exists(), case.id
        assert ".." not in case.input_path.parts


def test_load_cases_populates_expected_data_and_tags():
    evaluator = _make_evaluator()
    by_id = {c.id: c for c in evaluator.load_cases()}

    multi = by_id["multi_recipe_facing_pages"]
    assert "multi_recipe" in multi.tags
    assert len(multi.expected_data["recipes"]) == 2

    single = by_id["banana_bread"]
    assert "single_recipe" in single.tags
    assert single.expected_data["name"]


def test_load_cases_leaves_input_data_unset_but_cache_key_works():
    """Image bytes are hashed off disk; keeping every PNG resident would
    only bloat memory."""
    evaluator = _make_evaluator()
    case = evaluator.load_cases()[0]

    assert case.input_data is None
    key = case.get_cache_key()
    assert len(key) == 16
    # Same file -> stable key; different file -> different key.
    assert key == case.get_cache_key()
    other = [c for c in evaluator.load_cases() if c.id != case.id][0]
    assert other.get_cache_key() != key


def test_load_cases_falls_back_to_conventional_paths(tmp_path):
    """A manifest entry with no explicit `image`/`expected` resolves to
    the suite-local defaults (the text suite's `text:`-key trap)."""
    suite = tmp_path / "vision_extraction"
    (suite / "images").mkdir(parents=True)
    (suite / "expected").mkdir()
    (suite / "images" / "solo.png").write_bytes(b"not-a-real-png")
    (suite / "expected" / "solo.json").write_text(json.dumps({"name": "Solo"}))
    (suite / "manifest.yaml").write_text("cases:\n  - id: solo\n    tags: [image]\n")

    evaluator = _make_evaluator()
    evaluator.config.dataset_dir = tmp_path
    cases = evaluator.load_cases()

    assert len(cases) == 1
    assert cases[0].input_path.name == "solo.png"
    assert cases[0].expected_data == {"name": "Solo"}


# ---------- evaluate: cost guards ----------


def test_mock_ai_without_cache_skips_instead_of_billing(monkeypatch):
    calls: list = []
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A")]), calls)

    evaluator = _make_evaluator(mock_ai=True)
    case = [c for c in evaluator.load_cases() if c.id == "banana_bread"][0]
    monkeypatch.setattr(evaluator, "get_cached_response", lambda key: None)

    result = evaluator.evaluate(case)

    assert result.skipped is True
    assert calls == []


def test_cached_response_short_circuits_the_api(monkeypatch):
    calls: list = []
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A")]), calls)

    evaluator = _make_evaluator(mock_ai=True)
    case = [c for c in evaluator.load_cases() if c.id == "multi_recipe_facing_pages"][0]
    monkeypatch.setattr(
        evaluator,
        "get_cached_response",
        lambda key: {
            "recipes": [{"name": "A", "ingredients": []}, {"name": "B", "ingredients": []}],
            "_cost_cents": 7,
        },
    )

    result = evaluator.evaluate(case)

    assert calls == []
    assert result.cache_hit is True
    assert result.cost_cents == 7
    assert result.metrics["recipe_count_accuracy"] == 1.0


def test_missing_image_errors_without_calling_the_api(monkeypatch):
    calls: list = []
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A")]), calls)

    evaluator = _make_evaluator()
    case = EvalCase(id="ghost", input_path=Path("/nope/ghost.png"))

    result = evaluator.evaluate(case)

    assert result.error is not None
    assert "ghost" in result.error
    assert calls == []


# ---------- evaluate: metrics ----------


def test_evaluate_multi_recipe_exact_count(monkeypatch):
    _patch_extractor(
        monkeypatch,
        _FakeExtraction([_FakeRecipe("A", ingredients=2), _FakeRecipe("B", ingredients=2)]),
    )

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "multi_recipe_facing_pages"][0]

    result = evaluator.evaluate(case)

    assert result.metrics["recipe_count_accuracy"] == 1.0
    assert result.metrics["expected_recipe_count"] == 2
    assert result.metrics["actual_recipe_count"] == 2
    assert result.cost_cents == 3


def test_evaluate_undercount_scores_zero_on_multi_case(monkeypatch):
    """The whole point of the suite: a merged fan-out must be graded 0."""
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A+B", ingredients=4)]))

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "multi_recipe_three_panel"][0]

    result = evaluator.evaluate(case)

    assert result.metrics["actual_recipe_count"] == 1
    assert result.metrics["expected_recipe_count"] == 3
    assert result.metrics["recipe_count_accuracy"] == 0.0
    assert result.metrics["multi_recipe_count_accuracy"] == 0.0


def test_multi_recipe_metric_only_on_tagged_cases(monkeypatch):
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A", ingredients=1)]))

    evaluator = _make_evaluator()
    single = [c for c in evaluator.load_cases() if c.id == "banana_bread"][0]

    result = evaluator.evaluate(single)

    assert result.metrics["recipe_count_accuracy"] == 1.0
    assert "multi_recipe_count_accuracy" not in result.metrics


def test_evaluate_emits_the_same_metric_keys_as_the_text_suite(monkeypatch):
    _patch_extractor(
        monkeypatch,
        _FakeExtraction([_FakeRecipe("A", ingredients=2), _FakeRecipe("B", ingredients=2)]),
    )

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "multi_recipe_side_by_side"][0]

    metrics = evaluator.evaluate(case).metrics

    for key in (
        "field_accuracy",
        "ingredient_count_accuracy",
        "instruction_similarity",
        "recipe_count_accuracy",
        "timer_extraction_f1",
        "unit_enum_compliance",
    ):
        assert key in metrics, key


def test_failed_extraction_scores_zero_rather_than_erroring(monkeypatch):
    """A model that finds no recipe is a miss, not an infra failure — it
    must stay in the average instead of dropping out as an error."""
    _patch_extractor(monkeypatch, _FakeExtraction([], success=False))

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "multi_recipe_facing_pages"][0]

    result = evaluator.evaluate(case)

    assert result.error is None
    assert result.metrics["recipe_count_accuracy"] == 0.0
    assert result.metrics["multi_recipe_count_accuracy"] == 0.0
    assert result.passed is False


def test_extractor_exception_becomes_a_case_error(monkeypatch):
    import utils.services.recipe_extractors.vision_extractor as ve

    def _boom(image, openai_client=None):
        raise RuntimeError("socket exploded")

    monkeypatch.setattr(ve, "extract_recipe_from_image", _boom)

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "simple_pasta"][0]

    result = evaluator.evaluate(case)

    assert result.error == "socket exploded"
    assert result.passed is False


def _cached_evaluator(cache_root, **overrides) -> VisionExtractionEvaluator:
    """An evaluator whose cache lives in a tmp dir, so a write is visible
    without touching the real (gitignored but shared) datasets tree."""
    config = EvalConfig(dataset_dir=cache_root, cache_responses=True, **overrides)
    return VisionExtractionEvaluator(config)


def _real_case(case_id: str) -> EvalCase:
    return [c for c in _make_evaluator().load_cases() if c.id == case_id][0]


def test_failed_extraction_is_not_written_to_the_cache(tmp_path, monkeypatch):
    """Regression: `{"recipes": []}` is a truthy dict, so a failed
    extraction used to be cached like a real answer. One run without an
    API key then poisoned the cache, and every later mock re-grade
    replayed a fabricated 0.0 that was indistinguishable from a genuine
    model miss."""
    _patch_extractor(monkeypatch, _FakeExtraction([], success=False))

    evaluator = _cached_evaluator(tmp_path)
    result = evaluator.evaluate(_real_case("multi_recipe_facing_pages"))

    assert result.metrics["recipe_count_accuracy"] == 0.0  # still graded as a miss
    assert list(evaluator.cache_dir.glob("*.json")) == []


def test_successful_extraction_is_written_to_the_cache(tmp_path, monkeypatch):
    """Guard the inverse: the fix must not disable caching outright, or
    the post-live-run re-grade path loses its only input."""
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A"), _FakeRecipe("B")]))

    evaluator = _cached_evaluator(tmp_path)
    evaluator.evaluate(_real_case("multi_recipe_facing_pages"))

    cached = list(evaluator.cache_dir.glob("*.json"))
    assert len(cached) == 1
    assert len(json.loads(cached[0].read_text())["recipes"]) == 2


def test_mock_rerun_after_a_failed_run_skips_instead_of_replaying_zero(
    tmp_path, monkeypatch
):
    """End of the same regression: with nothing cached, the next mock run
    must fall into the skip guard rather than grading a phantom zero."""
    _patch_extractor(monkeypatch, _FakeExtraction([], success=False))
    case = _real_case("multi_recipe_facing_pages")

    _cached_evaluator(tmp_path).evaluate(case)  # failed live-ish run
    replay = _cached_evaluator(tmp_path, mock_ai=True).evaluate(case)

    assert replay.skipped is True
    assert "recipe_count_accuracy" not in replay.metrics


def test_extractor_receives_image_bytes(monkeypatch):
    calls: list = []
    _patch_extractor(monkeypatch, _FakeExtraction([_FakeRecipe("A")]), calls)

    evaluator = _make_evaluator()
    case = [c for c in evaluator.load_cases() if c.id == "simple_pasta"][0]
    evaluator.evaluate(case)

    assert len(calls) == 1
    assert isinstance(calls[0], bytes)
    assert calls[0].startswith(b"\x89PNG")


# ---------- runner wiring + gate ----------


def test_runner_resolves_the_vision_suite():
    runner = EvalRunner(_make_evaluator().config)
    evaluator = runner._get_evaluator("vision_extraction")

    assert isinstance(evaluator, VisionExtractionEvaluator)
    assert evaluator.name == "vision_extraction"


def _gate(metrics: dict, threshold: float = 0.80) -> bool:
    config = EvalConfig(thresholds=ThresholdConfig(recipe_count_accuracy=threshold))
    return EvalRunner(config)._check_thresholds("vision_extraction", metrics)


@pytest.mark.parametrize(
    "count_avg,expected",
    [(1.0, True), (0.8, True), (0.79, False), (0.0, False)],
)
def test_gate_enforces_080_recipe_count_accuracy(count_avg, expected):
    assert _gate({"recipe_count_accuracy_avg": count_avg}) is expected


def test_gate_fails_when_multi_recipe_subset_lags():
    """Single-recipe photos score ~1.0 for free — they must not paper
    over a fan-out regression."""
    assert (
        _gate({
            "recipe_count_accuracy_avg": 0.90,
            "multi_recipe_count_accuracy_avg": 0.50,
        })
        is False
    )


def test_gate_does_not_yet_enforce_field_accuracy():
    """field_accuracy is baseline-only for the vision suite (AC4)."""
    assert (
        _gate({
            "recipe_count_accuracy_avg": 1.0,
            "multi_recipe_count_accuracy_avg": 1.0,
            "field_accuracy_avg": 0.10,
        })
        is True
    )


def test_gate_passes_on_an_all_skipped_run():
    """mock_ai with a cold cache produces no metrics; that is a no-op,
    not a red suite."""
    assert _gate({}) is True


def test_vision_suite_is_opt_in_from_the_cli():
    from src.main import ALL_SUITES, DEFAULT_SUITES

    assert "vision_extraction" in ALL_SUITES
    assert "vision_extraction" not in DEFAULT_SUITES
