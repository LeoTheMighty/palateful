"""Text-based recipe extractor using OpenAI for OCR text."""

import json
import logging
from typing import Any

from utils.services.recipe_extractors.base import (
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractionResult,
    validate_vibe,
)

logger = logging.getLogger(__name__)

GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015

TEXT_EXTRACTION_PROMPT = """Extract the recipe from the following OCR text and return it as JSON.

The text was obtained via OCR from a photograph of a physical recipe (cookbook page, recipe card, etc.).
It may contain OCR errors, irregular formatting, or noise. Do your best to interpret and correct obvious OCR mistakes.

Return a JSON object with the following structure:
{
    "name": "Recipe name",
    "description": "Brief description (if available)",
    "ingredients": [
        {"text": "2 cups all-purpose flour", "quantity": 2, "unit": "cups", "name": "all-purpose flour"}
    ],
    "instructions": "Step-by-step instructions as a single string",
    "servings": 4,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "author": "Author name",
    "cuisine": "Italian",
    "category": "Main Course"
}

Also assign 1-2 vibes from: [light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming]
Include in your JSON response: "primary_vibe": "...", "secondary_vibe": "..." or null

Rules:
- Only include fields you can find in the content
- For ingredients, always include the full "text" field with the corrected original text
- Parse quantity as a number (e.g., "1/2" should be 0.5)
- Parse unit and ingredient name separately when possible
- Correct obvious OCR errors (e.g., "f1our" → "flour", "1/2 tsp sa1t" → "1/2 tsp salt")
- If you cannot find recipe content, return {"error": "No recipe found"}

OCR Text:
"""


def extract_recipe_from_text(
    text: str,
    openai_client: Any = None,
) -> ExtractionResult:
    """Extract recipe from OCR text using AI.

    Args:
        text: Raw OCR text from photographed recipe.
        openai_client: Optional OpenAI client instance.

    Returns:
        ExtractionResult with the extracted recipe or error information.
    """
    if not text or len(text.strip()) < 20:
        return ExtractionResult(
            success=False,
            error_message="OCR text is too short to contain a recipe",
            error_code="TEXT_TOO_SHORT",
            extractor_used="text_ai",
        )

    try:
        if openai_client is None:
            from openai import OpenAI
            openai_client = OpenAI()

        # Truncate if too long
        max_chars = 16000
        cleaned_text = text.strip()
        if len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars] + "..."

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a recipe extraction assistant. Extract recipe data from OCR text and return valid JSON. Correct obvious OCR errors.",
                },
                {
                    "role": "user",
                    "content": TEXT_EXTRACTION_PROMPT + cleaned_text,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )

        # Calculate cost
        usage = response.usage
        total_tokens = usage.total_tokens if usage else 0
        cost_cents = int((total_tokens / 1000) * GPT4O_MINI_COST_PER_1K_TOKENS * 100)
        if total_tokens > 0 and cost_cents == 0:
            cost_cents = 1

        # Parse response
        content = response.choices[0].message.content
        if not content:
            return ExtractionResult(
                success=False,
                error_message="Empty response from AI",
                error_code="AI_EMPTY_RESPONSE",
                extractor_used="text_ai",
                ai_cost_cents=cost_cents,
            )

        data = json.loads(content)

        if "error" in data:
            return ExtractionResult(
                success=False,
                error_message=data["error"],
                error_code="AI_NO_RECIPE_FOUND",
                extractor_used="text_ai",
                ai_cost_cents=cost_cents,
            )

        recipe = _parse_response(data)

        return ExtractionResult(
            success=True,
            recipe=recipe,
            extractor_used="text_ai",
            ai_cost_cents=cost_cents,
        )

    except json.JSONDecodeError as e:
        logger.exception("Failed to parse AI response as JSON")
        return ExtractionResult(
            success=False,
            error_message=f"Failed to parse AI response: {e}",
            error_code="AI_JSON_PARSE_ERROR",
            extractor_used="text_ai",
        )
    except Exception as e:
        logger.exception("Error during text extraction")
        return ExtractionResult(
            success=False,
            error_message=str(e),
            error_code="AI_EXTRACTION_ERROR",
            extractor_used="text_ai",
        )


def _parse_response(data: dict) -> ExtractedRecipe:
    """Parse AI response into ExtractedRecipe."""
    ingredients = []
    for ing in data.get("ingredients", []):
        if isinstance(ing, dict):
            ingredients.append(
                ExtractedIngredient(
                    text=ing.get("text", ""),
                    quantity=ing.get("quantity"),
                    unit=ing.get("unit"),
                    name=ing.get("name"),
                    notes=ing.get("notes"),
                    is_optional=ing.get("is_optional", False),
                )
            )
        elif isinstance(ing, str):
            ingredients.append(ExtractedIngredient(text=ing))

    return ExtractedRecipe(
        name=data.get("name") or "Untitled Recipe",
        description=data.get("description"),
        ingredients=ingredients,
        instructions=data.get("instructions"),
        servings=data.get("servings"),
        prep_time_minutes=data.get("prep_time_minutes"),
        cook_time_minutes=data.get("cook_time_minutes"),
        total_time_minutes=data.get("total_time_minutes"),
        image_url=data.get("image_url"),
        author=data.get("author"),
        cuisine=data.get("cuisine"),
        category=data.get("category"),
        keywords=data.get("keywords", []),
        primary_vibe=validate_vibe(data.get("primary_vibe")),
        secondary_vibe=validate_vibe(data.get("secondary_vibe")),
        raw_data=data,
    )
