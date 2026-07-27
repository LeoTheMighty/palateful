"""irrd-3a — a run that measured nothing must not become a baseline.

The failure this guards against was found by actually running step 1 of
the MANUAL.md operator handoff without a key: every fixture errored, both
gates FAILED, and ``--write-baseline`` still rewrote both files — nulls
for every number, but a real timestamp, a real commit, and a real
``_emit_confidence: false``. The file then *reads* as a captured "before"
baseline (that is exactly what the provenance fields are for) while
holding nothing, so an operator who sees "Baseline written" and a
plausible diff commits step 1 as done. Only the next run says otherwise —
and by then the misleading file is in the history.

Deterministic only — hand-built runs, no key, no network.
"""

from __future__ import annotations

import json
import re

from src.confidence_gates import (
    baseline_write_blockers,
    build_extraction_baseline,
    evaluate_gates,
    load_baseline,
    write_baselines,
)


def _recipe(name="Banana Bread", confidence=0.8, source="heuristic"):
    return {
        "name": name,
        "ingredients": [{"name": "flour", "quantity": 1.0, "unit": "cup"}],
        "steps": [{"instruction": "mix"}, {"instruction": "bake"}],
        "confidence_score": confidence,
        "confidence_source": source,
    }


def _ok(fixture_id="a", f1=0.8, confidence=0.8, name="Banana Bread"):
    return {
        "id": fixture_id,
        "strategy": "text_extractor",
        "scores": {"overall_f1": f1},
        "error": None,
        "extracted": _recipe(name=name, confidence=confidence),
        "expected": {"name": name},
    }


def _errored(fixture_id="a", message="APIError: no key"):
    return {
        "id": fixture_id,
        "strategy": "text_extractor",
        "scores": {},
        "error": message,
    }


# -------------------------------------------------------------------
# baseline_write_blockers
# -------------------------------------------------------------------


def test_a_healthy_run_has_no_blockers():
    assert baseline_write_blockers(evaluate_gates([_ok("a"), _ok("b")])) == []


def test_an_all_errored_run_is_blocked_and_names_the_fixtures():
    report = evaluate_gates([_errored("banana_bread"), _errored("simple_pasta")])
    blockers = baseline_write_blockers(report)

    assert blockers
    joined = " ".join(blockers)
    assert "all 2 fixture(s) failed extraction" in joined
    assert "banana_bread" in joined and "simple_pasta" in joined
    assert "neither gate collected a sample" in joined


def test_a_run_with_zero_fixtures_is_blocked():
    blockers = baseline_write_blockers(evaluate_gates([]))
    assert any("0 fixtures" in b for b in blockers)


def test_the_fixture_list_is_truncated_so_the_message_stays_readable():
    report = evaluate_gates([_errored(f"fixture_{i}") for i in range(9)])
    joined = " ".join(baseline_write_blockers(report))

    assert "all 9 fixture(s) failed extraction" in joined
    assert "..." in joined
    assert "fixture_8" not in joined


def test_a_partial_run_is_writable_because_it_measured_something():
    # One good fixture out of three is a thin baseline, but it is a real
    # measurement — the operator can see sample_count and judge it.
    report = evaluate_gates([_ok("a"), _errored("b"), _errored("c")])

    assert baseline_write_blockers(report) == []
    assert report["calibration"]["result"]["sample_count"] == 1


def test_a_scored_run_with_no_confidence_samples_is_still_writable():
    # Titles measured, confidences absent: the extraction baseline is
    # meaningful even though the calibration one records nulls.
    scored = _ok("a")
    scored["extracted"].pop("confidence_score")
    report = evaluate_gates([scored])

    assert report["calibration"]["result"]["sample_count"] == 0
    assert report["title"]["result"]["sample_count"] == 1
    assert baseline_write_blockers(report) == []


def test_blockers_tolerate_a_malformed_report():
    assert baseline_write_blockers({}) == [
        "the run scored 0 fixtures",
        "neither gate collected a sample, so both baselines would record "
        "nulls under a real timestamp/commit",
    ]


def test_a_bool_sample_count_is_not_mistaken_for_a_measurement():
    report = {
        "fixture_count": 1,
        "errored_fixtures": [],
        "calibration": {"result": {"sample_count": True}},
        "title": {"result": {"sample_count": True}},
    }
    assert any("neither gate" in b for b in baseline_write_blockers(report))


# -------------------------------------------------------------------
# write_baselines refuses
# -------------------------------------------------------------------


def test_write_baselines_refuses_an_empty_run_and_leaves_the_files_alone(tmp_path):
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    write_baselines(
        evaluate_gates([_ok("a")]),
        calibration_path=cal_path,
        extraction_path=ext_path,
        generated_at="2026-01-01T00:00:00-07:00",
    )
    before = (cal_path.read_text(), ext_path.read_text())

    try:
        write_baselines(
            evaluate_gates([_errored("a")]),
            calibration_path=cal_path,
            extraction_path=ext_path,
            generated_at="2026-02-02T00:00:00-07:00",
        )
    except ValueError as exc:
        assert "refusing to write a baseline" in str(exc)
    else:  # pragma: no cover - the guard is the point of the test
        raise AssertionError("expected write_baselines to refuse")

    # Not partially rewritten: the calibration file is written first, so a
    # refusal that happened per-file would have clobbered it.
    assert (cal_path.read_text(), ext_path.read_text()) == before


def test_force_records_the_empty_run_anyway(tmp_path):
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    written = write_baselines(
        evaluate_gates([_errored("a")]),
        calibration_path=cal_path,
        extraction_path=ext_path,
        generated_at="2026-02-02T00:00:00-07:00",
        force=True,
    )

    assert len(written) == 2
    assert load_baseline(cal_path)["_generated_at"] == "2026-02-02T00:00:00-07:00"
    assert load_baseline(cal_path)["confidence_calibration"]["sample_count"] == 0


# -------------------------------------------------------------------
# What the refused write would have produced
# -------------------------------------------------------------------


def test_a_forced_empty_baseline_is_exactly_the_trap_being_prevented(tmp_path):
    """Pin the downstream damage, so the guard's value is legible."""
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    write_baselines(
        evaluate_gates([_errored("a")], emit_confidence=False),
        calibration_path=cal_path,
        extraction_path=ext_path,
        generated_at="2026-02-02T00:00:00-07:00",
        generated_commit="deadbeef",
        force=True,
    )
    baseline = load_baseline(ext_path)

    # Looks captured — full provenance, indistinguishable on disk from a
    # real step-1 baseline...
    assert baseline["_generated_commit"] == "deadbeef"
    assert baseline["_generated_at"] == "2026-02-02T00:00:00-07:00"
    assert baseline["_emit_confidence"] is False
    # ...holds nothing.
    assert baseline["title_extraction"]["title_extraction_f1"] is None
    assert baseline["title_extraction"]["sample_count"] == 0

    # The next run does contradict the file — but only at run time, and
    # only if the operator reads past "Baseline written".
    later = evaluate_gates(
        [_ok("a")], extraction_baseline=baseline, emit_confidence=True
    )
    assert later["ac11_comparison"]["kind"] == "no_baseline"
    assert later["title"]["gate"]["baseline_missing"] is True
    assert later["title"]["gate"]["passed"] is True


# -------------------------------------------------------------------
# Written-file hygiene
# -------------------------------------------------------------------


def test_comment_text_survives_a_write_without_unicode_escaping(tmp_path):
    cal_path = tmp_path / "cal.json"
    ext_path = tmp_path / "ext.json"
    cal_path.write_text(
        json.dumps({"_comment": "em—dash and a café"}, ensure_ascii=False) + "\n"
    )
    write_baselines(
        evaluate_gates([_ok("a")]),
        calibration_path=cal_path,
        extraction_path=ext_path,
    )
    raw = cal_path.read_text()

    assert "em—dash and a café" in raw
    assert "\\u2014" not in raw


def test_the_checked_in_baselines_round_trip_without_escaping(tmp_path):
    """The real files carry em-dashes; a write must not churn every line."""
    from src.confidence_gates import EXTRACTION_BASELINE_PATH

    original = EXTRACTION_BASELINE_PATH.read_text()
    assert "—" in original, "guard assumes the checked-in comments use em-dashes"

    ext_path = tmp_path / "ext.json"
    ext_path.write_text(original)
    write_baselines(
        evaluate_gates([_ok("a")]),
        calibration_path=tmp_path / "cal.json",
        extraction_path=ext_path,
    )
    assert "\\u2014" not in ext_path.read_text()


def test_fixture_counts_are_written_as_ints_not_means(tmp_path):
    # They ride the same _aggregate_scores mean path as the ratios, so they
    # arrive as 8.0 and would land in the baseline as floats.
    payload = build_extraction_baseline(
        evaluate_gates(
            [_ok("a")],
            aggregate={
                "overall_f1_avg": 0.8,
                "total_fixtures": 8.0,
                "fixtures_with_errors": 3.0,
            },
        )
    )
    scores = payload["extraction_scores"]

    assert scores["total_fixtures"] == 8
    assert isinstance(scores["total_fixtures"], int)
    assert isinstance(scores["fixtures_with_errors"], int)
    assert scores["overall_f1_avg"] == 0.8
    assert isinstance(scores["overall_f1_avg"], float)


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------


def _run_cli(args, tmp_path, fixtures, emit_confidence=False):
    from click.testing import CliRunner

    from src.main import cli
    from src.run_artifact import save_run_artifact

    run_path = tmp_path / "run.json"
    save_run_artifact(
        {"strategy": "text_extractor", "aggregate": {}, "fixtures": fixtures},
        run_path,
        emit_confidence=emit_confidence,
    )
    result = CliRunner().invoke(
        cli, ["confidence-gate", "--from-run", str(run_path), *args]
    )
    plain = " ".join(re.sub(r"\x1b\[[0-9;]*m", "", result.output).split())
    return result, plain


def _redirect_baseline_writes(monkeypatch, tmp_path):
    """Point the CLI's writes at tmp files, keeping the real guard live."""
    import src.confidence_gates as gates

    real = gates.write_baselines

    def _stub(report, **kwargs):
        kwargs.pop("calibration_path", None)
        kwargs.pop("extraction_path", None)
        return real(
            report,
            calibration_path=tmp_path / "cal.json",
            extraction_path=tmp_path / "ext.json",
            **kwargs,
        )

    monkeypatch.setattr(gates, "write_baselines", _stub)


def test_cli_refuses_and_says_how_to_override(tmp_path, monkeypatch):
    _redirect_baseline_writes(monkeypatch, tmp_path)

    result, output = _run_cli(["--write-baseline"], tmp_path, [_errored("a")])

    assert result.exit_code == 1
    assert "Baseline NOT written" in output
    assert "--force-baseline to record it anyway" in output
    assert not (tmp_path / "cal.json").exists()


def test_cli_force_baseline_writes_the_empty_run(tmp_path, monkeypatch):
    _redirect_baseline_writes(monkeypatch, tmp_path)

    result, output = _run_cli(
        ["--write-baseline", "--force-baseline"], tmp_path, [_errored("a")]
    )

    assert "Baseline written" in output
    assert "Baseline NOT written" not in output
    assert (tmp_path / "cal.json").exists()
    assert result.exit_code == 1  # the gates themselves still failed


def test_cli_rejects_force_baseline_without_write_baseline(tmp_path):
    result, output = _run_cli(["--force-baseline"], tmp_path, [_ok("a")])

    assert result.exit_code == 1
    assert "--force-baseline only applies with --write-baseline" in output


def test_cli_write_baseline_still_works_on_a_measured_run(tmp_path, monkeypatch):
    _redirect_baseline_writes(monkeypatch, tmp_path)

    result, output = _run_cli(["--write-baseline"], tmp_path, [_ok("a")])

    assert "Baseline written" in output
    assert "Baseline NOT written" not in output
    assert load_baseline(tmp_path / "ext.json")["title_extraction"]["sample_count"] == 1
    assert result.exit_code == 0
