"""eri-2: ingredient-only parse pass for JSON-LD text-only ingredients.

JSON-LD's ``recipeIngredient`` field is spec'd as a plain-string list,
so ``JsonLdExtractor`` emits ``ExtractedIngredient(text=..., qty=None,
unit=None, name=None)`` for every row. This module fills those in via
a focused gpt-4o-mini call — a strict JSON-schema response format
pins the shape, temperature 0 pins determinism, and a per-batch
timeout + graceful fallback keeps the downstream import path safe
when OpenAI misbehaves.

Called from ``extract_recipe_from_html`` (eri-3a) on the text-only
subset of a JSON-LD recipe. Structured rows from JSON-LD itself are
passed through untouched.

Design notes (see ``epic-extractor-richer-ingredients.md``):

* Batches of **25** (not 50-then-remainder) for prompt-order
  determinism.
* Cap at ``max_total=200``; anything beyond dumps back as text-only
  with one ``IngredientParsePathological`` audit row per import.
* On any batch failure (rate limit, timeout, 5xx, schema violation,
  empty response) we log ``IngredientParseFailure`` and return the
  text-only inputs for that batch unchanged. Partial success across
  batches is fine — earlier successful batches are kept.
* Per-call token counts logged so we can true-up cost for the first
  week.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from utils.logging.ingredient_parse_logging import (
    log_ingredient_parse_failure,
    log_ingredient_parse_pathological,
)
from utils.services.recipe_extractors.base import ExtractedIngredient
from utils.services.recipe_extractors.unit_prompt import unit_rule

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_DEFAULT_BATCH_SIZE = 25
_DEFAULT_MAX_TOTAL = 200
_DEFAULT_TIMEOUT_SECONDS = 10.0

# Short freeform fallback used only if both flags are off. Kept
# intentionally terse — the main `unit_rule()` path provides the
# full list; this is just the "both-flags-off" rollback backstop.
_FREEFORM_UNIT_RULE = (
    '- "unit": the measurement unit only (e.g. "cup", "tbsp", "g"). '
    "Use null for count items or when there is no unit."
)


# Strict JSON-schema pinning the array-of-objects shape we want back.
# OpenAI's structured-output mode rejects any response that doesn't
# match this — eliminates the "wrapped in {ingredients: [...]}" and
# "dict instead of list" failure classes.
_PARSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "name": {"type": "string"},
                    "notes": {"type": ["string", "null"]},
                },
                "required": ["quantity", "unit", "name", "notes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ingredients"],
    "additionalProperties": False,
}


def _build_prompt(strings: list[str]) -> str:
    """Build the ingredient-only parse prompt for one batch.

    The prompt splices in ``unit_rule()`` so the soften/canonical/
    freeform decision lives in exactly one place (``unit_prompt.py``).
    """
    numbered = "\n".join(
        f"{i + 1}. {s}" for i, s in enumerate(strings)
    )
    return f"""Parse each ingredient string below into structured fields.

Return a JSON object with this shape — EXACTLY ONE entry per input, in input order:

{{
  "ingredients": [
    {{"quantity": <number or null>, "unit": <string or null>, "name": <string>, "notes": <string or null>}}
  ]
}}

Rules:
- "quantity": a number ONLY. Convert fractions ("1/2" -> 0.5, "1 1/2" -> 1.5). Use null for non-numeric amounts ("a pinch", "to taste"). Never include the unit or name here.
{unit_rule(freeform_fallback=_FREEFORM_UNIT_RULE)}
- "name": the canonical ingredient name, stripped of quantity, unit, and prep notes (e.g. "garlic" not "1 clove garlic, minced"; "vinegar" not "300 gram of vinegar").
- "notes": preparation/state qualifiers ("minced", "chopped", "room temperature", "to taste", "divided") or null. Do NOT hallucinate notes — if the source has no qualifier, notes MUST be null.

For ranges ("1-2 cups" / "1 to 2 cups"): emit "quantity" as the first value and capture the full range in "notes" (e.g. quantity=1, notes="to 2 cups").
Respect word boundaries: "a pinchful" is NOT "pinch" (unit: null, notes="pinchful").

Ingredient strings:
{numbered}
"""


def _to_text_only(strings: list[str]) -> list[ExtractedIngredient]:
    """Fall-through for a failed batch / overflow: the same nulls
    ``JsonLdExtractor`` would have emitted."""
    return [ExtractedIngredient(text=s.strip()) for s in strings]


def _parse_one_batch(
    strings: list[str],
    openai_client: Any,
    *,
    timeout_seconds: float,
    url_sample: str | None,
    import_item_id: Any,
) -> tuple[list[ExtractedIngredient], int]:
    """Parse one batch. Returns (ingredients, total_tokens).

    On ANY failure class (rate limit, timeout, 5xx, schema violation,
    empty response, wrong count, malformed JSON), logs
    ``IngredientParseFailure`` and falls back to text-only for this
    batch. Token count is 0 if the call didn't land.
    """
    prompt = _build_prompt(strings)
    try:
        response = openai_client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You parse ingredient lines into structured JSON. "
                        "Return exactly one object per input, in input order."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ingredient_parse",
                    "schema": _PARSE_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 — capture every OpenAI failure class
        error_class = exc.__class__.__name__
        logger.warning(
            "ingredient_parse: batch of %d failed with %s: %s",
            len(strings),
            error_class,
            exc,
        )
        log_ingredient_parse_failure(
            error_class=error_class,
            batch_size=len(strings),
            url_sample=url_sample,
            import_item_id=import_item_id,
        )
        return _to_text_only(strings), 0

    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

    content = response.choices[0].message.content if response.choices else None
    if not content:
        log_ingredient_parse_failure(
            error_class="EmptyResponse",
            batch_size=len(strings),
            url_sample=url_sample,
            import_item_id=import_item_id,
        )
        return _to_text_only(strings), total_tokens

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("ingredient_parse: non-JSON response: %s", exc)
        log_ingredient_parse_failure(
            error_class="JSONDecodeError",
            batch_size=len(strings),
            url_sample=url_sample,
            import_item_id=import_item_id,
        )
        return _to_text_only(strings), total_tokens

    raw = data.get("ingredients") if isinstance(data, dict) else None
    if not isinstance(raw, list) or len(raw) != len(strings):
        logger.warning(
            "ingredient_parse: schema violation — got %s entries for %d inputs",
            "None" if raw is None else len(raw),
            len(strings),
        )
        log_ingredient_parse_failure(
            error_class="SchemaViolation",
            batch_size=len(strings),
            url_sample=url_sample,
            import_item_id=import_item_id,
            extra={"got_len": len(raw) if isinstance(raw, list) else None},
        )
        return _to_text_only(strings), total_tokens

    parsed: list[ExtractedIngredient] = []
    for original, item in zip(strings, raw, strict=False):
        if not isinstance(item, dict):
            # One-off malformed item — fall back for just this row.
            parsed.append(ExtractedIngredient(text=original.strip()))
            continue
        qty_raw = item.get("quantity")
        try:
            quantity = float(qty_raw) if qty_raw is not None else None
        except (TypeError, ValueError):
            quantity = None
        unit = item.get("unit")
        name = item.get("name")
        notes = item.get("notes")
        # Preserve the original line in `text` so the UI stays in sync with
        # how json_ld.py populates it when the parse pass fires. The
        # pre-ERI behavior already put the whole raw line in `text`; we
        # keep that invariant.
        parsed.append(
            ExtractedIngredient(
                text=original.strip(),
                quantity=quantity,
                unit=unit if isinstance(unit, str) and unit else None,
                name=name if isinstance(name, str) and name.strip() else None,
                notes=notes if isinstance(notes, str) and notes.strip() else None,
            )
        )
    return parsed, total_tokens


def parse_ingredient_strings(
    strings: list[str],
    openai_client: Any,
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    max_total: int = _DEFAULT_MAX_TOTAL,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    url_sample: str | None = None,
    import_item_id: Any = None,
) -> list[ExtractedIngredient]:
    """Parse text-only ingredient strings into ``ExtractedIngredient``s.

    Empty input returns empty output. Overflow beyond ``max_total`` is
    dumped back as text-only and triggers one
    ``IngredientParsePathological`` audit row.

    The return list is always the same length as the input and ordered
    to match input order.
    """
    if not strings:
        return []

    tail: list[str] = []
    if len(strings) > max_total:
        # Parse up to max_total; dump the overflow back as text-only and
        # log one `IngredientParsePathological` audit row so the edge
        # case is visible.
        log_ingredient_parse_pathological(
            total=len(strings),
            max_total=max_total,
            url_sample=url_sample,
            import_item_id=import_item_id,
        )
        tail = strings[max_total:]
        strings = strings[:max_total]

    results: list[ExtractedIngredient] = []
    total_tokens_sum = 0
    for start in range(0, len(strings), batch_size):
        batch = strings[start : start + batch_size]
        parsed, tokens = _parse_one_batch(
            batch,
            openai_client,
            timeout_seconds=timeout_seconds,
            url_sample=url_sample,
            import_item_id=import_item_id,
        )
        results.extend(parsed)
        total_tokens_sum += tokens

    if total_tokens_sum:
        logger.info(
            "ingredient_parse: %d strings parsed in %d batches — %d tokens",
            len(strings),
            (len(strings) + batch_size - 1) // batch_size,
            total_tokens_sum,
        )
    if tail:
        results.extend(_to_text_only(tail))
    return results
