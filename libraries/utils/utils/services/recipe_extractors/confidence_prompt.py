"""Self-reported confidence prompt rule, gated by EXTRACTOR_EMIT_CONFIDENCE.

irrd-3 — when the flag is on (default), LLM-based extractors (ai, vision,
text) include a prompt instruction telling the model to emit a
`confidence_score` float in [0, 1] and a `confidence_source` of "model"
at the top of the recipe object. When the flag is off, the instruction
is omitted and downstream post-processing always falls back to the
heuristic (`confidence_source` -> "heuristic"), giving us a no-redeploy
rollback via ECS task def flip.

Read at extractor-call time, not at process startup, so a flag flip
applies to the very next request.
"""

from __future__ import annotations

import os

_CONFIDENCE_RULE = (
    "- Always include TWO extra top-level keys on each recipe object:\n"
    '    * "confidence_score": a float in [0.0, 1.0] reporting your own '
    "confidence in the full extraction. Emit `null` if you cannot "
    "self-assess. Emit `0.0` only when the extraction meaningfully "
    "failed — null and 0.0 are NOT the same signal.\n"
    '    * "confidence_source": the literal string "model".'
)


def emit_confidence() -> bool:
    """Read the feature flag at call time. Default-on."""
    raw = os.environ.get("EXTRACTOR_EMIT_CONFIDENCE", "true")
    return raw.strip().lower() not in ("false", "0", "no", "off")


def confidence_rule() -> str:
    """Return the prompt fragment for self-reported confidence.

    Empty string when the flag is OFF — callers splice the result in as
    ``{confidence_rule()}`` and expect no content when disabled.
    """
    if emit_confidence():
        return _CONFIDENCE_RULE
    return ""
