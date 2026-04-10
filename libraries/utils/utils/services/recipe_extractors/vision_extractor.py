"""Vision-based recipe extractor using OpenAI GPT-4o-mini."""

import base64
import io
import json
import logging
from typing import Any

from PIL import Image

from utils.schemas.recipe_extraction_schema import validate_extraction_result
from utils.services.recipe_extractors.base import (
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractionResult,
    validate_vibe,
)

logger = logging.getLogger(__name__)

GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015

VISION_SYSTEM_PROMPT = """Extract the recipe from this image and return it as JSON.

The image may be a cookbook page, printed recipe card, handwritten recipe, screenshot, or phone photo.
Handle these common challenges:
- Handwritten text: do your best to decipher; skip truly illegible parts
- Partial or cropped images: extract whatever is visible
- Blurry or low-quality photos: infer from context when characters are unclear
- Multiple recipes on a page: extract only the primary/largest recipe
- Decorative fonts or watermarks: ignore non-recipe content

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
    "instructions": "All steps as a single string, numbered. E.g.: 1. Preheat oven to 350F. 2. Mix dry ingredients...",
    "servings": 4,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "total_time_minutes": 45,
    "author": "Author name if visible",
    "cuisine": "e.g. Italian, Mexican, American, etc.",
    "category": "e.g. Main Course, Dessert, Appetizer, Side Dish, Breakfast, Soup, Salad, Bread, Beverage, Snack",
    "primary_vibe": "one of: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming",
    "secondary_vibe": "a different vibe from the same list, or null"
}

Ingredient examples:
  "3 large eggs"        -> {"text": "3 large eggs", "quantity": 3, "unit": null, "name": "large eggs", "notes": null, "is_optional": false}
  "1/2 cup diced onion" -> {"text": "1/2 cup diced onion", "quantity": 0.5, "unit": "cup", "name": "onion", "notes": "diced", "is_optional": false}
  "salt to taste"       -> {"text": "salt to taste", "quantity": null, "unit": null, "name": "salt", "notes": "to taste", "is_optional": false}

Ingredient rules:
- "text": the full ingredient line as it appears in the recipe
- "quantity": a number (convert fractions: "1/2" -> 0.5, "1 1/2" -> 1.5) or null
- "unit": standard unit (cup, tablespoon, teaspoon, pound, ounce, etc.) or null for count items
- "name": ingredient name without quantity, unit, or preparation notes
- "notes": preparation details (chopped, sauteed, room temperature) or null
- "is_optional": true only if explicitly marked optional in the recipe

Vibe assignment:
- primary_vibe: the single best vibe for the dish
- secondary_vibe: a second vibe only if clearly applicable, otherwise null
- Valid vibes: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming

General rules:
- Only include fields you can find or reasonably infer from the image
- Set missing fields to null rather than guessing
- If you cannot find recipe content, return {"error": "No recipe found"}
- Return ONLY valid JSON. No markdown fences, no explanation text."""


def extract_recipe_from_image(
    image: Image.Image | bytes,
    openai_client: Any = None,
) -> ExtractionResult:
    """Extract a structured recipe from an image using GPT-4o-mini vision.

    Args:
        image: PIL Image or raw bytes of the image.
        openai_client: Optional OpenAI client instance.

    Returns:
        ExtractionResult with the extracted recipe or error information.
    """
    try:
        # Convert to base64
        if isinstance(image, Image.Image):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
        else:
            image_bytes = image

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI()

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise recipe extraction assistant. "
                        "Extract structured recipe data from images of recipes and return valid JSON. "
                        "Handle printed text, handwritten notes, and low-quality photos. "
                        "Parse ingredient quantities as numbers, separate units from names, "
                        "and assign recipe vibes."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
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
                extractor_used="vision_ai",
                ai_cost_cents=cost_cents,
            )

        data = json.loads(content)

        if "error" in data:
            return ExtractionResult(
                success=False,
                error_message=data["error"],
                error_code="AI_NO_RECIPE_FOUND",
                extractor_used="vision_ai",
                ai_cost_cents=cost_cents,
            )

        # Validate against standard schema
        is_valid, errors = validate_extraction_result(data)
        if not is_valid:
            logger.warning("Vision extraction produced invalid schema: %s", errors)

        recipe = _parse_response(data)

        return ExtractionResult(
            success=True,
            recipe=recipe,
            extractor_used="vision_ai",
            ai_cost_cents=cost_cents,
        )

    except json.JSONDecodeError as e:
        logger.exception("Failed to parse AI vision response as JSON")
        return ExtractionResult(
            success=False,
            error_message=f"Failed to parse AI response: {e}",
            error_code="AI_JSON_PARSE_ERROR",
            extractor_used="vision_ai",
        )
    except Exception as e:
        logger.exception("Error during vision extraction")
        return ExtractionResult(
            success=False,
            error_message=str(e),
            error_code="AI_EXTRACTION_ERROR",
            extractor_used="vision_ai",
        )


def _parse_response(data: dict) -> ExtractedRecipe:
    """Parse AI vision response into ExtractedRecipe."""
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
