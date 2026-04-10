"""Strategy registry for recipe extraction evaluation.

Each strategy maps to a specific extractor pipeline. The registry is used
by the fixture-based runner to determine which extraction function to call
for a given input type.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

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
        "description": "OCR image then extract text via sidecar .ocr.txt",
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

    Loads the image from *image_path*, passes it to the production vision
    extractor, and returns the extracted recipe as a dict.

    Args:
        image_path: Filesystem path to the image file.

    Returns:
        Recipe dict matching the standard extraction schema.
    """
    from utils.services.recipe_extractors.vision_extractor import (
        extract_recipe_from_image,
    )

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image = Image.open(path)
    openai_client = kwargs.get("openai_client")

    result = extract_recipe_from_image(image, openai_client=openai_client)

    if not result.success or result.recipe is None:
        raise RuntimeError(
            f"Vision extraction failed: {result.error_message} ({result.error_code})"
        )

    return _recipe_to_dict(result.recipe)


def run_ocr_then_text(image_path: str, **kwargs: Any) -> dict[str, Any]:
    """Simulate the OCR-then-text pipeline for eval comparison.

    Instead of running the HunyuanOCR model (which requires the parser
    service), this reads a pre-extracted OCR sidecar file and feeds it
    through the production text extractor.  This lets us compare:

        "OCR raw text -> GPT-4o-mini text" vs "GPT-4o-mini vision direct"

    Sidecar convention:
        For ``fixtures/images/potato_quiche.jpg`` the sidecar is
        ``fixtures/images/potato_quiche.ocr.txt``.

    Args:
        image_path: Filesystem path to the image file.

    Returns:
        Recipe dict matching the standard extraction schema.

    Raises:
        FileNotFoundError: If the ``.ocr.txt`` sidecar does not exist.
    """
    from utils.services.recipe_extractors.text_extractor import extract_recipe_from_text

    path = Path(image_path)
    sidecar = path.with_suffix(".ocr.txt")

    if not sidecar.is_file():
        raise FileNotFoundError(
            f"OCR sidecar not found: {sidecar}. "
            f"Create a '{path.stem}.ocr.txt' file next to the image with "
            f"the raw OCR output to use this strategy."
        )

    ocr_text = sidecar.read_text(encoding="utf-8")
    openai_client = kwargs.get("openai_client")

    result = extract_recipe_from_text(ocr_text, openai_client=openai_client)

    if not result.success or result.recipe is None:
        raise RuntimeError(
            f"OCR-then-text extraction failed: {result.error_message} "
            f"({result.error_code})"
        )

    return _recipe_to_dict(result.recipe)


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
