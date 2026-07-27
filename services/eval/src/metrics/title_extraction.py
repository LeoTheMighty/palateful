"""irrd-3a — ``title_extraction_f1`` plus the AC11 soft regression gate.

irrd-3 changed the extractor prompts so the model also emits a
``confidence_score``. Adding an output field to a prompt is not free: it
can pull attention away from the fields that already worked. AC11 asks
for proof that the *title* — the one field a user notices instantly when
it's wrong — did not degrade.

``src.scoring`` has no title-only number. Its ``metadata_accuracy``
blends title, prep time, cook time, and servings into a single mean, so a
title regression can hide behind a servings improvement. This module adds
the dedicated metric:

    title_extraction_f1 = mean over fixtures of token-level F1 between
                          the extracted title and the ground-truth title

Token F1 (bag-of-tokens precision/recall, SQuAD-style) rather than a
boolean fuzzy match, because it degrades gradually: dropping a subtitle
costs recall proportionally instead of flipping a fixture from 1.0 to
0.0, which is what makes a 5% movement meaningful at 8 fixtures.

The gate is *relative*: the run must stay within
``TITLE_REGRESSION_MAX_RELATIVE_DROP`` (5%) of the recorded baseline in
``services/eval/baselines/extraction_baseline.json``. It deliberately
does not impose an absolute floor — this protects against *regression*
from the confidence prompts, which is the thing AC11 is about.

Pure arithmetic over already-collected extractions: no network, no
OpenAI key, no extractor imports. Producing the extractions is the
opt-in ~10-minute run; scoring them is unit-testable offline.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# AC11: the confidence-emitting prompts may not drop title_extraction_f1
# by more than 5% relative to the prior baseline.
TITLE_REGRESSION_MAX_RELATIVE_DROP = 0.05

# Keys an extracted/expected recipe dict may carry the title under.
# Fixtures use "name" (see services/eval/fixtures/expected/*.json);
# ``ExtractionResult`` payloads have been seen with both.
_TITLE_KEYS: tuple[str, ...] = ("name", "title")

# Float slack so a baseline round-tripped through JSON at 6 decimals
# doesn't fail its own gate.
_GATE_EPSILON = 1e-9

# How many of the worst-scoring fixtures to surface in the summary.
_WORST_OFFENDER_COUNT = 3

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class TitleSample:
    """One fixture's extracted title alongside the ground-truth title."""

    fixture_id: str
    extracted_title: str | None
    expected_title: str | None


def _title_of(recipe: Any) -> str | None:
    if not isinstance(recipe, dict):
        return None
    for key in _TITLE_KEYS:
        value = recipe.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _tokenize(title: str | None) -> list[str]:
    """Lowercase word tokens; punctuation and hyphens are separators."""
    if not title:
        return []
    return _TOKEN_RE.findall(title.lower())


def _token_f1(extracted: str | None, expected: str | None) -> dict[str, float]:
    """Bag-of-tokens precision / recall / F1 between two titles."""
    ext_tokens = _tokenize(extracted)
    exp_tokens = _tokenize(expected)

    if not ext_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Multiset overlap — a repeated token only counts as often as both
    # sides actually contain it.
    remaining: dict[str, int] = {}
    for token in exp_tokens:
        remaining[token] = remaining.get(token, 0) + 1
    overlap = 0
    for token in ext_tokens:
        if remaining.get(token, 0) > 0:
            remaining[token] -= 1
            overlap += 1

    precision = overlap / len(ext_tokens)
    recall = overlap / len(exp_tokens)
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _coerce_sample(raw: Any) -> TitleSample | None:
    """Accept a TitleSample, ``(extracted, expected)``, or
    ``(fixture_id, extracted, expected)``.

    Returns ``None`` for anything without a usable ground-truth title —
    a fixture with no expected name has nothing to regress against and
    must not be scored as a 0.0, which would drag the mean down for a
    reason unrelated to extraction quality.
    """
    if isinstance(raw, TitleSample):
        sample = raw
    elif isinstance(raw, dict):
        sample = TitleSample(
            fixture_id=str(raw.get("fixture_id") or raw.get("id") or "unknown"),
            extracted_title=_title_of(raw.get("extracted")),
            expected_title=_title_of(raw.get("expected")),
        )
    elif isinstance(raw, tuple | list) and len(raw) == 2:
        sample = TitleSample(
            fixture_id="unknown",
            extracted_title=_title_of(raw[0]),
            expected_title=_title_of(raw[1]),
        )
    elif isinstance(raw, tuple | list) and len(raw) == 3:
        sample = TitleSample(
            fixture_id=str(raw[0]),
            extracted_title=_title_of(raw[1]),
            expected_title=_title_of(raw[2]),
        )
    else:
        return None

    if not _tokenize(sample.expected_title):
        return None
    return sample


def compute_title_extraction_f1(pairs: Iterable[Any]) -> dict[str, Any]:
    """Compute ``title_extraction_f1`` over eval fixtures.

    Args:
        pairs: Iterable of :class:`TitleSample`, ``{"fixture_id",
            "extracted", "expected"}`` dicts, ``(extracted, expected)``
            recipe-dict tuples, or ``(fixture_id, extracted, expected)``
            triples. Entries whose *expected* recipe has no title are
            dropped and counted in ``skipped_count``.

    Returns:
        ``{"title_extraction_f1", "precision", "recall",
        "exact_match_rate", "sample_count", "skipped_count",
        "per_fixture", "worst_offenders"}``. The headline metric is
        ``None`` when nothing scored — an empty run is "unknown", never
        "perfect".
    """
    per_fixture: list[dict[str, Any]] = []
    skipped = 0

    for raw in pairs:
        sample = _coerce_sample(raw)
        if sample is None:
            skipped += 1
            continue
        scores = _token_f1(sample.extracted_title, sample.expected_title)
        per_fixture.append({
            "fixture_id": sample.fixture_id,
            "extracted_title": sample.extracted_title,
            "expected_title": sample.expected_title,
            "precision": scores["precision"],
            "recall": scores["recall"],
            "f1": scores["f1"],
            "exact_match": (
                _tokenize(sample.extracted_title)
                == _tokenize(sample.expected_title)
            ),
        })

    if not per_fixture:
        return {
            "title_extraction_f1": None,
            "precision": None,
            "recall": None,
            "exact_match_rate": None,
            "sample_count": 0,
            "skipped_count": skipped,
            "per_fixture": [],
            "worst_offenders": [],
        }

    n = len(per_fixture)
    return {
        "title_extraction_f1": sum(r["f1"] for r in per_fixture) / n,
        "precision": sum(r["precision"] for r in per_fixture) / n,
        "recall": sum(r["recall"] for r in per_fixture) / n,
        "exact_match_rate": sum(1 for r in per_fixture if r["exact_match"]) / n,
        "sample_count": n,
        "skipped_count": skipped,
        "per_fixture": per_fixture,
        "worst_offenders": sorted(per_fixture, key=lambda r: r["f1"])[
            :_WORST_OFFENDER_COUNT
        ],
    }


def _finite(value: Any) -> float | None:
    """Coerce to float, rejecting bool, NaN, and infinities."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def baseline_title_f1(baseline: Any) -> float | None:
    """Pull ``title_extraction_f1`` out of a baseline payload.

    Tolerates both the nested shape used by
    ``baselines/extraction_baseline.json`` and a bare
    ``{"title_extraction_f1": ...}`` dict, so a caller can hand the gate
    either the whole file or just the relevant section.
    """
    if not isinstance(baseline, dict):
        return None
    section = baseline.get("title_extraction")
    if isinstance(section, dict) and "title_extraction_f1" in section:
        return _finite(section.get("title_extraction_f1"))
    return _finite(baseline.get("title_extraction_f1"))


def check_title_regression_gate(
    result: dict[str, Any],
    baseline: dict[str, Any] | None = None,
    max_relative_drop: float = TITLE_REGRESSION_MAX_RELATIVE_DROP,
) -> dict[str, Any]:
    """Apply the AC11 gate: title F1 may not fall >5% below baseline.

    Three outcomes that are *not* a plain numeric comparison:

    * No samples (``title_extraction_f1 is None``) → **fail**. A gate
      that green-lights on an empty run protects nothing.
    * No baseline recorded (the checked-in placeholder is all nulls) →
      **pass**, flagged ``baseline_missing``. There is nothing to
      regress against; this run is what establishes the baseline.
    * Baseline of 0.0 → **pass** for any value; nothing can drop below
      zero and the relative drop is undefined.
    """
    value = _finite(result.get("title_extraction_f1"))
    baseline_value = baseline_title_f1(baseline)
    sample_count = result.get("sample_count", 0)

    common: dict[str, Any] = {
        "metric": "title_extraction_f1",
        "value": value,
        "baseline": baseline_value,
        "max_relative_drop": max_relative_drop,
        "sample_count": sample_count,
        "enforcement": "soft",
    }

    if value is None:
        return {
            **common,
            "passed": False,
            "baseline_missing": baseline_value is None,
            "min_allowed": None,
            "relative_drop": None,
            "reason": "no scored fixtures — title quality unknown, refusing to pass",
        }

    if baseline_value is None:
        return {
            **common,
            "passed": True,
            "baseline_missing": True,
            "min_allowed": None,
            "relative_drop": None,
            "reason": (
                f"no baseline recorded — nothing to regress against; "
                f"this run establishes title_extraction_f1 = {value:.4f}"
            ),
        }

    min_allowed = baseline_value * (1.0 - max_relative_drop)
    relative_drop = (
        (baseline_value - value) / baseline_value if baseline_value > 0 else 0.0
    )
    passed = value >= min_allowed - _GATE_EPSILON

    return {
        **common,
        "passed": passed,
        "baseline_missing": False,
        "min_allowed": min_allowed,
        "relative_drop": relative_drop,
        "reason": (
            f"title F1 {value:.4f} >= min allowed {min_allowed:.4f} "
            f"({max_relative_drop:.0%} below baseline {baseline_value:.4f})"
            if passed
            else f"title F1 {value:.4f} < min allowed {min_allowed:.4f} — "
            f"dropped {relative_drop:.2%} vs baseline {baseline_value:.4f}; "
            f"retune the confidence-emitting prompts before shipping"
        ),
    }


def _fmt(value: Any, spec: str = ".4f") -> str:
    return format(value, spec) if isinstance(value, float) else "n/a"


def format_title_regression_summary(
    result: dict[str, Any],
    gate: dict[str, Any],
) -> str:
    """Human-readable pass/fail block for the run output.

    Carries metric value, baseline, and threshold on the headline lines
    so a regression is diagnosable from the run output alone.
    """
    status = "PASSED" if gate.get("passed") else "FAILED"
    lines = [
        "=" * 64,
        f"TITLE EXTRACTION REGRESSION GATE: {status}",
        "=" * 64,
        f"  title F1       : {_fmt(gate.get('value'))}",
        f"  baseline F1    : {_fmt(gate.get('baseline'))}",
        f"  max drop       : {gate.get('max_relative_drop', 0):.0%} relative",
        f"  min allowed    : {_fmt(gate.get('min_allowed'))}",
        "  actual drop    : "
        + (
            f"{gate['relative_drop']:+.2%}"
            if isinstance(gate.get("relative_drop"), float)
            else "n/a"
        ),
        f"  fixtures       : {result.get('sample_count', 0)}"
        + (
            f" ({result['skipped_count']} skipped — no ground-truth title)"
            if result.get("skipped_count")
            else ""
        ),
        f"  precision      : {_fmt(result.get('precision'))}",
        f"  recall         : {_fmt(result.get('recall'))}",
        f"  exact match    : {_fmt(result.get('exact_match_rate'))}",
        f"  enforcement    : {gate.get('enforcement', 'soft')}",
        f"  reason         : {gate.get('reason', '')}",
    ]

    worst = result.get("worst_offenders") or []
    if worst and not gate.get("passed"):
        lines.append("  worst fixtures :")
        for row in worst:
            lines.append(
                f"    - {row['fixture_id']}: F1 {row['f1']:.3f} | "
                f"got {row['extracted_title']!r} "
                f"want {row['expected_title']!r}"
            )

    lines.append("=" * 64)
    return "\n".join(lines)
