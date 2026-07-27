"""irrd-3a — unit tests for saving and replaying an expensive fixture run.

Deterministic only: every test builds its own run payloads, so nothing
here needs OPENAI_API_KEY, network, or the ~10-minute real run. What is
under test is the claim the replay rests on — that a heuristic-sourced
confidence can be recomputed offline from a saved extraction and land
exactly where a fresh run would have put it.
"""

from __future__ import annotations

import json

import pytest
from utils.services.recipe_extractors import confidence_heuristic as heuristic

from src.confidence_gates import format_gate_report, replay_gates
from src.run_artifact import (
    RUN_ARTIFACT_SCHEMA_VERSION,
    build_run_artifact,
    load_run_artifact,
    moved_changes,
    recompute_heuristic_confidences,
    save_run_artifact,
)


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


def _fixture_result(fixture_id="banana_bread", extracted=None, f1=0.9, error=None):
    result = {
        "id": fixture_id,
        "strategy": "text_extractor",
        "input_type": "text",
        "scores": {"overall_f1": f1},
        "error": error,
        "duration_ms": 12.0,
    }
    if error is None:
        result["extracted"] = extracted if extracted is not None else _recipe()
        result["expected"] = {"name": "Banana Bread"}
    return result


def _summary(results):
    return {
        "strategy": "text_extractor",
        "fixtures": results,
        "aggregate": {"total_fixtures": float(len(results)), "overall_f1_avg": 0.9},
    }


# -------------------------------------------------------------------
# Envelope + round trip
# -------------------------------------------------------------------


def test_artifact_carries_version_strategy_fixtures_and_flag_state():
    artifact = build_run_artifact(
        _summary([_fixture_result()]),
        generated_at="2026-07-27T23:00:00-06:00",
        generated_commit="abc123",
        emit_confidence=True,
    )

    assert artifact["_schema_version"] == RUN_ARTIFACT_SCHEMA_VERSION
    assert artifact["strategy"] == "text_extractor"
    assert len(artifact["fixtures"]) == 1
    assert artifact["aggregate"]["total_fixtures"] == 1.0
    assert artifact["_generated_at"] == "2026-07-27T23:00:00-06:00"
    assert artifact["_generated_commit"] == "abc123"
    # Without the flag state a replayed report can't say whether the
    # model was ever asked for a score.
    assert artifact["emit_confidence"] is True
    assert "--from-run" in artifact["_comment"]


def test_artifact_survives_an_empty_summary():
    artifact = build_run_artifact({})

    assert artifact["fixtures"] == []
    assert artifact["aggregate"] == {}
    assert artifact["strategy"] is None


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "nested" / "run.json"
    written = save_run_artifact(
        _summary([_fixture_result(), _fixture_result("pasta", f1=0.5)]),
        path,
        emit_confidence=False,
    )

    assert written == path
    loaded = load_run_artifact(path)
    assert [f["id"] for f in loaded["fixtures"]] == ["banana_bread", "pasta"]
    assert loaded["emit_confidence"] is False


def test_save_degrades_unserializable_values_instead_of_losing_the_run(tmp_path):
    # The run cost ten minutes and an API key; a stray non-JSON value in
    # one payload must not take the whole thing down.
    class Weird:
        def __repr__(self):
            return "<weird>"

    result = _fixture_result()
    result["extracted"]["oddball"] = Weird()
    path = save_run_artifact(_summary([result]), tmp_path / "run.json")

    loaded = load_run_artifact(path)
    assert loaded["fixtures"][0]["extracted"]["oddball"] == "<weird>"


# -------------------------------------------------------------------
# Load refuses ambiguity
# -------------------------------------------------------------------


def test_load_rejects_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_run_artifact(tmp_path / "nope.json")


def test_load_rejects_unreadable_json(tmp_path):
    path = tmp_path / "run.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="readable JSON"):
        load_run_artifact(path)


def test_load_rejects_a_non_object(tmp_path):
    path = tmp_path / "run.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="JSON object"):
        load_run_artifact(path)


def test_load_rejects_an_unknown_schema_version(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"_schema_version": 99, "fixtures": []}))
    with pytest.raises(ValueError, match="schema version"):
        load_run_artifact(path)


def test_load_rejects_a_payload_with_no_fixtures_list(tmp_path):
    # An empty replay would look exactly like a legitimately failing run,
    # so this has to be loud.
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"_schema_version": RUN_ARTIFACT_SCHEMA_VERSION}))
    with pytest.raises(ValueError, match="fixtures"):
        load_run_artifact(path)


def test_load_accepts_a_run_with_zero_fixtures(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(
        json.dumps({"_schema_version": RUN_ARTIFACT_SCHEMA_VERSION, "fixtures": []})
    )
    assert load_run_artifact(path)["fixtures"] == []


# -------------------------------------------------------------------
# Recompute under current weights
# -------------------------------------------------------------------


def test_recompute_matches_the_production_heuristic_exactly():
    # The whole replay rests on this: same extraction + same weights ->
    # the score a fresh run would have recorded.
    extracted = _recipe(confidence=0.11, source="heuristic")
    results, changes = recompute_heuristic_confidences([_fixture_result(extracted=extracted)])

    expected = heuristic.compute_heuristic_confidence(extracted)
    assert results[0]["extracted"]["confidence_score"] == pytest.approx(expected)
    assert changes == [
        {"fixture_id": "banana_bread", "recorded": 0.11, "recomputed": pytest.approx(expected)}
    ]


def test_recompute_follows_a_weight_edit(monkeypatch):
    extracted = _recipe(steps=3, quantities=1, source="heuristic")
    before = heuristic.compute_heuristic_confidence(extracted)

    monkeypatch.setattr(heuristic, "_W_INGREDIENTS", 1.0)
    monkeypatch.setattr(heuristic, "_W_TITLE", 0.0)
    monkeypatch.setattr(heuristic, "_W_STEPS", 0.0)

    results, _ = recompute_heuristic_confidences([_fixture_result(extracted=extracted)])
    after = results[0]["extracted"]["confidence_score"]

    assert after != pytest.approx(before)
    assert after == pytest.approx(0.5)  # 1 of 2 ingredients has a quantity


def test_recompute_leaves_model_sourced_scores_alone():
    # Nothing offline knows what the model would have said, and these are
    # precisely the samples a weight retune cannot move.
    results, changes = recompute_heuristic_confidences(
        [_fixture_result(extracted=_recipe(confidence=0.42, source="model"))]
    )

    assert results[0]["extracted"]["confidence_score"] == 0.42
    assert changes == []


def test_recompute_skips_errored_and_payload_free_fixtures():
    payload_free = {"id": "no_payload", "scores": {"overall_f1": 0.4}, "error": None}
    results, changes = recompute_heuristic_confidences(
        [_fixture_result("boom", error="Extraction failed: no key"), payload_free, "junk"]
    )

    assert [r["id"] for r in results] == ["boom", "no_payload"]
    assert changes == []


def test_recompute_does_not_mutate_the_saved_run():
    original = _fixture_result(extracted=_recipe(confidence=0.11, source="heuristic"))
    recompute_heuristic_confidences([original])

    assert original["extracted"]["confidence_score"] == 0.11


def test_moved_changes_separates_reached_samples_from_unchanged_ones():
    changes = [
        {"fixture_id": "same", "recorded": 0.5, "recomputed": 0.5},
        {"fixture_id": "moved", "recorded": 0.5, "recomputed": 0.7},
        {"fixture_id": "was_null", "recorded": None, "recomputed": 0.7},
        {"fixture_id": "was_bool", "recorded": True, "recomputed": 1.0},
    ]

    assert [c["fixture_id"] for c in moved_changes(changes)] == [
        "moved",
        "was_null",
        "was_bool",
    ]


def test_moved_changes_ignores_float_noise():
    changes = [{"fixture_id": "a", "recorded": 0.7, "recomputed": 0.7 + 1e-12}]
    assert moved_changes(changes) == []


# -------------------------------------------------------------------
# replay_gates
# -------------------------------------------------------------------


def _artifact(results, **kwargs):
    return build_run_artifact(_summary(results), **kwargs)


def test_replay_applies_both_gates_and_records_its_provenance(tmp_path):
    artifact = _artifact(
        [_fixture_result(extracted=_recipe(confidence=0.9, source="heuristic"), f1=0.9)],
        generated_at="2026-07-27T23:00:00-06:00",
        generated_commit="abc123",
        emit_confidence=False,
    )

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
        source_path="/tmp/run.json",
    )

    assert report["fixture_count"] == 1
    assert report["calibration"]["result"]["sample_count"] == 1
    assert report["title"]["result"]["title_extraction_f1"] == 1.0
    replay = report["replay"]
    assert replay["source_path"] == "/tmp/run.json"
    assert replay["recorded_at"] == "2026-07-27T23:00:00-06:00"
    assert replay["recorded_commit"] == "abc123"
    assert replay["emit_confidence"] is False
    assert replay["recompute_heuristic"] is True
    assert [c["fixture_id"] for c in replay["recomputed_fixtures"]] == ["banana_bread"]


def test_replay_as_recorded_reproduces_the_original_verdict(tmp_path):
    # A wildly miscalibrated recorded score: 0.05 confidence against a
    # 0.9 F1. Kept as-is, the calibration gate must fail exactly as it
    # did on the day of the run.
    artifact = _artifact(
        [_fixture_result(extracted=_recipe(confidence=0.05, source="heuristic"), f1=0.9)]
    )

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
        recompute_heuristic=False,
    )

    assert report["calibration"]["result"]["mae"] == pytest.approx(0.85)
    assert report["calibration"]["gate"]["passed"] is False
    assert report["replay"]["recompute_heuristic"] is False
    assert report["replay"]["recomputed_fixtures"] == []


def test_replay_recomputes_away_a_stale_recorded_score(tmp_path):
    # Same run as above, but replayed under the live weights: the score
    # is regenerated from the extraction, so the MAE reflects today's
    # heuristic rather than the one that produced 0.05.
    extracted = _recipe(confidence=0.05, source="heuristic")
    artifact = _artifact([_fixture_result(extracted=extracted, f1=0.9)])

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
    )

    live = heuristic.compute_heuristic_confidence(extracted)
    assert report["calibration"]["result"]["mae"] == pytest.approx(abs(live - 0.9))
    assert [c["fixture_id"] for c in report["replay"]["moved_fixtures"]] == ["banana_bread"]


def test_replay_of_an_empty_run_still_fails_closed(tmp_path):
    report = replay_gates(
        _artifact([]),
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
    )

    assert report["calibration"]["result"]["sample_count"] == 0
    assert report["passed"] is False


def test_replay_keeps_the_strategy_the_run_was_recorded_under(tmp_path):
    artifact = _artifact([_fixture_result()])
    artifact["strategy"] = "vision_extractor"

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
    )
    assert report["strategy"] == "vision_extractor"


def test_replay_report_announces_itself_as_a_replay(tmp_path):
    artifact = _artifact(
        [_fixture_result(extracted=_recipe(confidence=0.05, source="heuristic"), f1=0.9)],
        generated_at="2026-07-27T23:00:00-06:00",
    )

    text = format_gate_report(
        replay_gates(
            artifact,
            calibration_baseline_path=tmp_path / "missing_cal.json",
            extraction_baseline_path=tmp_path / "missing_ext.json",
            source_path="/tmp/run.json",
        )
    )

    assert "REPLAY: saved run /tmp/run.json" in text
    assert "recorded 2026-07-27T23:00:00-06:00" in text
    assert "1 heuristic confidence(s) recomputed" in text
    assert "1 changed" in text


def test_as_recorded_report_says_so(tmp_path):
    text = format_gate_report(
        replay_gates(
            _artifact([_fixture_result()]),
            calibration_baseline_path=tmp_path / "missing_cal.json",
            extraction_baseline_path=tmp_path / "missing_ext.json",
            recompute_heuristic=False,
            source_path="/tmp/run.json",
        )
    )

    assert "--as-recorded" in text


def test_live_report_has_no_replay_line(tmp_path):
    from src.confidence_gates import evaluate_gates

    text = format_gate_report(evaluate_gates([_fixture_result()]))
    assert "REPLAY" not in text


# -------------------------------------------------------------------
# Save during a live run, then replay it
# -------------------------------------------------------------------


def test_live_run_saves_an_artifact_that_replays_to_the_same_verdict(
    tmp_path, monkeypatch
):
    # The operator-facing promise: pay for the run once, then re-read it
    # (or retune against it) for free.
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

    run_path = tmp_path / "run.json"
    live = run_confidence_gates(
        fixtures,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
        save_run_path=run_path,
        generated_at="2026-07-27T23:00:00-06:00",
        generated_commit="abc123",
    )

    assert live["saved_run_path"] == str(run_path)
    # The verdict stays a verdict — the payloads live in the run file.
    assert "_summary" not in live and "fixtures" not in live

    replayed = replay_gates(
        load_run_artifact(run_path),
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
        source_path=run_path,
    )

    assert replayed["fixture_count"] == live["fixture_count"]
    assert replayed["calibration"]["result"]["mae"] == pytest.approx(
        live["calibration"]["result"]["mae"]
    )
    assert replayed["title"]["result"]["title_extraction_f1"] == pytest.approx(
        live["title"]["result"]["title_extraction_f1"]
    )
    assert replayed["passed"] == live["passed"]


def test_a_live_run_without_save_run_writes_nothing(tmp_path, monkeypatch):
    from src.confidence_gates import run_confidence_gates

    fixtures = tmp_path / "fixtures"
    (fixtures / "text").mkdir(parents=True)
    (fixtures / "expected").mkdir()
    (fixtures / "text" / "sample.txt").write_text("Banana Bread")
    (fixtures / "expected" / "sample.json").write_text(json.dumps({"name": "Banana Bread"}))
    monkeypatch.setattr(
        "src.fixture_runner.get_strategy_function",
        lambda _strategy: (lambda _input: {"name": "Banana Bread", "steps": []}),
    )

    report = run_confidence_gates(
        fixtures,
        calibration_baseline_path=tmp_path / "missing_cal.json",
        extraction_baseline_path=tmp_path / "missing_ext.json",
    )

    assert "saved_run_path" not in report
    assert list(tmp_path.glob("*.json")) == []


# -------------------------------------------------------------------
# CLI wiring
# -------------------------------------------------------------------


def _invoke(args):
    from click.testing import CliRunner

    from src.main import cli

    return CliRunner().invoke(cli, args)


def test_cli_accepts_the_replay_flags():
    result = _invoke(["confidence-gate", "--help"])
    assert result.exit_code == 0
    for flag in ("--save-run", "--from-run", "--as-recorded"):
        assert flag in result.output


def test_cli_rejects_saving_a_run_it_is_only_replaying(tmp_path):
    result = _invoke([
        "confidence-gate", "--from-run", str(tmp_path / "run.json"),
        "--save-run", str(tmp_path / "other.json"),
    ])
    assert result.exit_code == 1
    assert "Pick one" in result.output


def test_cli_rejects_as_recorded_without_a_saved_run():
    result = _invoke(["confidence-gate", "--as-recorded"])
    assert result.exit_code == 1
    assert "--as-recorded only applies" in result.output


def test_cli_reports_an_unreadable_saved_run_without_calling_the_extractors(tmp_path):
    # No API key in the loop's environment: reaching extraction here
    # would surface as a different error than the one asserted.
    result = _invoke(["confidence-gate", "--from-run", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "Saved run not found" in result.output


def test_operator_docs_describe_the_replay_loop():
    # The whole point of the artifact is the handoff: an operator who
    # only reads MANUAL.md must still learn that a retune is free.
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    for doc in (repo_root / "MANUAL.md", repo_root / "services/eval/README.md"):
        text = doc.read_text()
        assert "--save-run" in text, doc
        assert "--from-run" in text, doc


def test_cli_replays_a_saved_run_end_to_end(tmp_path):
    path = save_run_artifact(
        _summary([_fixture_result(extracted=_recipe(confidence=0.05, source="heuristic"))]),
        tmp_path / "run.json",
        generated_at="2026-07-27T23:00:00-06:00",
    )

    result = _invoke(["confidence-gate", "--from-run", str(path), "-o", str(tmp_path / "r.json")])

    assert "REPLAY: saved run" in result.output
    assert "OVERALL:" in result.output
    saved = json.loads((tmp_path / "r.json").read_text())
    assert saved["replay"]["recompute_heuristic"] is True
    # Exit code mirrors the gate verdict, replay or not.
    assert result.exit_code == (0 if saved["passed"] else 1)
