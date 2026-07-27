"""End-to-end wiring check for the vision suite (bugs-imp-pho-7).

The unit tests in `test_vision_extraction_evaluator.py` poke the
evaluator directly. These drive the *real* `EvalRunner` over the *real*
committed manifest and PNG fixtures — manifest load, path resolution,
per-case grading, metric aggregation, and `_check_thresholds` — so the
one live vision run (which costs money and happens once) isn't the first
time the whole chain executes together.

Zero API calls: the run is `mock_ai`, and every case is served from a
cache seeded here. That is exactly the path a re-grade after the live
run takes, so it grades the same code the baseline capture will.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from src.config import EvalConfig, ThresholdConfig
from src.evaluators.vision_extraction_evaluator import VisionExtractionEvaluator
from src.runner import EvalRunner

SERVICE_DIR = Path(__file__).resolve().parent.parent
REAL_SUITE_DIR = SERVICE_DIR / "datasets" / "vision_extraction"
REAL_MANIFEST = REAL_SUITE_DIR / "manifest.yaml"


def _absolutized_manifest() -> dict:
    """The committed manifest with `image`/`expected` made absolute.

    Copying the suite into a tmp dir is what keeps the seeded cache out
    of the checkout (`datasets/*/cache/` is gitignored but still real).
    Absolute paths let the copy keep pointing at the *committed*
    fixtures, so this test grades the shipping dataset rather than a
    stand-in.
    """
    manifest = yaml.safe_load(REAL_MANIFEST.read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        for key in ("image", "expected"):
            if key in case:
                case[key] = str((REAL_SUITE_DIR / case[key]).resolve())
    return manifest


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    """A tmp `datasets/` holding only an absolutized vision suite."""
    suite = tmp_path / "vision_extraction"
    suite.mkdir(parents=True)
    (suite / "manifest.yaml").write_text(yaml.safe_dump(_absolutized_manifest()))
    return tmp_path


def _config(dataset_dir: Path, **overrides) -> EvalConfig:
    defaults = dict(
        dataset_dir=dataset_dir,
        mock_ai=True,
        cache_responses=True,
        # Sequential so a failure points at a case, not a worker.
        parallel_workers=1,
        thresholds=ThresholdConfig(recipe_count_accuracy=0.80),
    )
    defaults.update(overrides)
    return EvalConfig(**defaults)


def _seed_cache(config: EvalConfig, *, drop_recipes: set[str] = frozenset()) -> int:
    """Write one cached response per case, derived from its expected JSON.

    A case named in `drop_recipes` is cached one recipe short, which is
    how a fan-out regression looks to the gate.
    """
    evaluator = VisionExtractionEvaluator(config)
    cases = evaluator.load_cases()
    assert cases, "manifest copy produced no cases"

    for case in cases:
        recipes = evaluator._normalize_to_recipe_list(case.expected_data)
        if case.id in drop_recipes:
            recipes = recipes[:-1]
        payload = {"recipes": recipes, "_cost_cents": 3}
        cache_file = evaluator.cache_dir / f"{case.get_cache_key()}.json"
        cache_file.write_text(json.dumps(payload))

    return len(cases)


def test_seeded_run_grades_every_committed_case(dataset_dir):
    config = _config(dataset_dir)
    expected_cases = _seed_cache(config)

    suite = EvalRunner(config)._run_suite("vision_extraction")

    assert suite.total_cases == expected_cases
    assert suite.skipped_cases == 0, "seeded cache must not skip"
    assert [r.cache_hit for r in suite.results] == [True] * expected_cases
    assert [r.error for r in suite.results] == [None] * expected_cases


def test_seeded_run_emits_both_gated_metrics(dataset_dir):
    config = _config(dataset_dir)
    _seed_cache(config)

    suite = EvalRunner(config)._run_suite("vision_extraction")

    assert suite.metrics_summary["recipe_count_accuracy_avg"] == 1.0
    # Only the multi_recipe-tagged cases contribute this one — its
    # presence is what makes the tag-scoped half of the gate real.
    assert suite.metrics_summary["multi_recipe_count_accuracy_avg"] == 1.0
    assert "field_accuracy_avg" in suite.metrics_summary
    assert suite.passed_threshold is True


def test_multi_recipe_undercount_turns_the_suite_red(dataset_dir):
    """One recipe short on every fan-out case must fail the gate even
    though the single-recipe photos still score 1.0."""
    config = _config(dataset_dir)
    multi_ids = {
        case["id"]
        for case in _absolutized_manifest()["cases"]
        if "multi_recipe" in case.get("tags", [])
    }
    assert multi_ids, "manifest lost its multi_recipe cases"
    _seed_cache(config, drop_recipes=multi_ids)

    suite = EvalRunner(config)._run_suite("vision_extraction")

    assert suite.metrics_summary["multi_recipe_count_accuracy_avg"] == 0.0
    assert suite.metrics_summary["recipe_count_accuracy_avg"] > 0.0
    assert suite.passed_threshold is False


def test_cold_cache_run_skips_everything_and_stays_green(dataset_dir):
    """No cache + mock_ai = the zero-spend default. A no-op is not a
    regression, so the gate must not go red."""
    suite = EvalRunner(_config(dataset_dir))._run_suite("vision_extraction")

    assert suite.total_cases > 0
    assert suite.skipped_cases == suite.total_cases
    assert suite.metrics_summary == {}
    assert suite.passed_threshold is True


def test_tag_filter_narrows_the_run_to_fan_out_cases(dataset_dir):
    """`--tags multi_recipe` is the documented cheap re-run; it must
    still produce the tag-scoped metric the gate reads."""
    config = _config(dataset_dir, only_tags=["multi_recipe"])
    _seed_cache(config)

    suite = EvalRunner(config)._run_suite("vision_extraction")

    assert 0 < suite.total_cases < len(_absolutized_manifest()["cases"])
    assert suite.metrics_summary["multi_recipe_count_accuracy_avg"] == 1.0
    assert suite.passed_threshold is True


def test_missing_image_errors_without_billing(dataset_dir, tmp_path):
    """A fixture that vanished must surface as a case error, not as a
    live call — the evaluator checks the file before touching OpenAI."""
    suite_dir = dataset_dir / "vision_extraction"
    manifest = _absolutized_manifest()
    ghost = tmp_path / "not_there.png"
    manifest["cases"] = [dict(manifest["cases"][0], image=str(ghost))]
    (suite_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest))

    config = _config(dataset_dir, mock_ai=False)
    suite = EvalRunner(config)._run_suite("vision_extraction")

    assert suite.total_cases == 1
    assert suite.results[0].error is not None
    assert suite.results[0].cost_cents == 0


def test_run_writes_no_cache_into_the_checkout(dataset_dir):
    """Guard the guard: the tmp-dataset trick is the only reason these
    tests don't litter `datasets/vision_extraction/cache/`."""
    real_cache = REAL_SUITE_DIR / "cache"
    before = sorted(p.name for p in real_cache.glob("*.json")) if real_cache.exists() else []

    config = _config(dataset_dir)
    _seed_cache(config)
    EvalRunner(config)._run_suite("vision_extraction")

    after = sorted(p.name for p in real_cache.glob("*.json")) if real_cache.exists() else []
    assert before == after
    assert (dataset_dir / "vision_extraction" / "cache").exists()


def test_full_run_reports_the_suite_under_its_name(dataset_dir):
    """`EvalRunner.run` (what the CLI calls) keys the suite correctly and
    the payload round-trips through the results JSON the baseline
    capture reads."""
    config = _config(dataset_dir)
    _seed_cache(config)

    results = EvalRunner(config).run(["vision_extraction"])
    payload = json.loads(json.dumps(results.to_dict()))

    suite = payload["suite_results"]["vision_extraction"]
    assert suite["suite_name"] == "vision_extraction"
    assert suite["passed_threshold"] is True
    assert suite["metrics_summary"]["multi_recipe_count_accuracy_avg"] == 1.0
    assert len(suite["results"]) == suite["total_cases"]


def test_tmp_suite_stays_in_sync_with_the_committed_manifest(dataset_dir):
    """If someone adds a case to the real manifest, these tests pick it
    up automatically — assert that rather than trusting it."""
    shutil.rmtree(dataset_dir / "vision_extraction" / "cache", ignore_errors=True)
    config = _config(dataset_dir)
    loaded = {c.id for c in VisionExtractionEvaluator(config).load_cases()}
    committed = {c["id"] for c in yaml.safe_load(REAL_MANIFEST.read_text())["cases"]}

    assert loaded == committed
