"""Text-based recipe extractor using OpenAI for OCR text."""

import json
import logging
from typing import Any

from utils.services.recipe_extractors.base import (
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractedStep,
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


def _steps_to_instructions(steps: Any) -> str | None:
    """Convert steps array to a single instructions string for backward compat.

    Accepts `Any` because the LLM sometimes returns the field as a string,
    a dict, or None; all of those fall through to None here and the caller
    falls back to `data["instructions"]`.
    """
    if not steps or not isinstance(steps, list):
        return None
    lines = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        lines.append(f"{s.get('order', i + 1)}. {s.get('instruction', '')}")
    return "\n".join(lines) if lines else None


def _parse_steps(raw_steps: Any) -> list[ExtractedStep] | None:
    """Parse the LLM's steps array into ExtractedStep objects.

    Returns None if the input is missing, not a list, or malformed in a
    way we can't recover from. Missing `order` values are backfilled by
    position. Missing `instruction` strings drop the step. On total
    failure the caller falls back to the joined `instructions` string.
    """
    if not raw_steps or not isinstance(raw_steps, list):
        return None
    parsed: list[ExtractedStep] = []
    for idx, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            continue
        instruction = raw.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            continue
        order_raw = raw.get("order", idx)
        try:
            order = int(order_raw)
        except (TypeError, ValueError):
            order = idx
        parsed.append(
            ExtractedStep(order=order, instruction=instruction.strip())
        )
    return parsed or None


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
        # Preserve BOTH shapes: structured `steps` for downstream
        # consumers that can handle them (create_recipe_task writes one
        # RecipeStep row per entry), and the joined `instructions`
        # string as a fallback for display and for the "graceful
        # degradation" path when steps parsing fails.
        steps=_parse_steps(data.get("steps")),
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
