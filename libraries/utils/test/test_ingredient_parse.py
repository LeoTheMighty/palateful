"""eri-2: parse_ingredient_strings unit tests.

Covers happy path, batching, cap, and every failure fallback class
(rate limit, timeout, 5xx, empty response, schema violation, malformed
JSON, wrong-count-response). The OpenAI client is always a MagicMock;
no real calls are made. Audit-log emissions are intercepted via
`monkeypatch` on the logging helper so we can assert the exact
`error_class` we pass through.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.services.recipe_extractors.base import ExtractedIngredient
from utils.services.recipe_extractors.ingredient_parse import (
    _DEFAULT_BATCH_SIZE,
    _DEFAULT_MAX_TOTAL,
    parse_ingredient_strings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(items: list[dict], *, total_tokens: int = 100):
    """Build a MagicMock that mimics an OpenAI ChatCompletion response."""
    content = json.dumps({"ingredients": items})
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_tokens=total_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def _client_returning(response):
    """Return a MagicMock client whose chat.completions.create returns `response`."""
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


def _client_raising(exc):
    """Return a MagicMock client whose chat.completions.create raises `exc`."""
    client = MagicMock()
    client.chat.completions.create.side_effect = exc
    return client


@pytest.fixture
def capture_audit(monkeypatch):
    """Capture IngredientParseFailure audit calls without touching the DB."""
    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_failure",
        _record,
    )
    return calls


@pytest.fixture
def capture_pathological(monkeypatch):
    """Capture IngredientParsePathological audit calls without touching the DB."""
    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "utils.services.recipe_extractors.ingredient_parse.log_ingredient_parse_pathological",
        _record,
    )
    return calls


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_parses_three_ingredients(capture_audit):
    response = _build_response(
        [
            {"quantity": 1, "unit": "clove", "name": "garlic", "notes": "minced"},
            {"quantity": 300, "unit": "g", "name": "vinegar", "notes": None},
            {"quantity": 2, "unit": "stalk", "name": "celery", "notes": "chopped"},
        ]
    )
    client = _client_returning(response)

    result = parse_ingredient_strings(
        [
            "1 clove garlic, minced",
            "300 gram of vinegar",
            "2 stalks celery, chopped",
        ],
        client,
    )
    assert len(result) == 3
    assert result[0].quantity == 1
    assert result[0].unit == "clove"
    assert result[0].name == "garlic"
    assert result[0].notes == "minced"
    # text preserves the original raw line
    assert result[0].text == "1 clove garlic, minced"
    assert result[1].quantity == 300
    assert result[1].unit == "g"
    assert result[1].notes is None
    assert result[2].unit == "stalk"
    assert capture_audit == []


def test_empty_input_returns_empty_without_calling_openai():
    client = MagicMock()
    assert parse_ingredient_strings([], client) == []
    client.chat.completions.create.assert_not_called()


def test_preserves_input_order_and_length():
    response = _build_response(
        [
            {"quantity": 1, "unit": "cup", "name": "flour", "notes": None},
            {"quantity": 2, "unit": "cup", "name": "sugar", "notes": None},
        ]
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup flour", "2 cups sugar"], client)
    assert [r.text for r in result] == ["1 cup flour", "2 cups sugar"]


def test_null_quantity_and_unit_allowed(capture_audit):
    response = _build_response(
        [{"quantity": None, "unit": None, "name": "salt", "notes": "to taste"}]
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["Salt, to taste"], client)
    assert result[0].quantity is None
    assert result[0].unit is None
    assert result[0].name == "salt"
    assert result[0].notes == "to taste"
    assert capture_audit == []


def test_coerces_string_quantity_to_float_when_possible(capture_audit):
    response = _build_response(
        [
            {"quantity": "0.5", "unit": "cup", "name": "milk", "notes": None},
        ]
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1/2 cup milk"], client)
    assert result[0].quantity == 0.5


def test_malformed_per_row_quantity_falls_through_to_null(capture_audit):
    response = _build_response(
        [
            {"quantity": "not a number", "unit": "cup", "name": "milk", "notes": None},
        ]
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup milk"], client)
    assert result[0].quantity is None
    assert result[0].unit == "cup"


# ---------------------------------------------------------------------------
# Batching: 25-per-batch, two calls for 26 inputs
# ---------------------------------------------------------------------------


def test_batches_of_25_are_sent_separately(capture_audit):
    client = MagicMock()
    # Two calls — first 25, then 1. Each gets a matching-length response.
    client.chat.completions.create.side_effect = [
        _build_response(
            [{"quantity": 1, "unit": "cup", "name": f"n{i}", "notes": None} for i in range(25)]
        ),
        _build_response(
            [{"quantity": 1, "unit": "cup", "name": "tail", "notes": None}]
        ),
    ]
    strings = [f"1 cup n{i}" for i in range(26)]
    result = parse_ingredient_strings(strings, client)
    assert len(result) == 26
    assert client.chat.completions.create.call_count == 2
    assert capture_audit == []


def test_default_batch_size_is_25_and_max_total_is_200():
    # Constant-pin so a future refactor can't silently shrink the cap.
    assert _DEFAULT_BATCH_SIZE == 25
    assert _DEFAULT_MAX_TOTAL == 200


# ---------------------------------------------------------------------------
# Cap: >max_total overflow dumps to text-only
# ---------------------------------------------------------------------------


def test_overflow_beyond_max_total_is_text_only(capture_audit, capture_pathological):
    client = MagicMock()
    # Small caps for a cheap test. We expect 2 calls (batch_size=2, max_total=4 -> 2 batches of 2).
    client.chat.completions.create.side_effect = [
        _build_response(
            [
                {"quantity": 1, "unit": "cup", "name": "a", "notes": None},
                {"quantity": 1, "unit": "cup", "name": "b", "notes": None},
            ]
        ),
        _build_response(
            [
                {"quantity": 1, "unit": "cup", "name": "c", "notes": None},
                {"quantity": 1, "unit": "cup", "name": "d", "notes": None},
            ]
        ),
    ]
    strings = [f"{i} cup thing-{i}" for i in range(6)]  # 6 > max_total=4
    result = parse_ingredient_strings(
        strings, client, batch_size=2, max_total=4
    )
    assert len(result) == 6
    # First 4 are parsed
    assert result[0].name == "a"
    assert result[3].name == "d"
    # Last 2 are text-only (null fields)
    assert result[4].name is None
    assert result[4].quantity is None
    assert result[4].unit is None
    assert result[4].text == strings[4]
    assert result[5].text == strings[5]
    # Pathological audit fired exactly once with the total + overflow
    assert len(capture_pathological) == 1
    assert capture_pathological[0]["total"] == 6
    assert capture_pathological[0]["max_total"] == 4


def test_no_pathological_audit_under_cap(capture_audit, capture_pathological):
    response = _build_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    client = _client_returning(response)
    parse_ingredient_strings(["1 cup flour"], client, batch_size=2, max_total=4)
    assert capture_pathological == []


# ---------------------------------------------------------------------------
# Failure fallbacks — each class falls through to text-only for that batch
# ---------------------------------------------------------------------------


class _FakeRateLimitError(Exception):
    pass


class _FakeAPIError(Exception):
    pass


class _FakeTimeoutError(Exception):
    pass


def test_rate_limit_error_returns_text_only_and_audits(capture_audit):
    client = _client_raising(_FakeRateLimitError("429"))
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert len(result) == 1
    assert result[0].text == "1 cup flour"
    assert result[0].quantity is None
    assert result[0].unit is None
    assert len(capture_audit) == 1
    assert capture_audit[0]["error_class"] == "_FakeRateLimitError"
    assert capture_audit[0]["batch_size"] == 1


def test_timeout_returns_text_only_and_audits(capture_audit):
    client = _client_raising(_FakeTimeoutError("slow"))
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert result[0].quantity is None
    assert capture_audit[0]["error_class"] == "_FakeTimeoutError"


def test_api_5xx_returns_text_only_and_audits(capture_audit):
    client = _client_raising(_FakeAPIError("503"))
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert result[0].text == "1 cup flour"
    assert capture_audit[0]["error_class"] == "_FakeAPIError"


def test_empty_response_content_audits_and_falls_through(capture_audit):
    # Response arrived but content is empty.
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
        usage=SimpleNamespace(total_tokens=5),
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert result[0].quantity is None
    assert capture_audit[0]["error_class"] == "EmptyResponse"


def test_non_json_content_audits_and_falls_through(capture_audit):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
        usage=SimpleNamespace(total_tokens=5),
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert result[0].quantity is None
    assert capture_audit[0]["error_class"] == "JSONDecodeError"


def test_schema_violation_wrong_count_audits_and_falls_through(capture_audit):
    # Model returned 1 entry for 2 inputs — schema violation per our contract.
    response = _build_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup flour", "2 cups sugar"], client)
    assert len(result) == 2
    assert all(r.quantity is None and r.name is None for r in result)
    assert capture_audit[0]["error_class"] == "SchemaViolation"


def test_schema_violation_missing_ingredients_key_audits(capture_audit):
    # Model returned a different top-level key.
    content = json.dumps({"not_ingredients": []})
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=5),
    )
    client = _client_returning(response)
    result = parse_ingredient_strings(["1 cup flour"], client)
    assert result[0].quantity is None
    assert capture_audit[0]["error_class"] == "SchemaViolation"


# ---------------------------------------------------------------------------
# Partial success across batches — earlier batches kept, later batch falls
# through on failure.
# ---------------------------------------------------------------------------


def test_partial_success_keeps_earlier_batches_and_falls_through_on_late_failure(
    capture_audit,
):
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _build_response(
            [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
        ),
        _FakeRateLimitError("2nd batch rate limited"),
    ]
    result = parse_ingredient_strings(
        ["1 cup flour", "2 cups sugar"], client, batch_size=1
    )
    assert len(result) == 2
    # First batch succeeded
    assert result[0].quantity == 1
    assert result[0].name == "flour"
    # Second batch fell through
    assert result[1].quantity is None
    assert result[1].text == "2 cups sugar"
    # One audit call for the failed batch
    assert len(capture_audit) == 1
    assert capture_audit[0]["error_class"] == "_FakeRateLimitError"


# ---------------------------------------------------------------------------
# Per-call kwargs — strict schema response format wiring + temperature 0
# ---------------------------------------------------------------------------


def test_request_uses_strict_json_schema_response_format(capture_audit):
    response = _build_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    client = _client_returning(response)
    parse_ingredient_strings(["1 cup flour"], client)
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["temperature"] == 0
    # Strict json_schema response format is the whole point
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["strict"] is True
    # Timeout flows through to the OpenAI SDK
    assert "timeout" in call_kwargs


def test_timeout_kwarg_is_threaded_through(capture_audit):
    response = _build_response(
        [{"quantity": 1, "unit": "cup", "name": "flour", "notes": None}]
    )
    client = _client_returning(response)
    parse_ingredient_strings(["1 cup flour"], client, timeout_seconds=7.5)
    assert client.chat.completions.create.call_args.kwargs["timeout"] == 7.5
