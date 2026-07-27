"""irrd-3a — unit tests for the two-gate wiring (src/confidence_gates.py).

Deterministic only: every test feeds hand-built fixture-runner results,
so nothing here needs OPENAI_API_KEY, network, or the ~10-minute real
run. What is under test is the plumbing — samples built from run output,
both gates applied, the combined verdict, the report text, and the
baseline round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.confidence_gates import (
    CALIBRATION_BASELINE_PATH,
    EXTRACTION_BASELINE_PATH,
    build_calibration_baseline,
    build_calibration_samples,
    build_extraction_baseline,
    build_title_pairs,
    evaluate_gates,
    format_gate_report,
    load_baseline,
    write_baselines,
)
from src.metrics.confidence_calibration import CALIBRATION_MAE_THRESHOLD
from src.metrics.title_extraction import TITLE_REGRESSION_MAX_RELATIVE_DROP


def _recipe(name="Banana Bread", steps=3, quantities=2, confidence=0.8, source="model"):
    return {
        "name": name,
        "ingredients": [
            {"name": f"ing{i}", "quantity": 1.0 if i < quantities else None, "unit": "cup"}
            for i in range(2)
        ],
        "steps": [{"instruction": f"step {i}"} for i in range(steps)],
        "confidence_score": confidence,
        "confidence_source": source,
    }


def _fixture_result(
    fixture_id="banana_bread",
    f1=0.8,
    confidence=0.8,
    source="model",
    extracted_name="Banana Bread",
    expected_name="Banana Bread",
    error=None,
):
    result = {
        "id": fixture_id,
        "strategy": "text_extractor",
        "input_type": "text",
        "scores": {"overall_f1": f1},
        "error": error,
        "duration_ms": 1.0,
    }
    if error is None:
        result["extracted"] = _recipe(
            name=extracted_name, confidence=confidence, source=source
        )
        result["expected"] = {"name": expected_name}
    return result


# -------------------------------------------------------------------
# Sample building
# -------------------------------------------------------------------


def test_calibration_samples_pair_confidence_with_scored_f1():
    samples = build_calibration_samples([
        _fixture_result("a", f1=0.7, confidence=0.9, source="model"),
        _fixture_result("b", f1=0.5, confidence=0.4, source="heuristic"),
    ])
    assert [s["fixture_id"] for s in samples] == ["a", "b"]
    assert samples[0]["confidence"] == 0.9
    assert samples[0]["ground_truth_f1"] == 0.7
    assert samples[1]["source"] == "heuristic"


def test_calibration_samples_carry_the_production_heuristic_signals():
    # A titled recipe with 3 steps and half its ingredients quantified —
    # the numbers come from confidence_heuristic.structural_signals, not
    # from a copy of the formula living in the eval suite.
    samples = build_calibration_samples([_fixture_result()])
    signals = samples[0]["signals"]
    assert signals["title"] == 1.0
    assert signals["steps"] == 1.0
    assert 0.0 < signals["ingredients"] <= 1.0


def test_calibration_samples_can_skip_signals():
    samples = build_calibration_samples([_fixture_result()], with_signals=False)
    assert "signals" not in samples[0]


def test_errored_fixtures_produce_no_samples():
    results = [
        _fixture_result("ok"),
        _fixture_result("broken", error="Extraction failed: boom"),
    ]
    assert [s["fixture_id"] for s in build_calibration_samples(results)] == ["ok"]
    assert [p["fixture_id"] for p in build_title_pairs(results)] == ["ok"]


def test_result_without_extracted_payload_is_skipped():
    # run_eval only attaches payloads with include_payloads=True; a run
    # collected without them must not be scored as zeroes.
    stripped = _fixture_result()
    stripped.pop("extracted")
    assert build_calibration_samples([stripped]) == []
    assert build_title_pairs([stripped]) == []


def test_title_pairs_pass_through_extracted_and_expected():
    pairs = build_title_pairs([
        _fixture_result("a", extracted_name="Potato Quiche", expected_name="Potato Quiche")
    ])
    assert pairs[0]["extracted"]["name"] == "Potato Quiche"
    assert pairs[0]["expected"]["name"] == "Potato Quiche"


# -------------------------------------------------------------------
# Combined gate evaluation
# -------------------------------------------------------------------


def test_well_calibrated_run_with_exact_titles_passes_both_gates():
    report = evaluate_gates([
        _fixture_result("a", f1=0.8, confidence=0.8),
        _fixture_result("b", f1=0.7, confidence=0.75),
    ])
    assert report["passed"] is True
    assert report["calibration"]["gate"]["passed"] is True
    assert report["title"]["gate"]["passed"] is True
    assert report["title"]["result"]["title_extraction_f1"] == 1.0


def test_miscalibrated_run_fails_even_though_titles_are_perfect():
    report = evaluate_gates([
        _fixture_result("a", f1=0.2, confidence=0.95),
        _fixture_result("b", f1=0.1, confidence=0.99),
    ])
    assert report["passed"] is False
    assert report["calibration"]["gate"]["passed"] is False
    assert report["calibration"]["gate"]["value"] > CALIBRATION_MAE_THRESHOLD
    assert report["title"]["gate"]["passed"] is True


def test_title_regression_fails_the_run_even_though_calibration_is_fine():
    baseline = {"title_extraction": {"title_extraction_f1": 1.0}}
    report = evaluate_gates(
        [
            _fixture_result(
                "a", f1=0.8, confidence=0.8,
                extracted_name="Bread", expected_name="Banana Bread",
            )
        ],
        extraction_baseline=baseline,
    )
    assert report["calibration"]["gate"]["passed"] is True
    assert report["title"]["gate"]["passed"] is False
    assert report["passed"] is False


def test_empty_run_fails_closed():
    report = evaluate_gates([])
    assert report["passed"] is False
    assert report["calibration"]["gate"]["passed"] is False
    assert report["title"]["gate"]["passed"] is False


def test_fully_errored_run_fails_closed_and_names_the_fixtures():
    report = evaluate_gates([
        _fixture_result("a", error="Extraction failed: 429"),
        _fixture_result("b", error="Extraction failed: 429"),
    ])
    assert report["passed"] is False
    assert report["errored_fixtures"] == ["a", "b"]
    assert report["fixture_count"] == 2


def test_calibration_baseline_is_context_not_the_verdict():
    # Gate decides on the 0.3 threshold; the baseline only reports drift.
    report = evaluate_gates(
        [_fixture_result("a", f1=0.8, confidence=0.85)],
        calibration_baseline={"confidence_calibration": {"mae": 0.01}},
    )
    gate = report["calibration"]["gate"]
    assert gate["passed"] is True
    assert abs(gate["delta_vs_baseline"] - (gate["value"] - 0.01)) < 1e-9


def test_aggregate_and_strategy_are_carried_through():
    report = evaluate_gates(
        [_fixture_result()],
        aggregate={"overall_f1_avg": 0.81},
        strategy="vision_extractor",
    )
    assert report["strategy"] == "vision_extractor"
    assert report["aggregate"]["overall_f1_avg"] == 0.81


# -------------------------------------------------------------------
# Report rendering
# -------------------------------------------------------------------


def test_report_renders_both_gate_blocks_and_a_combined_verdict():
    report = evaluate_gates([_fixture_result("a", f1=0.8, confidence=0.8)])
    text = format_gate_report(report)
    assert "CONFIDENCE CALIBRATION GATE: PASSED" in text
    assert "TITLE EXTRACTION REGRESSION GATE: PASSED" in text
    assert "OVERALL: PASSED" in text
    assert "strategy=text_extractor" in text


def test_failed_report_names_the_failing_gate_in_the_overall_line():
    report = evaluate_gates([
        _fixture_result("a", f1=0.1, confidence=0.99),
        _fixture_result("b", f1=0.1, confidence=0.95),
    ])
    text = format_gate_report(report)
    assert "OVERALL: FAILED" in text
    assert "calibration=FAIL" in text
    assert "title=pass" in text


def test_calibration_failure_points_at_the_signal_to_retune():
    results = []
    for i, (f1, signal) in enumerate([(0.1, 0), (0.9, 3), (0.5, 1)]):
        r = _fixture_result(f"f{i}", f1=f1, confidence=0.99)
        r["extracted"]["steps"] = [{"instruction": "s"} for _ in range(signal)]
        results.append(r)
    text = format_gate_report(evaluate_gates(results))
    assert "AC9 next step: shift heuristic weight toward 'steps'" in text
    assert "confidence_heuristic.py" in text


def test_title_failure_points_at_the_prompt_retune():
    report = evaluate_gates(
        [
            _fixture_result(
                "a", f1=0.8, confidence=0.8,
                extracted_name="Bread", expected_name="Banana Bread",
            )
        ],
        extraction_baseline={"title_extraction": {"title_extraction_f1": 1.0}},
    )
    text = format_gate_report(report)
    assert "AC11 next step" in text
    assert "EXTRACTOR_EMIT_CONFIDENCE" in text


def test_report_lists_excluded_extraction_errors():
    report = evaluate_gates([
        _fixture_result("ok", f1=0.8, confidence=0.8),
        _fixture_result("boom", error="Extraction failed: timeout"),
    ])
    text = format_gate_report(report)
    assert "Extraction errors (1): boom" in text
    assert "excluded from both metrics" in text


# -------------------------------------------------------------------
# Baseline loading
# -------------------------------------------------------------------


def test_load_baseline_reads_the_checked_in_files():
    assert load_baseline(CALIBRATION_BASELINE_PATH) is not None
    assert load_baseline(EXTRACTION_BASELINE_PATH) is not None


def test_load_baseline_tolerates_missing_and_malformed_files(tmp_path):
    assert load_baseline(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_baseline(bad) is None
    listy = tmp_path / "list.json"
    listy.write_text("[1, 2]")
    assert load_baseline(listy) is None


def test_baseline_paths_resolve_independently_of_cwd():
    assert CALIBRATION_BASELINE_PATH.is_file()
    assert EXTRACTION_BASELINE_PATH.is_file()
    assert CALIBRATION_BASELINE_PATH.parent.name == "baselines"


# -------------------------------------------------------------------
# Baseline refresh
# -------------------------------------------------------------------


def test_calibration_baseline_merge_keeps_the_explanatory_comments():
    existing = load_baseline(CALIBRATION_BASELINE_PATH)
    report = evaluate_gates([
        _fixture_result("a", f1=0.8, confidence=0.8),
        _fixture_result("b", f1=0.6, confidence=0.7),
    ])
    payload = build_calibration_baseline(
        report, existing=existing, generated_at="2026-07-27T12:00:00-06:00",
        generated_commit="abc123",
    )
    assert payload["_comment"] == existing["_comment"]
    assert payload["_fixture_set"] == "services/eval/fixtures/expected/*.json"
    assert payload["_generated_at"] == "2026-07-27T12:00:00-06:00"
    assert payload["_generated_commit"] == "abc123"
    assert payload["confidence_calibration"]["sample_count"] == 2
    assert payload["confidence_calibration"]["mae"] is not None


def test_calibration_baseline_mirrors_the_live_heuristic_weights():
    from utils.services.recipe_extractors import confidence_heuristic as ch

    payload = build_calibration_baseline(evaluate_gates([_fixture_result()]))
    assert payload["heuristic_weights"]["ingredients"] == ch._W_INGREDIENTS
    assert payload["heuristic_weights"]["title"] == ch._W_TITLE
    assert payload["heuristic_weights"]["steps"] == ch._W_STEPS
    assert (
        payload["thresholds"]["confidence_calibration_mae_max"]
        == CALIBRATION_MAE_THRESHOLD
    )


def test_calibration_baseline_does_not_mutate_the_input():
    existing = load_baseline(CALIBRATION_BASELINE_PATH)
    snapshot = json.dumps(existing, sort_keys=True)
    build_calibration_baseline(evaluate_gates([_fixture_result()]), existing=existing)
    assert json.dumps(existing, sort_keys=True) == snapshot


def test_extraction_baseline_records_title_numbers_and_aggregates():
    existing = load_baseline(EXTRACTION_BASELINE_PATH)
    report = evaluate_gates(
        [_fixture_result("a", f1=0.8, confidence=0.8)],
        aggregate={"overall_f1_avg": 0.81, "total_fixtures": 1.0, "junk": 9.9},
        strategy="text_extractor",
    )
    payload = build_extraction_baseline(report, existing=existing)
    assert payload["title_extraction"]["title_extraction_f1"] == 1.0
    assert payload["title_extraction"]["sample_count"] == 1
    assert payload["extraction_scores"]["overall_f1_avg"] == 0.81
    assert "junk" not in payload["extraction_scores"]
    assert (
        payload["thresholds"]["title_extraction_f1_max_relative_drop"]
        == TITLE_REGRESSION_MAX_RELATIVE_DROP
    )
    assert payload["_comment"] == existing["_comment"]


def test_write_baselines_round_trips_into_a_gateable_baseline(tmp_path):
    cal_path = tmp_path / "confidence_calibration_baseline.json"
    ext_path = tmp_path / "extraction_baseline.json"

    first = evaluate_gates([
        _fixture_result("a", f1=0.8, confidence=0.8, expected_name="Banana Bread"),
        _fixture_result("b", f1=0.7, confidence=0.7, expected_name="Banana Bread"),
    ])
    written = write_baselines(first, calibration_path=cal_path, extraction_path=ext_path)
    assert [p.name for p in written] == [cal_path.name, ext_path.name]

    # A rerun of the same quality compares cleanly against what we wrote.
    second = evaluate_gates(
        [
            _fixture_result("a", f1=0.8, confidence=0.8, expected_name="Banana Bread"),
            _fixture_result("b", f1=0.7, confidence=0.7, expected_name="Banana Bread"),
        ],
        calibration_baseline=load_baseline(cal_path),
        extraction_baseline=load_baseline(ext_path),
    )
    assert second["passed"] is True
    assert second["title"]["gate"]["baseline_missing"] is False
    assert second["title"]["gate"]["baseline"] == 1.0
    assert second["calibration"]["gate"]["delta_vs_baseline"] == 0.0


def test_written_baseline_catches_a_later_title_regression(tmp_path):
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    write_baselines(
        evaluate_gates([_fixture_result("a", f1=0.8, confidence=0.8)]),
        calibration_path=cal_path,
        extraction_path=ext_path,
    )
    regressed = evaluate_gates(
        [
            _fixture_result(
                "a", f1=0.8, confidence=0.8,
                extracted_name="Bread", expected_name="Banana Bread",
            )
        ],
        extraction_baseline=load_baseline(ext_path),
    )
    assert regressed["title"]["gate"]["passed"] is False
    assert regressed["title"]["gate"]["relative_drop"] > TITLE_REGRESSION_MAX_RELATIVE_DROP


def test_write_baselines_creates_files_when_none_exist(tmp_path):
    target = tmp_path / "nested" / "cal.json"
    other = tmp_path / "nested" / "ext.json"
    write_baselines(
        evaluate_gates([_fixture_result()]),
        calibration_path=target,
        extraction_path=other,
    )
    assert json.loads(target.read_text())["confidence_calibration"]["sample_count"] == 1
    assert json.loads(other.read_text())["title_extraction"]["sample_count"] == 1


def test_written_baselines_stay_json_parsable_with_trailing_newline(tmp_path):
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    write_baselines(
        evaluate_gates([_fixture_result()]),
        calibration_path=cal_path,
        extraction_path=ext_path,
    )
    for path in (cal_path, ext_path):
        raw = path.read_text()
        assert raw.endswith("\n")
        json.loads(raw)


# -------------------------------------------------------------------
# Wiring against the real repo layout
# -------------------------------------------------------------------


def test_run_confidence_gates_wires_a_whole_fixture_run(tmp_path, monkeypatch):
    # The only seam that normally costs an API key: run_eval must be
    # asked for payloads, and its output must reach both metrics. The
    # extractor itself is stubbed, so this stays network-free.
    from src.confidence_gates import run_confidence_gates

    fixtures = tmp_path / "fixtures"
    (fixtures / "text").mkdir(parents=True)
    (fixtures / "expected").mkdir()
    (fixtures / "text" / "sample.txt").write_text("Banana Bread\n1 cup flour\nmix")
    (fixtures / "expected" / "sample.json").write_text(
        json.dumps({
            "name": "Banana Bread",
            "ingredients": [{"name": "flour", "quantity": 1, "unit": "cup"}],
            "steps": [{"instruction": "mix"}],
        })
    )

    extracted = {
        "name": "Banana Bread",
        "ingredients": [{"name": "flour", "quantity": 1, "unit": "cup"}],
        "steps": [{"instruction": "mix"}],
        "confidence_score": 0.8,
        "confidence_source": "model",
    }
    monkeypatch.setattr(
        "src.fixture_runner.get_strategy_function",
        lambda _strategy: (lambda _input: extracted),
    )

    report = run_confidence_gates(
        fixtures,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
    )

    assert report["fixture_count"] == 1
    assert report["errored_fixtures"] == []
    assert report["calibration"]["result"]["sample_count"] == 1
    assert report["title"]["result"]["title_extraction_f1"] == 1.0
    assert report["aggregate"]["total_fixtures"] == 1.0
    # No baseline on disk: the title gate has nothing to regress against.
    assert report["title"]["gate"]["baseline_missing"] is True
    assert report["passed"] is True


def test_gate_command_is_registered_and_opt_in():
    # AC: the expensive run is invoked explicitly, never from the fast
    # CI path — so it must exist as its own command, and `test` must not
    # depend on it.
    from src.main import cli

    assert "confidence-gate" in cli.commands
    project = json.loads(
        (Path(__file__).resolve().parents[1] / "project.json").read_text()
    )
    targets = project["targets"]
    assert "confidence-gate" in targets
    assert "confidence-gate" not in targets["test"]["options"]["command"]
    assert "confidence-gate" not in targets["lint"]["options"]["command"]
