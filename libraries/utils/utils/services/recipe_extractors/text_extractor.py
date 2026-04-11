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

The text was obtained via OCR from a photograph of a physical recipe (cookbook page, recipe card, handwritten note, etc.).
It may contain OCR artifacts such as:
- Character substitutions (digits for letters: "f1our" -> "flour", "sa1t" -> "salt", "0nion" -> "onion")
- Coordinate noise or bounding-box numbers from OCR engines (ignore any stray numbers not part of the recipe)
- Irregular line breaks, merged words, or split words across lines
- Garbled text, repeated characters, or missing spaces
- Headers, footers, page numbers, or watermarks mixed in

Do your best to interpret and correct these OCR errors to produce a clean, accurate recipe.

Return a JSON object with EXACTLY this structure:
{
    "name": "Recipe Name",
    "description": "Brief 1-2 sentence description of the dish",
    "ingredients": [
        {
            "text": "2 cups all-purpose flour",
            "quantity": 2,
            "unit": "cups",
            "name": "all-purpose flour",
            "notes": "sifted",
            "is_optional": false
        }
    ],
    "steps": [
        {"instruction": "Preheat oven to 350F.", "order": 1},
        {"instruction": "Mix dry ingredients in a large bowl.", "order": 2},
        {"instruction": "Bake for 25 minutes.", "order": 3}
    ],
    "servings": 4,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "total_time_minutes": 45,
    "author": "Author name if found",
    "cuisine": "e.g. Italian, Mexican, American, etc.",
    "category": "e.g. Main Course, Dessert, Appetizer, Side Dish, Breakfast, Soup, Salad, Bread, Beverage, Snack",
    "primary_vibe": "one of: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming",
    "secondary_vibe": "a different vibe from the same list, or null"
}

Ingredient rules:
- "text": the corrected full ingredient line as a human would read it (e.g. "1/2 cup diced onion, sauteed")
- "quantity": a number (convert fractions: "1/2" -> 0.5, "1 1/2" -> 1.5, "a pinch" -> null)
- "unit": standard unit string (e.g. "cup", "tablespoon", "teaspoon", "pound", "ounce", "clove", "piece") or null for count items (e.g. "3 large eggs" -> unit: null)
- "name": the ingredient name without quantity, unit, or preparation notes (e.g. "all-purpose flour", "large eggs", "Gruyere cheese")
- "notes": preparation details like "chopped", "sauteed", "room temperature", or null
- "is_optional": true only if the recipe explicitly says the ingredient is optional

Vibe assignment:
- Choose a primary_vibe that best captures the dish's character
- Choose a secondary_vibe only if a second vibe clearly applies; otherwise set to null
- Valid vibes: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming

General rules:
- Only include fields you can actually find or reasonably infer from the text
- Set missing fields to null rather than guessing
- If you cannot find recipe content at all, return {"error": "No recipe found"}
- Return ONLY valid JSON. No markdown fences, no explanation text.

OCR Text:
"""


def _steps_to_instructions(steps: list[dict] | None) -> str | None:
    """Convert steps array to a single instructions string for backward compat."""
    if not steps:
        return None
    return "\n".join(
        f"{s.get('order', i+1)}. {s.get('instruction', '')}"
        for i, s in enumerate(steps)
    )


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
                    "content": (
                        "You are a precise recipe extraction assistant. "
                        "Extract structured recipe data from OCR text and return valid JSON. "
                        "Correct OCR artifacts (character substitutions, coordinate noise, garbled text). "
                        "Parse ingredient quantities as numbers, separate units from names, "
                        "and assign recipe vibes."
                    ),
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
        instructions=_steps_to_instructions(data.get("steps")) or data.get("instructions"),
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
