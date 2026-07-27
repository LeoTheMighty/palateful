"""irrd-3a — persist one expensive fixture run so the gates can replay it.

The confidence gates need a real run: ``OPENAI_API_KEY`` and ~10 minutes
over the checked-in fixtures. AC9 then asks the operator to *retune the
heuristic weights until MAE <= 0.3*, which naively means paying for a
fresh run after every weight edit.

It doesn't have to. The heuristic is a pure function of the extracted
recipe (``compute_heuristic_confidence``), and the extraction itself does
not depend on the weights — so the same run replayed under new weights
yields exactly the confidence scores a fresh run would have produced.
Model-emitted scores are a different story: nothing offline can change
what the model said, so those are replayed verbatim.

This module is the storage half of that: save a run's per-fixture
payloads to JSON, load it back, and recompute the heuristic-sourced
confidences under whatever weights are currently in
``confidence_heuristic.py``. ``src.confidence_gates.replay_gates`` is the
consumer.

The saved artifact is a debugging record, not a checked-in baseline —
write it to /tmp or an untracked path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Bumped when the artifact's shape changes incompatibly. ``load_run_artifact``
# refuses anything it doesn't recognise rather than silently mis-reading a
# future file.
RUN_ARTIFACT_SCHEMA_VERSION = 1

_HEURISTIC_SOURCE = "heuristic"


# ---------------------------------------------------------------------------
# Build / save
# ---------------------------------------------------------------------------

def build_run_artifact(
    summary: dict[str, Any],
    generated_at: str | None = None,
    generated_commit: str | None = None,
    emit_confidence: bool | None = None,
) -> dict[str, Any]:
    """Wrap a ``fixture_runner.run_eval`` summary in a versioned envelope.

    ``emit_confidence`` records the ``EXTRACTOR_EMIT_CONFIDENCE`` state the
    run happened under — without it a replayed report can't say whether
    the scores came from a model that was asked or one that never was.
    """
    return {
        "_schema_version": RUN_ARTIFACT_SCHEMA_VERSION,
        "_comment": (
            "irrd-3a saved fixture run. Replay the confidence gates over it "
            "with `npx nx run eval:confidence-gate -- --from-run <this file>` "
            "— no OPENAI_API_KEY needed. Heuristic-sourced confidences are "
            "recomputed under the current weights in confidence_heuristic.py, "
            "so a weight retune can be confirmed without re-running extraction."
        ),
        "_generated_at": generated_at,
        "_generated_commit": generated_commit,
        "emit_confidence": emit_confidence,
        "strategy": summary.get("strategy"),
        "fixtures": summary.get("fixtures") or [],
        "aggregate": summary.get("aggregate") or {},
    }


def save_run_artifact(
    summary: dict[str, Any],
    path: str | Path,
    generated_at: str | None = None,
    generated_commit: str | None = None,
    emit_confidence: bool | None = None,
) -> Path:
    """Write :func:`build_run_artifact` to ``path``. Returns the path written.

    ``default=str`` mirrors the rest of the CLI's result-dumping: an
    unexpected non-JSON value in an extracted payload degrades to its
    repr instead of losing the whole (expensive) run.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = build_run_artifact(
        summary,
        generated_at=generated_at,
        generated_commit=generated_commit,
        emit_confidence=emit_confidence,
    )
    target.write_text(json.dumps(artifact, indent=2, default=str) + "\n")
    return target


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_run_artifact(path: str | Path) -> dict[str, Any]:
    """Read a saved run back, or raise ``ValueError`` explaining why not.

    Loud rather than lenient: a replay that silently ran over zero
    fixtures would report a failing gate with no samples, which looks
    exactly like a legitimately failing run.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Saved run not found: {p}")
    try:
        loaded = json.loads(p.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"Saved run is not readable JSON: {p} ({exc})") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Saved run must be a JSON object: {p}")

    version = loaded.get("_schema_version")
    if version != RUN_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"Saved run schema version {version!r} is not supported "
            f"(expected {RUN_ARTIFACT_SCHEMA_VERSION}): {p}"
        )
    if not isinstance(loaded.get("fixtures"), list):
        raise ValueError(f"Saved run has no 'fixtures' list: {p}")
    return loaded


# ---------------------------------------------------------------------------
# Replay under current weights
# ---------------------------------------------------------------------------

def _heuristic_confidence(recipe: Any) -> float:
    """Current-weights heuristic score, read from the production module.

    Imported lazily so this module stays importable without the extractor
    package on the path.
    """
    from utils.services.recipe_extractors.confidence_heuristic import (
        compute_heuristic_confidence,
    )

    return compute_heuristic_confidence(recipe)


def recompute_heuristic_confidences(
    fixture_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Re-score heuristic-sourced fixtures under the current weights.

    Returns ``(results, changes)`` where ``results`` is a copy — the input
    is never mutated, so a caller can compare as-recorded against
    recomputed — and ``changes`` lists
    ``{fixture_id, recorded, recomputed}`` for every fixture that was
    re-scored (including ones whose score happened not to move, so the
    report can say how many samples the weights actually reach).

    Model-sourced fixtures, errored fixtures, and fixtures saved without
    payloads are passed through untouched: no offline computation can
    tell us what the model would have said.
    """
    results: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for raw in fixture_results:
        if not isinstance(raw, dict):
            continue
        result = json.loads(json.dumps(raw, default=str))
        extracted = result.get("extracted")
        if (
            not result.get("error")
            and isinstance(extracted, dict)
            and extracted.get("confidence_source") == _HEURISTIC_SOURCE
        ):
            recorded = extracted.get("confidence_score")
            recomputed = _heuristic_confidence(extracted)
            extracted["confidence_score"] = recomputed
            changes.append({
                "fixture_id": result.get("id", "unknown"),
                "recorded": recorded,
                "recomputed": recomputed,
            })
        results.append(result)

    return results, changes


def moved_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The subset of :func:`recompute_heuristic_confidences` that actually moved.

    A replay under unchanged weights recomputes every heuristic sample and
    moves none of them; that distinction is what tells an operator whether
    their weight edit reached the samples they thought it would.
    """
    moved = []
    for change in changes:
        recorded = change.get("recorded")
        recomputed = change.get("recomputed")
        if not isinstance(recorded, int | float) or isinstance(recorded, bool):
            moved.append(change)
            continue
        if abs(float(recomputed) - float(recorded)) > 1e-9:
            moved.append(change)
    return moved
