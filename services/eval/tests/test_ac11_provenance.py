"""irrd-3a — the AC11 gate must know whether it compared a real before/after.

AC11 asks whether turning the confidence-emitting prompts on cost title
quality. Answering it needs the baseline captured with
``EXTRACTOR_EMIT_CONFIDENCE=false`` and the compared run with it ``true``.
Any other pairing still yields a numeric verdict — and that verdict passes
easily, because it compares like with like. These tests pin the
provenance that keeps such a pass from reading as "the prompts are fine".

Deterministic: hand-built reports and tmp_path baselines only. No key,
no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Sibling module: pytest puts the tests/ directory on sys.path.
from test_confidence_gates import _fixture_result

from src.confidence_gates import (
    CALIBRATION_BASELINE_PATH,
    EXTRACTION_BASELINE_PATH,
    baseline_emit_confidence,
    build_calibration_baseline,
    build_extraction_baseline,
    classify_ac11_comparison,
    evaluate_gates,
    format_gate_report,
    load_baseline,
    write_baselines,
)

# -------------------------------------------------------------------
# Reading the flag state off a baseline
# -------------------------------------------------------------------


def test_baseline_emit_confidence_reads_the_recorded_state():
    assert baseline_emit_confidence({"_emit_confidence": False}) is False
    assert baseline_emit_confidence({"_emit_confidence": True}) is True


def test_baseline_emit_confidence_is_none_when_absent_or_not_a_bool():
    # The prose _extractor_flag string is deliberately NOT parsed: it is a
    # hint for humans and can disagree with reality.
    assert baseline_emit_confidence({}) is None
    assert baseline_emit_confidence({"_emit_confidence": None}) is None
    assert baseline_emit_confidence({"_extractor_flag": "EXTRACTOR_EMIT_CONFIDENCE=false"}) is None
    assert baseline_emit_confidence({"_emit_confidence": "false"}) is None
    assert baseline_emit_confidence(None) is None
    assert baseline_emit_confidence("not a dict") is None


# -------------------------------------------------------------------
# Classification
# -------------------------------------------------------------------


def test_off_baseline_versus_on_run_is_the_real_ac11_comparison():
    verdict = classify_ac11_comparison({"_emit_confidence": False}, True)
    assert verdict["kind"] == "before_after"
    assert verdict["is_before_after"] is True
    assert verdict["baseline_emit_confidence"] is False
    assert verdict["run_emit_confidence"] is True
    assert "valid AC11 before/after" in verdict["note"]


def test_both_on_is_a_drift_check_not_a_before_after():
    # The hazard this whole module exists for: the operator forgets
    # EXTRACTOR_EMIT_CONFIDENCE=false on the baseline run, and every later
    # comparison is confidence-on vs confidence-on.
    verdict = classify_ac11_comparison({"_emit_confidence": True}, True)
    assert verdict["kind"] == "same_state"
    assert verdict["is_before_after"] is False
    assert "drift check" in verdict["note"]
    assert "does not prove" in verdict["note"]


def test_both_off_says_the_prompts_were_never_exercised():
    verdict = classify_ac11_comparison({"_emit_confidence": False}, False)
    assert verdict["kind"] == "same_state"
    assert verdict["is_before_after"] is False
    assert "never exercised" in verdict["note"]


def test_on_baseline_versus_off_run_is_flagged_as_inverted():
    verdict = classify_ac11_comparison({"_emit_confidence": True}, False)
    assert verdict["kind"] == "reversed"
    assert verdict["is_before_after"] is False
    assert "inverted" in verdict["note"]


def test_unknown_state_on_either_side_refuses_to_claim_a_before_after():
    for baseline, run in (
        ({}, True),
        ({"_emit_confidence": False}, None),
        ({}, None),
    ):
        verdict = classify_ac11_comparison(baseline, run)
        assert verdict["kind"] == "unknown", (baseline, run)
        assert verdict["is_before_after"] is False
        assert "does not prove" in verdict["note"]


def test_missing_baseline_reports_that_nothing_was_compared():
    verdict = classify_ac11_comparison(
        {"_emit_confidence": False}, True, baseline_missing=True
    )
    assert verdict["kind"] == "no_baseline"
    assert verdict["is_before_after"] is False
    assert "nothing was compared" in verdict["note"]
    # It still names the state this run establishes, so the operator can
    # see whether the baseline they just captured is the right "before".
    assert "EXTRACTOR_EMIT_CONFIDENCE=true" in verdict["note"]


# -------------------------------------------------------------------
# Wiring into the gate report
# -------------------------------------------------------------------


def _passing_report(baseline, emit_confidence):
    return evaluate_gates(
        [_fixture_result("a", f1=0.8, confidence=0.8)],
        extraction_baseline=baseline,
        with_signals=False,
        emit_confidence=emit_confidence,
    )


def test_report_carries_the_run_flag_state_and_the_classification():
    report = _passing_report({"title_extraction": {"title_extraction_f1": 0.9}}, True)
    assert report["emit_confidence"] is True
    assert report["ac11_comparison"]["kind"] == "unknown"


def test_a_numerically_passing_gate_can_still_be_a_vacuous_comparison():
    # Same numbers, same PASS — but the provenance says the confidence
    # prompts were on for both sides, so the pass proves nothing about
    # them. Both facts have to be visible at once.
    baseline = {
        "_emit_confidence": True,
        "title_extraction": {"title_extraction_f1": 0.9},
    }
    report = _passing_report(baseline, True)
    assert report["title"]["gate"]["passed"] is True
    assert report["passed"] is True
    assert report["ac11_comparison"]["is_before_after"] is False
    assert report["ac11_comparison"]["kind"] == "same_state"


def test_the_genuine_before_after_is_marked_as_such():
    baseline = {
        "_emit_confidence": False,
        "title_extraction": {"title_extraction_f1": 0.9},
    }
    report = _passing_report(baseline, True)
    assert report["ac11_comparison"]["is_before_after"] is True


def test_no_baseline_wins_over_the_flag_states():
    # An all-null placeholder baseline still carries _emit_confidence:
    # null, but the gate compared nothing, so that is what gets reported.
    report = _passing_report({"_emit_confidence": False, "title_extraction": {}}, True)
    assert report["title"]["gate"]["baseline_missing"] is True
    assert report["ac11_comparison"]["kind"] == "no_baseline"


def test_default_call_reports_an_unknown_run_state():
    # evaluate_gates is called directly by tests and by replay; leaving
    # the state out must not fabricate a before/after.
    report = evaluate_gates([_fixture_result("a")], with_signals=False)
    assert report["emit_confidence"] is None
    assert report["ac11_comparison"]["is_before_after"] is False


# -------------------------------------------------------------------
# Rendering
# -------------------------------------------------------------------


def test_vacuous_comparison_is_rendered_as_a_warning():
    baseline = {
        "_emit_confidence": True,
        "title_extraction": {"title_extraction_f1": 0.9},
    }
    text = format_gate_report(_passing_report(baseline, True))
    assert "OVERALL: PASSED" in text
    assert "WARNING: baseline and run were both captured" in text
    assert "drift check" in text


def test_real_before_after_is_rendered_without_a_warning():
    baseline = {
        "_emit_confidence": False,
        "title_extraction": {"title_extraction_f1": 0.9},
    }
    text = format_gate_report(_passing_report(baseline, True))
    assert "AC11 comparison: valid AC11 before/after" in text
    assert "WARNING" not in text


def test_reports_without_a_classification_render_unchanged():
    # format_gate_report is also handed hand-built dicts (and older saved
    # reports) that predate the field.
    report = _passing_report({"title_extraction": {"title_extraction_f1": 0.9}}, True)
    report.pop("ac11_comparison")
    text = format_gate_report(report)
    assert "WARNING" not in text
    assert "OVERALL:" in text


# -------------------------------------------------------------------
# Stamping it into the baselines
# -------------------------------------------------------------------


def test_written_baselines_record_the_flag_state_they_were_captured_under():
    report = _passing_report(None, False)
    for builder in (build_extraction_baseline, build_calibration_baseline):
        payload = builder(report, existing={})
        assert payload["_emit_confidence"] is False
        assert payload["_extractor_flag"] == "EXTRACTOR_EMIT_CONFIDENCE=false"


def test_an_unknown_run_state_never_overwrites_a_recorded_one():
    report = evaluate_gates([_fixture_result("a")], with_signals=False)
    existing = {
        "_emit_confidence": False,
        "_extractor_flag": "EXTRACTOR_EMIT_CONFIDENCE=false",
    }
    payload = build_extraction_baseline(report, existing=existing)
    assert payload["_emit_confidence"] is False
    assert payload["_extractor_flag"] == "EXTRACTOR_EMIT_CONFIDENCE=false"


def test_baseline_write_then_compare_reports_a_genuine_before_after(tmp_path):
    # The full operator loop: step 1 writes the baseline from a
    # confidence-OFF run, step 2 compares a confidence-ON run against it.
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"

    before = _passing_report(None, False)
    write_baselines(before, calibration_path=cal_path, extraction_path=ext_path)
    assert json.loads(ext_path.read_text())["_emit_confidence"] is False

    after = evaluate_gates(
        [_fixture_result("a", f1=0.8, confidence=0.8)],
        extraction_baseline=load_baseline(ext_path),
        with_signals=False,
        emit_confidence=True,
    )
    assert after["ac11_comparison"]["kind"] == "before_after"
    assert after["ac11_comparison"]["is_before_after"] is True
    assert "valid AC11 before/after" in format_gate_report(after)


def test_forgetting_the_flag_in_step_one_is_caught_at_step_two(tmp_path):
    # Same loop with the env var forgotten: the numbers still pass, and
    # the report says why that pass is not AC11.
    ext_path = tmp_path / "ext.json"
    write_baselines(
        _passing_report(None, True),
        calibration_path=tmp_path / "cal.json",
        extraction_path=ext_path,
    )
    after = evaluate_gates(
        [_fixture_result("a", f1=0.8, confidence=0.8)],
        extraction_baseline=load_baseline(ext_path),
        with_signals=False,
        emit_confidence=True,
    )
    assert after["title"]["gate"]["passed"] is True
    assert after["ac11_comparison"]["kind"] == "same_state"
    assert "WARNING" in format_gate_report(after)


# -------------------------------------------------------------------
# Replay reads the recorded state, not the current shell
# -------------------------------------------------------------------


def test_replay_classifies_against_the_state_the_run_was_recorded_under(tmp_path):
    from src.confidence_gates import replay_gates
    from src.run_artifact import build_run_artifact

    ext_path = tmp_path / "ext.json"
    write_baselines(
        _passing_report(None, False),
        calibration_path=tmp_path / "cal.json",
        extraction_path=ext_path,
    )

    summary = {
        "strategy": "text_extractor",
        "aggregate": {},
        "fixtures": [_fixture_result("a", f1=0.8, confidence=0.8, source="heuristic")],
    }
    artifact = build_run_artifact(summary, emit_confidence=True)

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "cal.json",
        extraction_baseline_path=ext_path,
    )
    # The replaying shell has no EXTRACTOR_EMIT_CONFIDENCE set at all; the
    # classification must come from the artifact.
    assert report["emit_confidence"] is True
    assert report["ac11_comparison"]["kind"] == "before_after"


def test_replay_of_an_artifact_without_a_recorded_state_stays_unknown(tmp_path):
    from src.confidence_gates import replay_gates
    from src.run_artifact import build_run_artifact

    ext_path = tmp_path / "ext.json"
    write_baselines(
        _passing_report(None, False),
        calibration_path=tmp_path / "cal.json",
        extraction_path=ext_path,
    )
    summary = {
        "strategy": "text_extractor",
        "aggregate": {},
        "fixtures": [_fixture_result("a", f1=0.8, confidence=0.8, source="heuristic")],
    }
    artifact = build_run_artifact(summary)

    report = replay_gates(
        artifact,
        calibration_baseline_path=tmp_path / "cal.json",
        extraction_baseline_path=ext_path,
    )
    assert report["emit_confidence"] is None
    assert report["ac11_comparison"]["kind"] == "unknown"


# -------------------------------------------------------------------
# The CLI warns at the moment the mistake is made
# -------------------------------------------------------------------


def _write_baseline_output(tmp_path, monkeypatch, emit_confidence):
    """Run `confidence-gate --from-run ... --write-baseline` and capture stdout.

    The real ``write_baselines`` defaults to the checked-in files, so it
    is stubbed — this test is about the warning, not the write.
    """
    from click.testing import CliRunner

    import src.confidence_gates as gates
    from src.main import cli
    from src.run_artifact import save_run_artifact

    monkeypatch.setattr(gates, "write_baselines", lambda *a, **k: [])
    run_path = tmp_path / "run.json"
    save_run_artifact(
        {
            "strategy": "text_extractor",
            "aggregate": {},
            "fixtures": [_fixture_result("a", f1=0.8, confidence=0.8, source="heuristic")],
        },
        run_path,
        emit_confidence=emit_confidence,
    )
    result = CliRunner().invoke(
        cli, ["confidence-gate", "--from-run", str(run_path), "--write-baseline"]
    )
    # rich wraps at the console width and colours literals like `true`;
    # compare on de-styled, whitespace-collapsed text.
    return " ".join(re.sub(r"\x1b\[[0-9;]*m", "", result.output).split())


def test_cli_warns_when_a_baseline_is_written_from_a_confidence_on_run(
    tmp_path, monkeypatch
):
    output = _write_baseline_output(tmp_path, monkeypatch, emit_confidence=True)
    assert "EXTRACTOR_EMIT_CONFIDENCE=true" in output
    assert "re-run with the flag false" in output


def test_cli_stays_quiet_when_the_baseline_run_had_the_flag_off(tmp_path, monkeypatch):
    output = _write_baseline_output(tmp_path, monkeypatch, emit_confidence=False)
    assert "re-run with the flag false" not in output
    assert "Review the diff and commit the baselines" in output


# -------------------------------------------------------------------
# Checked-in files
# -------------------------------------------------------------------


def test_checked_in_baselines_declare_the_provenance_field():
    for path in (EXTRACTION_BASELINE_PATH, CALIBRATION_BASELINE_PATH):
        payload = load_baseline(path)
        assert "_emit_confidence" in payload, path
        # Placeholder until the first real run — no run has stamped it.
        assert payload["_emit_confidence"] is None, path
        assert payload["_emit_confidence_comment"], path


def test_the_flag_is_default_on_which_is_why_this_guard_exists():
    # EXTRACTOR_EMIT_CONFIDENCE defaults to true, so an operator who runs
    # --write-baseline without the prefix captures a confidence-ON
    # baseline by default — the vacuous comparison is the easy mistake,
    # not the exotic one.
    from src.confidence_gates import _emit_confidence_state

    for raw, expected in (("false", False), ("true", True), (None, True)):
        env = {} if raw is None else {"EXTRACTOR_EMIT_CONFIDENCE": raw}
        with _patched_env(env):
            assert _emit_confidence_state() is expected, raw


def _patched_env(env):
    import contextlib
    import os

    @contextlib.contextmanager
    def _ctx():
        previous = os.environ.get("EXTRACTOR_EMIT_CONFIDENCE")
        os.environ.pop("EXTRACTOR_EMIT_CONFIDENCE", None)
        os.environ.update(env)
        try:
            yield
        finally:
            os.environ.pop("EXTRACTOR_EMIT_CONFIDENCE", None)
            if previous is not None:
                os.environ["EXTRACTOR_EMIT_CONFIDENCE"] = previous

    return _ctx()


def test_operator_docs_explain_why_step_one_needs_the_flag_off():
    # An operator who only reads the handoff must learn that forgetting
    # the env var makes step 2 vacuous — the code can only warn after the
    # ten minutes are already spent.
    repo_root = Path(__file__).resolve().parents[3]
    for doc in (repo_root / "MANUAL.md", repo_root / "services/eval/README.md"):
        text = doc.read_text()
        assert "EXTRACTOR_EMIT_CONFIDENCE=false" in text, doc
        assert "before/after" in text, doc


def test_checked_in_baseline_paths_are_the_documented_ones():
    root = Path(__file__).resolve().parents[1]
    assert EXTRACTION_BASELINE_PATH == root / "baselines" / "extraction_baseline.json"
    assert (
        CALIBRATION_BASELINE_PATH
        == root / "baselines" / "confidence_calibration_baseline.json"
    )
