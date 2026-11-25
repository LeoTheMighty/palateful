"""End-to-end wiring check for the *text* suite (bugs-imp-pho-7).

The vision suite's acceptance criterion is "graded at the same bar as
text". That claim was hollow: the committed `recipe_extraction` manifest
declares `text:` inputs and `extractor: text`, but the evaluator only read
`html:` and only knew the `json_ld`/`ai`/`auto` extractors, so all three
fan-out cases errored with "HTML content not found" before any metric was
computed — the `recipe_count_accuracy` gate had nothing to grade.

These tests drive the real `EvalRunner` over the real committed manifest
and text fixtures, mirroring `test_vision_suite_end_to_end.py`. Zero API
calls: the run is `mock_ai` and every case is served from a cache seeded
here.
"""

import json
from pathlib import Path

import pytest
import yaml

from src.config import EvalConfig, ThresholdConfig
from src.evaluators.recipe_extraction_evaluator import RecipeExtractionEvaluator
from src.runner import EvalRunner

SERVICE_DIR = Path(__file__).resolve().parent.parent
REAL_SUITE_DIR = SERVICE_DIR / "datasets" / "recipe_extraction"
REAL_MANIFEST = REAL_SUITE_DIR / "manifest.yaml"

SUITE = "recipe_extraction"


def _absolutized_manifest() -> dict:
    """The committed manifest with `text`/`html`/`expected` made absolute.

    Same trick as the vision suite: the copy lives in a tmp dataset dir so
    the seeded cache never lands in the checkout, but it still grades the
    *committed* fixtures.
    """
    manifest = yaml.safe_load(REAL_MANIFEST.read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        for key in ("text", "html", "expected"):
            if key in case:
                case[key] = str((REAL_SUITE_DIR / case[key]).resolve())
    return manifest


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    suite = tmp_path / SUITE
    suite.mkdir(parents=True)
    (suite / "manifest.yaml").write_text(yaml.safe_dump(_absolutized_manifest()))
    return tmp_path


def _config(dataset_dir: Path, **overrides) -> EvalConfig:
    defaults = dict(
        dataset_dir=dataset_dir,
        mock_ai=True,
        cache_responses=True,
        parallel_workers=1,
        thresholds=ThresholdConfig(recipe_count_accuracy=0.80),
    )
    defaults.update(overrides)
    return EvalConfig(**defaults)


def _seed_cache(config: EvalConfig, *, drop_recipes: set[str] = frozenset()) -> int:
    evaluator = RecipeExtractionEvaluator(config)
    cases = evaluator.load_cases()
    assert cases, "manifest copy produced no cases"

    for case in cases:
        recipes = evaluator._normalize_to_recipe_list(case.expected_data)
        if case.id in drop_recipes:
            recipes = recipes[:-1]
        payload = {"recipes": recipes, "_cost_cents": 2}
        cache_file = evaluator.cache_dir / f"{case.get_cache_key()}.json"
        cache_file.write_text(json.dumps(payload))

    return len(cases)


# ---------- case loading (the regression) ----------


def test_manifest_text_inputs_actually_load(dataset_dir):
    """Regression: every case must arrive with its input content read.

    Before the fix `load_cases` only looked at `html:`, so `input_data`
    was `None` for all three cases and `evaluate` bailed out immediately.
    """
    cases = RecipeExtractionEvaluator(_config(dataset_dir)).load_cases()

    assert cases
    for case in cases:
        assert case.input_path.is_file(), f"{case.id}: input path does not exist"
        assert case.input_data, f"{case.id}: input content not loaded"
        assert case.expected_data is not None, f"{case.id}: expected JSON not loaded"


def test_committed_manifest_declares_only_multi_recipe_fan_out_cases():
    """Guard the premise of the gate: these fixtures are what makes
    `recipe_count_accuracy` meaningful in the text suite."""
    cases = yaml.safe_load(REAL_MANIFEST.read_text(encoding="utf-8"))["cases"]

    assert cases
    assert all("multi_recipe" in case.get("tags", []) for case in cases)


# ---------- grading ----------


def test_seeded_run_grades_every_committed_case(dataset_dir):
    config = _config(dataset_dir)
    expected_cases = _seed_cache(config)

    suite = EvalRunner(config)._run_suite(SUITE)

    assert suite.total_cases == expected_cases
    assert [r.error for r in suite.results] == [None] * expected_cases
    assert [r.cache_hit for r in suite.results] == [True] * expected_cases


def test_seeded_run_emits_the_gated_count_metric(dataset_dir):
    """The whole point: `recipe_count_accuracy_avg` must be a real
    measurement, not the 1.0 default `_check_thresholds` falls back to
    when the metric is missing."""
    config = _config(dataset_dir)
    _seed_cache(config)

    suite = EvalRunner(config)._run_suite(SUITE)

    assert "recipe_count_accuracy_avg" in suite.metrics_summary
    assert suite.metrics_summary["recipe_count_accuracy_avg"] == 1.0
    assert suite.metrics_summary["field_accuracy_avg"] > 0
    assert suite.passed_threshold is True


def test_undercount_turns_the_text_suite_red(dataset_dir):
    """A fan-out regression (one recipe short everywhere) must fail the
    same 0.80 gate the vision suite is held to."""
    config = _config(dataset_dir)
    all_ids = {case["id"] for case in _absolutized_manifest()["cases"]}
    _seed_cache(config, drop_recipes=all_ids)

    suite = EvalRunner(config)._run_suite(SUITE)

    assert suite.metrics_summary["recipe_count_accuracy_avg"] == 0.0
    assert suite.passed_threshold is False


def test_cold_cache_run_skips_everything_and_stays_green(dataset_dir):
    """`mock_ai` + no cache is the zero-spend default. These cases have no
    offline extractor, so a no-op run must skip — scoring them 0.0 would
    report an unrun suite as a fan-out regression."""
    suite = EvalRunner(_config(dataset_dir))._run_suite(SUITE)

    assert suite.total_cases > 0
    assert suite.skipped_cases == suite.total_cases
    assert suite.metrics_summary == {}
    assert suite.passed_threshold is True


def test_all_errored_run_still_goes_red(dataset_dir):
    """The skipped-run amnesty must not extend to errors: a case whose
    input vanished is a broken suite, not a no-op."""
    manifest = _absolutized_manifest()
    manifest["cases"] = [dict(manifest["cases"][0], text=str(dataset_dir / "gone.txt"))]
    (dataset_dir / SUITE / "manifest.yaml").write_text(yaml.safe_dump(manifest))

    suite = EvalRunner(_config(dataset_dir))._run_suite(SUITE)

    assert suite.skipped_cases == 0
    assert suite.results[0].error is not None
    assert suite.passed_threshold is False


def test_run_writes_no_cache_into_the_checkout(dataset_dir):
    real_cache = REAL_SUITE_DIR / "cache"
    before = sorted(p.name for p in real_cache.glob("*.json")) if real_cache.exists() else []

    config = _config(dataset_dir)
    _seed_cache(config)
    EvalRunner(config)._run_suite(SUITE)

    after = sorted(p.name for p in real_cache.glob("*.json")) if real_cache.exists() else []
    assert before == after


# ---------- the `text` extractor branch ----------


class _FakeRecipe:
    def __init__(self, title):
        self.title = title
        self.ingredients = []


class _FakeResult:
    def __init__(self, recipes, success=True):
        self.success = success
        self.recipes = list(recipes)
        # The deprecated singular alias, as `ExtractionResult.__post_init__`
        # populates it. Reading this instead of `recipes` is the bug the
        # multi-recipe wrapper exists to prevent.
        self.recipe = recipes[0] if recipes else None
        self.ai_cost_cents = 7


def test_multi_recipe_wrapper_reads_recipes_not_the_deprecated_alias(dataset_dir):
    evaluator = RecipeExtractionEvaluator(_config(dataset_dir))

    wrapped = evaluator._to_multi_recipe_dict(
        _FakeResult([_FakeRecipe("a"), _FakeRecipe("b"), _FakeRecipe("c")])
    )

    assert [r["title"] for r in wrapped["recipes"]] == ["a", "b", "c"]


def test_text_extractor_branch_is_dispatched_and_wrapped(dataset_dir, monkeypatch):
    """`extractor: text` (what the manifest declares) must reach
    `extract_recipe_from_text` — it previously matched no branch, so
    extraction silently returned None."""
    import utils.services.recipe_extractors.text_extractor as text_extractor

    seen = {}

    def _fake(text, openai_client=None):
        seen["text"] = text
        return _FakeResult([_FakeRecipe("x"), _FakeRecipe("y")])

    monkeypatch.setattr(text_extractor, "extract_recipe_from_text", _fake)

    evaluator = RecipeExtractionEvaluator(_config(dataset_dir, mock_ai=False))
    extracted, _duration, cost = evaluator._extract_recipe(
        html="Some OCR text", url=None, extractor_type="text"
    )

    assert seen["text"] == "Some OCR text"
    assert [r["title"] for r in extracted["recipes"]] == ["x", "y"]
    assert cost == 7


def test_failed_text_extraction_is_not_cached_as_an_empty_fan_out(dataset_dir, monkeypatch):
    """A failure must return None, not `{"recipes": []}` — the latter is
    truthy and `evaluate` would cache it, replaying a fabricated 0.0 on
    every later mock re-grade (same defect already fixed in the vision
    evaluator)."""
    import utils.services.recipe_extractors.text_extractor as text_extractor

    monkeypatch.setattr(
        text_extractor,
        "extract_recipe_from_text",
        lambda text, openai_client=None: _FakeResult([], success=False),
    )

    evaluator = RecipeExtractionEvaluator(_config(dataset_dir, mock_ai=False))
    extracted, _duration, _cost = evaluator._extract_recipe(
        html="Some OCR text", url=None, extractor_type="text"
    )

    assert extracted is None


def test_mock_mode_never_calls_the_text_extractor(dataset_dir, monkeypatch):
    """Cost guard: `mock_ai` with a cold cache must not bill a text call."""
    import utils.services.recipe_extractors.text_extractor as text_extractor

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("live text extraction attempted in mock mode")

    monkeypatch.setattr(text_extractor, "extract_recipe_from_text", _boom)

    evaluator = RecipeExtractionEvaluator(_config(dataset_dir))
    extracted, duration, cost = evaluator._extract_recipe(
        html="Some OCR text", url=None, extractor_type="text"
    )

    assert extracted is None
    assert (duration, cost) == (0.0, 0)
