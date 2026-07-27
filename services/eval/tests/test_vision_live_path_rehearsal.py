"""Offline rehearsal of the *live* vision path (bugs-imp-pho-7).

Every other vision test fakes the extractor: `test_vision_extraction_evaluator`
monkeypatches `extract_recipe_from_image` itself, and
`test_vision_suite_end_to_end` seeds the cache with the expected JSON
*as if* it were model output. Both therefore grade a payload that is
perfectly shaped by construction, and neither ever runs the production
extractor.

That leaves the one leg that the single paid run actually depends on
untested: real PNG bytes -> real `extract_recipe_from_image` -> real
`ExtractedRecipe` dataclasses -> `_recipe_to_dict` -> the metric code. If
those shapes disagree, the baseline comes back looking like a model
failure and the money is spent.

These tests stub exactly one boundary — the OpenAI SDK client — and run
everything else for real. No network, no key, no spend.

They also pin the two *ground-truth skews* that cap what a perfect
extraction can score, so the baseline numbers are read correctly rather
than mistaken for model misses. See the README's "Reading the baseline"
table.
"""

import base64
import json
from pathlib import Path

import openai
import pytest
import yaml

from src.config import EvalConfig, ThresholdConfig
from src.evaluators.vision_extraction_evaluator import VisionExtractionEvaluator

SERVICE_DIR = Path(__file__).resolve().parent.parent
REAL_SUITE_DIR = SERVICE_DIR / "datasets" / "vision_extraction"
REAL_MANIFEST = REAL_SUITE_DIR / "manifest.yaml"

# Plural / spelled-out unit words used by the committed ground truth, mapped
# to the canonical token the production prompt actually asks the model for
# (`utils.services.recipe_extractors.unit_prompt`).
GROUND_TRUTH_TO_CANONICAL = {
    "cups": "cup",
    "tablespoons": "tbsp",
    "tablespoon": "tbsp",
    "teaspoons": "tsp",
    "teaspoon": "tsp",
    "slices": "slice",
}


# --------------------------------------------------------------------------
# OpenAI SDK stub — the only faked boundary.
# --------------------------------------------------------------------------


class _StubCompletions:
    def __init__(self, stub: "_StubClient"):
        self._stub = stub

    def create(self, **kwargs):
        self._stub.calls.append(kwargs)
        if self._stub.raises is not None:
            raise self._stub.raises
        return _StubResponse(self._stub.content, self._stub.total_tokens)


class _StubChat:
    def __init__(self, stub: "_StubClient"):
        self.completions = _StubCompletions(stub)


class _StubClient:
    """Stands in for `openai.OpenAI()`; records every request."""

    def __init__(self, content: str, *, total_tokens: int, raises: Exception | None):
        self.content = content
        self.total_tokens = total_tokens
        self.raises = raises
        self.calls: list[dict] = []
        self.chat = _StubChat(self)


class _StubResponse:
    def __init__(self, content: str, total_tokens: int):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]
        self.usage = type("U", (), {"total_tokens": total_tokens})()


@pytest.fixture
def stub_openai(monkeypatch):
    """Patch `openai.OpenAI` and hand back the stub for assertions.

    `extract_recipe_from_image` does `from openai import OpenAI` at call
    time, so patching the module attribute is enough — and it is the only
    patch these tests apply.
    """

    def _install(payload, *, total_tokens: int = 4000, raises: Exception | None = None):
        content = payload if isinstance(payload, str) else json.dumps(payload)
        stub = _StubClient(content, total_tokens=total_tokens, raises=raises)
        monkeypatch.setattr(openai, "OpenAI", lambda *a, **k: stub)
        return stub

    return _install


# --------------------------------------------------------------------------
# Suite plumbing — a tmp dataset dir so live-path cache writes stay out of
# the checkout, pointing at the *committed* manifest and PNGs.
# --------------------------------------------------------------------------


def _absolutized_manifest() -> dict:
    manifest = yaml.safe_load(REAL_MANIFEST.read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        for key in ("image", "expected"):
            if key in case:
                case[key] = str((REAL_SUITE_DIR / case[key]).resolve())
    return manifest


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    suite = tmp_path / "vision_extraction"
    suite.mkdir(parents=True)
    (suite / "manifest.yaml").write_text(yaml.safe_dump(_absolutized_manifest()))
    return tmp_path


def _evaluator(dataset_dir: Path, *, mock_ai: bool = False) -> VisionExtractionEvaluator:
    return VisionExtractionEvaluator(
        EvalConfig(
            dataset_dir=dataset_dir,
            mock_ai=mock_ai,
            cache_responses=True,
            parallel_workers=1,
            thresholds=ThresholdConfig(recipe_count_accuracy=0.80),
        )
    )


def _case(evaluator: VisionExtractionEvaluator, case_id: str):
    for case in evaluator.load_cases():
        if case.id == case_id:
            return case
    raise AssertionError(f"case {case_id} vanished from the committed manifest")


def _ground_truth_payload(evaluator, case) -> dict:
    """The expected JSON replayed as if the model had returned it."""
    return {"recipes": [dict(r) for r in evaluator._normalize_to_recipe_list(case.expected_data)]}


def _canonicalize_units(payload: dict) -> tuple[dict, int]:
    """Rewrite ground-truth unit words into the tokens the prompt asks for."""
    out = json.loads(json.dumps(payload))
    rewritten = 0
    for recipe in out["recipes"]:
        for ing in recipe.get("ingredients") or []:
            unit = ing.get("unit")
            canonical = GROUND_TRUTH_TO_CANONICAL.get(str(unit).lower()) if unit else None
            if canonical and canonical != unit:
                ing["unit"] = canonical
                rewritten += 1
    return out, rewritten


# --------------------------------------------------------------------------
# The request the paid run will actually send.
# --------------------------------------------------------------------------


def test_live_path_sends_the_committed_png_to_gpt4o_mini(dataset_dir, stub_openai):
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "multi_recipe_facing_pages")
    stub = stub_openai(_ground_truth_payload(evaluator, case))

    evaluator.evaluate(case)

    assert len(stub.calls) == 1, "one image must cost exactly one call"
    request = stub.calls[0]
    assert request["model"] == "gpt-4o-mini"
    assert request["response_format"] == {"type": "json_object"}

    image_part = next(
        part for part in request["messages"][1]["content"] if part["type"] == "image_url"
    )
    url = image_part["image_url"]["url"]
    assert image_part["image_url"]["detail"] == "high"
    assert url.startswith("data:image/png;base64,")
    # The bytes on the wire are the committed fixture, not a re-encode.
    assert base64.b64decode(url.split(",", 1)[1]) == case.input_path.read_bytes()


# --------------------------------------------------------------------------
# Shape parity: production output vs the committed ground truth.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_id",
    [
        "banana_bread",
        "simple_pasta",
        "multi_recipe_facing_pages",
        "multi_recipe_side_by_side",
        "multi_recipe_three_panel",
    ],
)
def test_ground_truth_response_grades_a_perfect_case(dataset_dir, stub_openai, case_id):
    """A model that returns the expected JSON verbatim must score 1.0
    everywhere. Anything less is an evaluator/fixture shape mismatch, and
    would show up in the paid baseline as a model failure."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, case_id)
    stub_openai(_ground_truth_payload(evaluator, case))

    result = evaluator.evaluate(case)

    assert result.error is None
    assert result.skipped is False
    assert result.metrics["recipe_count_accuracy"] == 1.0
    assert result.metrics["field_accuracy"] == pytest.approx(1.0)
    assert result.metrics["missing_fields"] == []
    assert result.passed is True


def test_timer_annotation_is_not_graded_as_a_recipe_field(dataset_dir, stub_openai):
    """`expected_timers` is a grading annotation, not something an
    extractor emits. Counting it as an expected field silently capped
    field_accuracy at 7/8 on every timer-annotated fixture."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "simple_pasta")
    assert "expected_timers" in case.expected_data, "fixture lost its timer annotation"
    stub_openai(_ground_truth_payload(evaluator, case))

    result = evaluator.evaluate(case)

    assert result.metrics["field_accuracy"] == pytest.approx(1.0)
    assert "expected_timers" not in result.metrics["missing_fields"]


def test_extractor_output_carries_the_expected_recipe_keys(dataset_dir, stub_openai):
    """Pin the production `ExtractedRecipe` -> dict projection: the keys
    the fixtures grade on must all survive it."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "banana_bread")
    stub_openai(_ground_truth_payload(evaluator, case))

    result = evaluator.evaluate(case)
    recipe = result.actual_output["recipes"][0]

    for key in case.expected_data:
        if key == "expected_timers":
            continue
        assert key in recipe, f"production output dropped the graded field {key!r}"
    ingredient = recipe["ingredients"][0]
    assert {"text", "quantity", "unit", "name", "notes"} <= set(ingredient)


# --------------------------------------------------------------------------
# Ground-truth skews: what a *prompt-compliant* perfect model really scores.
# --------------------------------------------------------------------------


def test_canonical_units_cap_field_accuracy_below_one(dataset_dir, stub_openai):
    """The prompt tells the model to emit `cup`/`tbsp`/`tsp`; the committed
    ground truth spells them `cups`/`tablespoons`/`teaspoon`. Ingredient
    dicts compare exactly, so a model that obeys the prompt loses the whole
    `ingredients` field. This is the real ceiling — not a regression."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "multi_recipe_facing_pages")
    payload, rewritten = _canonicalize_units(_ground_truth_payload(evaluator, case))
    assert rewritten > 0, "fixture no longer uses spelled-out unit words"
    stub_openai(payload)

    result = evaluator.evaluate(case)

    # 5 of 6 graded fields; only `ingredients` mismatches.
    assert result.metrics["field_accuracy"] == pytest.approx(5 / 6)
    assert result.metrics["recipe_count_accuracy"] == 1.0, "counts are unaffected"


def test_reading_the_page_instructions_scores_zero_similarity(dataset_dir, stub_openai):
    """The multi-recipe fixtures render Directions in the PNG but carry no
    `instructions` key, so `instruction_similarity` is 0.0 for a model that
    correctly reads them. Reported, not gated — and not a model miss."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "multi_recipe_facing_pages")
    assert all(
        "instructions" not in r for r in evaluator._normalize_to_recipe_list(case.expected_data)
    )
    payload = _ground_truth_payload(evaluator, case)
    for recipe in payload["recipes"]:
        recipe["instructions"] = "1. Whisk the dry ingredients.\n2. Cook."
    stub_openai(payload)

    result = evaluator.evaluate(case)

    assert result.metrics["instruction_similarity"] == 0.0
    assert result.metrics["field_accuracy"] == pytest.approx(1.0), (
        "instructions is not a graded field on this fixture"
    )


# --------------------------------------------------------------------------
# Cost, caching, and the operator's live-run -> re-grade two-step.
# --------------------------------------------------------------------------


def test_cost_cents_come_from_reported_token_usage(dataset_dir, stub_openai):
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "banana_bread")
    stub_openai(_ground_truth_payload(evaluator, case), total_tokens=1_000_000)

    result = evaluator.evaluate(case)

    assert result.cost_cents > 0
    assert result.duration_ms >= 0


def test_live_run_then_mock_regrade_reproduces_the_metrics(dataset_dir, stub_openai):
    """The documented procedure: one paid run fills the cache, then every
    later grade replays it offline. The two must agree exactly."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "multi_recipe_three_panel")
    stub_openai(_ground_truth_payload(evaluator, case))

    live = evaluator.evaluate(case)
    assert live.cache_hit is False

    regrade = _evaluator(dataset_dir, mock_ai=True).evaluate(_case(evaluator, case.id))

    assert regrade.cache_hit is True
    assert regrade.skipped is False
    assert regrade.metrics["recipe_count_accuracy"] == live.metrics["recipe_count_accuracy"]
    assert regrade.metrics["field_accuracy"] == pytest.approx(live.metrics["field_accuracy"])
    assert regrade.metrics["multi_recipe_count_accuracy"] == 1.0


def test_api_failure_grades_zero_and_leaves_the_cache_clean(dataset_dir, stub_openai):
    """A bad key or a rate limit must not be remembered — a later mock
    re-grade would replay it as a fabricated 0.0."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "multi_recipe_side_by_side")
    stub_openai({}, raises=RuntimeError("401 invalid api key"))

    result = evaluator.evaluate(case)

    assert result.error is None, "an API failure is a graded miss, not a case error"
    assert result.metrics["recipe_count_accuracy"] == 0.0
    assert result.metrics["multi_recipe_count_accuracy"] == 0.0
    assert list(evaluator.cache_dir.glob("*.json")) == []


def test_model_ignoring_the_recipes_envelope_still_grades(dataset_dir, stub_openai):
    """`_parse_recipes_payload` wraps a bare recipe object. On a
    single-recipe fixture that is a correct answer, and the count metric
    must say so rather than reading the envelope literally."""
    evaluator = _evaluator(dataset_dir)
    case = _case(evaluator, "banana_bread")
    stub_openai(dict(case.expected_data))  # bare recipe, no "recipes" key

    result = evaluator.evaluate(case)

    assert result.metrics["actual_recipe_count"] == 1
    assert result.metrics["recipe_count_accuracy"] == 1.0
