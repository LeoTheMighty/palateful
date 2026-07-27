"""Tests for scripts/capture_vision_baseline.py (bugs-imp-pho-7 AC4).

The live vision run happens once and costs money, so the step that turns
it into the committed baseline has to work the first time. These tests
drive the capture script off a synthetic results payload — and off a
real seeded run — without any API calls.
"""

import functools
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
BASELINE_PATH = SERVICE_DIR / "baselines" / "vision_extraction_baseline.json"


@functools.cache
def _load_script():
    """Import scripts/capture_vision_baseline.py without packaging it."""
    name = "capture_vision_baseline"
    spec = importlib.util.spec_from_file_location(
        name, SERVICE_DIR / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _case(case_id, *, expected_n, actual_n, field_accuracy, tags_multi=False, **over):
    metrics = {
        "recipe_count_accuracy": 1.0 if expected_n == actual_n else 0.0,
        "expected_recipe_count": expected_n,
        "actual_recipe_count": actual_n,
        "field_accuracy": field_accuracy,
        # Reported as a dict by the evaluator, not a scalar.
        "unit_enum_compliance": {
            "compliance": 0.75,
            "total_units": 4,
            "non_canonical": {"knob": 1},
        },
    }
    if tags_multi:
        metrics["multi_recipe_count_accuracy"] = metrics["recipe_count_accuracy"]
    payload = {
        "case_id": case_id,
        "passed": field_accuracy >= 0.9,
        "skipped": False,
        "metrics": metrics,
        "error": None,
        "cost_cents": 3,
        "cache_hit": False,
    }
    payload.update(over)
    return payload


def _results(**suite_over):
    suite = {
        "suite_name": "vision_extraction",
        "total_cases": 3,
        "passed_cases": 2,
        "failed_cases": 1,
        "skipped_cases": 0,
        "duration_seconds": 12.5,
        "passed_threshold": True,
        "metrics_summary": {
            "recipe_count_accuracy_avg": 1.0,
            "multi_recipe_count_accuracy_avg": 1.0,
            "field_accuracy_avg": 0.82,
            "ingredient_count_accuracy_avg": 0.91,
        },
        "results": [
            _case("banana_bread", expected_n=1, actual_n=1, field_accuracy=0.95),
            _case("simple_pasta", expected_n=1, actual_n=1, field_accuracy=0.88),
            _case(
                "multi_recipe_facing_pages",
                expected_n=2,
                actual_n=2,
                field_accuracy=0.63,
                tags_multi=True,
            ),
        ],
    }
    suite.update(suite_over)
    return {
        "timestamp": "2026-07-27T22:00:00",
        "suite_results": {"vision_extraction": suite},
        "total_duration_seconds": 12.5,
        "config_snapshot": {"mock_ai": False},
    }


def _build(results, **over):
    script = _load_script()
    kwargs = dict(
        generated_at="2026-07-27T22:00:00+00:00",
        commit="abc1234",
        results_file="results/vision-baseline.json",
    )
    kwargs.update(over)
    return script.build_baseline(results, **kwargs)


# ---------- committed placeholder ----------


def test_committed_baseline_is_valid_json_with_null_placeholders():
    baseline = json.loads(BASELINE_PATH.read_text())

    assert baseline["_suite"] == "vision_extraction"
    assert baseline["_generated_at"] is None, "placeholder must stay unpopulated"
    assert set(baseline["metrics"]) == set(_load_script().BASELINE_METRICS)
    assert all(v is None for v in baseline["metrics"].values())


def test_committed_baseline_pins_the_080_hard_gate():
    thresholds = json.loads(BASELINE_PATH.read_text())["thresholds"]

    assert thresholds["recipe_count_accuracy"] == 0.8
    assert thresholds["multi_recipe_count_accuracy"] == 0.8
    # field_accuracy is deliberately soft until a real number lands.
    assert thresholds["field_accuracy"] is None


def test_committed_baseline_documents_the_capture_command():
    comment = json.loads(BASELINE_PATH.read_text())["_comment"]

    assert "capture_vision_baseline.py" in comment
    assert "--suite vision_extraction" in comment


# ---------- build_baseline ----------


def test_build_baseline_carries_every_reported_metric():
    baseline = _build(_results())

    assert baseline["metrics"]["recipe_count_accuracy_avg"] == 1.0
    assert baseline["metrics"]["multi_recipe_count_accuracy_avg"] == 1.0
    assert baseline["metrics"]["field_accuracy_avg"] == 0.82


def test_build_baseline_nulls_metrics_the_run_did_not_emit():
    """A metric the run never produced must read as 'not measured', not
    as a zero that a future regression check would compare against."""
    baseline = _build(_results())

    assert baseline["metrics"]["timer_extraction_f1_avg"] is None
    assert "timer_extraction_f1_avg" in baseline["metrics"]


def test_build_baseline_records_provenance_and_cost():
    baseline = _build(_results())

    assert baseline["_generated_at"] == "2026-07-27T22:00:00+00:00"
    assert baseline["_generated_commit"] == "abc1234"
    assert baseline["_results_file"] == "results/vision-baseline.json"
    assert baseline["run"]["cost_cents"] == 9
    assert baseline["run"]["passed_threshold"] is True


def test_build_baseline_pins_per_case_counts():
    per_case = _build(_results())["per_case"]

    assert set(per_case) == {
        "banana_bread",
        "simple_pasta",
        "multi_recipe_facing_pages",
    }
    assert per_case["multi_recipe_facing_pages"]["expected_recipe_count"] == 2
    assert per_case["multi_recipe_facing_pages"]["field_accuracy"] == 0.63


def test_build_baseline_flattens_the_dict_valued_unit_metric():
    """`unit_enum_compliance` is a dict, so the runner never averages it
    into a `_avg` key. Its scalar is pinned per-case instead — listing a
    `unit_enum_compliance_avg` that can never populate would be a
    permanently-null row pretending to be a measurement."""
    script = _load_script()
    baseline = _build(_results())

    assert "unit_enum_compliance_avg" not in script.BASELINE_METRICS
    assert baseline["per_case"]["banana_bread"]["unit_enum_compliance"] == 0.75


def test_build_baseline_promotes_field_accuracy_into_thresholds():
    """The soft field_accuracy bar is set from the captured run — that is
    the whole point of AC4's regression reference."""
    thresholds = _build(_results())["thresholds"]

    assert thresholds["field_accuracy"] == 0.82
    assert thresholds["recipe_count_accuracy"] == 0.8


def test_build_baseline_preserves_the_explanatory_comment():
    previous = json.loads(BASELINE_PATH.read_text())
    baseline = _build(_results(), previous=previous)

    assert baseline["_comment"] == previous["_comment"]
    assert baseline["thresholds"]["_count_enforcement"].startswith("hard")


def test_build_baseline_rejects_a_payload_without_the_vision_suite():
    with pytest.raises(LookupError, match="no 'vision_extraction' suite"):
        _build({"suite_results": {"ocr": {}}})


def test_build_baseline_rejects_an_all_skipped_run():
    """A mock/cold-cache run has real structure but no numbers — capturing
    it would enshrine an empty baseline as if it were measured."""
    skipped = [dict(r, skipped=True, metrics={}) for r in _results()["suite_results"]["vision_extraction"]["results"]]

    with pytest.raises(LookupError, match="skipped"):
        _build(_results(results=skipped, skipped_cases=3))


def test_build_baseline_keeps_a_case_error_visible():
    results = _results()
    results["suite_results"]["vision_extraction"]["results"][0]["error"] = "boom"

    per_case = _build(results)["per_case"]

    assert per_case["banana_bread"]["error"] == "boom"


# ---------- markdown rendering ----------


def test_render_markdown_labels_the_hard_gates():
    markdown = _load_script().render_markdown(_build(_results()))

    assert "`recipe_count_accuracy_avg` | 1.000 | hard ≥ 0.800" in markdown
    assert "`multi_recipe_count_accuracy_avg` | 1.000 | hard ≥ 0.800" in markdown
    assert "`field_accuracy_avg` | 0.820 | reported" in markdown


def test_render_markdown_includes_a_per_case_table():
    markdown = _load_script().render_markdown(_build(_results()))

    assert "| Case | Expected N | Actual N | field_accuracy |" in markdown
    assert "`multi_recipe_facing_pages` | 2 | 2 | 0.630" in markdown


def test_render_markdown_renders_missing_numbers_as_dashes():
    markdown = _load_script().render_markdown(_build(_results()))

    assert "`timer_extraction_f1_avg` | — |" in markdown


# ---------- CLI ----------


def test_main_writes_the_baseline_file(tmp_path, capsys):
    script = _load_script()
    results_path = tmp_path / "run.json"
    results_path.write_text(json.dumps(_results()))
    out_path = tmp_path / "baseline.json"

    code = script.main(["--results", str(results_path), "--output", str(out_path)])

    assert code == 0
    written = json.loads(out_path.read_text())
    assert written["metrics"]["field_accuracy_avg"] == 0.82
    assert "baseline written" in capsys.readouterr().out


def test_main_dry_run_leaves_the_file_alone(tmp_path, capsys):
    script = _load_script()
    results_path = tmp_path / "run.json"
    results_path.write_text(json.dumps(_results()))
    out_path = tmp_path / "baseline.json"

    code = script.main(
        ["--results", str(results_path), "--output", str(out_path), "--dry-run"]
    )

    assert code == 0
    assert not out_path.exists()
    assert json.loads(capsys.readouterr().out)["metrics"]["field_accuracy_avg"] == 0.82


def test_main_exits_2_when_there_is_nothing_to_capture(tmp_path):
    script = _load_script()
    results_path = tmp_path / "run.json"
    results_path.write_text(json.dumps({"suite_results": {}}))

    assert script.main(["--results", str(results_path), "--output", str(tmp_path / "b.json")]) == 2


def test_main_exits_1_on_an_unreadable_results_file(tmp_path):
    script = _load_script()
    bad = tmp_path / "nope.json"

    assert script.main(["--results", str(bad), "--output", str(tmp_path / "b.json")]) == 1


def test_main_merges_into_the_committed_placeholder(tmp_path):
    """Capturing must not blow away the file's explanatory comment."""
    script = _load_script()
    results_path = tmp_path / "run.json"
    results_path.write_text(json.dumps(_results()))
    out_path = tmp_path / "baseline.json"
    out_path.write_text(BASELINE_PATH.read_text())

    assert script.main(["--results", str(results_path), "--output", str(out_path)]) == 0
    written = json.loads(out_path.read_text())
    assert "capture_vision_baseline.py" in written["_comment"]
    assert written["_generated_at"] is not None


# ---------- capture over a real run ----------


def test_capture_round_trips_a_real_seeded_run(tmp_path):
    """Wire the actual runner output into the actual capture path — the
    two halves of AC4 have to agree on the JSON shape."""
    import yaml
    from test_vision_suite_end_to_end import (
        _absolutized_manifest,
        _config,
        _seed_cache,
    )

    from src.runner import EvalRunner

    dataset_dir = tmp_path / "datasets"
    suite_dir = dataset_dir / "vision_extraction"
    suite_dir.mkdir(parents=True)
    (suite_dir / "manifest.yaml").write_text(yaml.safe_dump(_absolutized_manifest()))

    config = _config(dataset_dir)
    _seed_cache(config)
    results = EvalRunner(config).run(["vision_extraction"])

    baseline = _build(json.loads(json.dumps(results.to_dict())))

    assert baseline["metrics"]["recipe_count_accuracy_avg"] == 1.0
    assert baseline["metrics"]["multi_recipe_count_accuracy_avg"] == 1.0
    assert baseline["run"]["passed_threshold"] is True
    assert len(baseline["per_case"]) == results.suite_results["vision_extraction"].total_cases
    assert "hard ≥ 0.800" in _load_script().render_markdown(baseline)
