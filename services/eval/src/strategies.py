"""Strategy registry for recipe extraction evaluation.

Each strategy maps to a specific extractor pipeline. The registry is used
by the fixture-based runner to determine which extraction function to call
for a given input type.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------------

STRATEGIES: dict[str, dict[str, Any]] = {
    "text_extractor": {
        "name": "GPT-4o-mini Text",
        "description": "Extract from text via GPT-4o-mini",
        "function": "run_text_extraction",
        "input_types": ["text"],
    },
    "vision_extractor": {
        "name": "GPT-4o-mini Vision",
        "description": "Extract from image via GPT-4o-mini vision",
        "function": "run_vision_extraction",
        "input_types": ["image"],
    },
    "ocr_then_text": {
        "name": "HunyuanOCR + GPT-4o-mini",
        "description": "OCR image then extract text",
        "function": "run_ocr_then_text",
        "input_types": ["image"],
    },
}


# ---------------------------------------------------------------------------
# Strategy runner functions
# ---------------------------------------------------------------------------

def run_text_extraction(text: str, openai_client: Any = None) -> dict[str, Any]:
    """Run the production TextExtractor on raw text.

    Args:
        text: Raw OCR or plain text containing a recipe.
        openai_client: Optional OpenAI client (for testing / mocking).

    Returns:
        Recipe dict matching the standard extraction schema.
    """
    from utils.services.recipe_extractors.text_extractor import extract_recipe_from_text

    result = extract_recipe_from_text(text, openai_client=openai_client)

    if not result.success or result.recipe is None:
        raise RuntimeError(
            f"Text extraction failed: {result.error_message} ({result.error_code})"
        )

    return _recipe_to_dict(result.recipe)


def run_vision_extraction(image_path: str, **kwargs: Any) -> dict[str, Any]:
    """Extract recipe from an image via GPT-4o-mini vision.

    Not yet implemented -- placeholder for a future vision-based pipeline.
    """
    raise NotImplementedError(
        "Vision extraction strategy is not yet implemented. "
        "Use 'ocr_then_text' for image-based extraction."
    )


def run_ocr_then_text(image_path: str, **kwargs: Any) -> dict[str, Any]:
    """Run HunyuanOCR on an image, then feed the text through text_extractor.

    Not yet implemented -- requires the parser service to be running locally
    or a direct model import.
    """
    raise NotImplementedError(
        "OCR-then-text strategy is not yet implemented. "
        "Requires the parser service for OCR inference."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recipe_to_dict(recipe: Any) -> dict[str, Any]:
    """Convert an ExtractedRecipe dataclass to a plain dict."""
    if hasattr(recipe, "__dataclass_fields__"):
        result = asdict(recipe)
        # Omit internal raw_data to keep the dict clean
        result.pop("raw_data", None)
        return result

    if hasattr(recipe, "__dict__"):
        result = {}
        for key, value in recipe.__dict__.items():
            if key.startswith("_"):
                continue
            if hasattr(value, "__dataclass_fields__"):
                result[key] = asdict(value)
            elif isinstance(value, list):
                result[key] = [
                    asdict(item) if hasattr(item, "__dataclass_fields__") else item
                    for item in value
                ]
            else:
                result[key] = value
        result.pop("raw_data", None)
        return result

    return dict(recipe) if isinstance(recipe, dict) else {}


def get_strategy_function(strategy_name: str):
    """Look up the callable for a given strategy name.

    Returns:
        The strategy runner function.

    Raises:
        ValueError: If the strategy name is unknown.
    """
    entry = STRATEGIES.get(strategy_name)
    if entry is None:
        available = ", ".join(STRATEGIES.keys())
        raise ValueError(f"Unknown strategy '{strategy_name}'. Available: {available}")

    func_name = entry["function"]
    func_map = {
        "run_text_extraction": run_text_extraction,
        "run_vision_extraction": run_vision_extraction,
        "run_ocr_then_text": run_ocr_then_text,
    }

    func = func_map.get(func_name)
    if func is None:
        raise ValueError(f"Strategy function '{func_name}' not found in registry")

    return func


def list_strategies() -> list[dict[str, Any]]:
    """Return a summary list of available strategies."""
    return [
        {"key": key, **{k: v for k, v in entry.items() if k != "function"}}
        for key, entry in STRATEGIES.items()
    ]
