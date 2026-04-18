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
from utils.services.recipe_extractors.unit_prompt import unit_rule

logger = logging.getLogger(__name__)

GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015

# Legacy freeform unit instruction kept for the rollback path
# (EXTRACTOR_EMIT_CANONICAL_UNITS=false).
_FREEFORM_UNIT_RULE = (
    '- "unit": the measurement unit ONLY (e.g. "cup", "tablespoon", '
    '"teaspoon", "pound", "ounce", "clove", "piece", "can", "recipe"). Use '
    'null for count items ("3 large eggs" -> unit: null) or when there is no '
    "unit. Never include the number or ingredient name here."
)


def _vision_system_prompt() -> str:
    """riip-3: build the prompt with the canonical-or-freeform unit rule."""
    return f"""Extract every recipe from this image and return them as JSON.

The image may be a cookbook page, printed recipe card, handwritten recipe, screenshot, or phone photo.
Handle these common challenges:
- Handwritten text: do your best to decipher; skip truly illegible parts
- Partial or cropped images: extract whatever is visible
- Blurry or low-quality photos: infer from context when characters are unclear
- Multiple recipes on a page: emit each as a separate object in the "recipes" array; do not merge them.
- Decorative fonts or watermarks: ignore non-recipe content

Multi-recipe detection:
- If the image contains MULTIPLE DISTINCT recipes (e.g. a cookbook facing-page spread, two recipe cards side-by-side), emit EACH as a separate object in the "recipes" array, in the order they read top-to-bottom, left-to-right.
- A recipe is "distinct" when it has its own title AND its own ingredient list.
- A "Variation", "Substitution Notes", or "Serving Suggestions" subsection is NOT a distinct recipe — fold it into the preceding recipe's description or ignore.
- If only one recipe is present, return a length-1 array.

Return a JSON object with EXACTLY this structure:
{{
    "recipes": [
        {{
            "name": "Recipe Name",
            "description": "Brief 1-2 sentence description of the dish",
            "ingredients": [
                {{
                    "text": "all-purpose flour, sifted",
                    "quantity": 2,
                    "unit": "cup",
                    "name": "all-purpose flour",
                    "notes": "sifted",
                    "is_optional": false
                }}
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
        }}
    ]
}}

Ingredient rules — CRITICAL: quantity, unit, and text are rendered together downstream as "<quantity> <unit> <text>". Do NOT duplicate information across these fields or the UI will show things like "9 tbsp 9 tbsp butter".

- "quantity": a number ONLY. Convert fractions ("1/2" -> 0.5, "1 1/2" -> 1.5). Use null when the source has no numeric quantity ("a pinch", "to taste", "Salt"). Never include the unit or ingredient name here.
{unit_rule(freeform_fallback=_FREEFORM_UNIT_RULE)}
- "name": the canonical ingredient name, stripped of quantity, unit, and prep notes. Use the most generic form: "onion" not "diced yellow onion", "butter" not "9 tbsp butter".
- "notes": preparation or state qualifiers ("chopped", "minced", "sauteed", "room temperature", "divided", "to taste") or null.
- "text": the ingredient DESCRIPTION as it should appear next to the quantity and unit. Keep prep qualifiers in natural order, but STRIP the numeric quantity and the unit off the front. Never begins with a number or a unit. If the source has no quantity/unit to strip (e.g. "Salt"), use the whole line.
- "is_optional": true only if explicitly marked optional in the recipe.

Worked examples (source line -> extracted fields):
- "9 tablespoons butter" ->
    {{"text": "butter", "quantity": 9, "unit": "tbsp", "name": "butter", "notes": null, "is_optional": false}}
- "3 tablespoons minced shallots" ->
    {{"text": "minced shallots", "quantity": 3, "unit": "tbsp", "name": "shallots", "notes": "minced", "is_optional": false}}
- "1/2 cup diced onion, sauteed" ->
    {{"text": "diced onion, sauteed", "quantity": 0.5, "unit": "cup", "name": "onion", "notes": "diced, sauteed", "is_optional": false}}
- "3 large eggs" ->
    {{"text": "large eggs", "quantity": 3, "unit": null, "name": "eggs", "notes": "large", "is_optional": false}}
- "Pinch nutmeg" ->
    {{"text": "nutmeg", "quantity": null, "unit": "pinch", "name": "nutmeg", "notes": null, "is_optional": false}}
- "Salt to taste" ->
    {{"text": "salt, to taste", "quantity": null, "unit": null, "name": "salt", "notes": "to taste", "is_optional": false}}

BAD examples — do NOT produce these:
- {{"text": "9 tbsp butter", "quantity": 9, "unit": "tbsp", ...}}   # text repeats quantity+unit
- {{"text": "tbsp butter", "quantity": 9, "unit": "tbsp", ...}}     # text repeats unit
- {{"quantity": "9 tbsp", ...}}                                     # quantity must be a number

Vibe assignment:
- primary_vibe: the single best vibe for the dish
- secondary_vibe: a second vibe only if clearly applicable, otherwise null
- Valid vibes: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming

General rules:
- Only include fields you can find or reasonably infer from the image
- Set missing fields to null rather than guessing
- If you cannot find recipe content, return {{"error": "No recipe found"}}
- Return ONLY valid JSON. No markdown fences, no explanation text."""


# Backward-compat alias — `VISION_SYSTEM_PROMPT` was a string before riip-3.
# Kept for any test that imports it directly.
VISION_SYSTEM_PROMPT = _vision_system_prompt()


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
                        {"type": "text", "text": _vision_system_prompt()},
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

        # Validate against standard schema — applied per-recipe below on the
        # bare-object fallback; the multi-recipe wrapper fails this check
        # because validate_extraction_result expects a single recipe shape.
        if "recipes" not in data:
            is_valid, errors = validate_extraction_result(data)
            if not is_valid:
                logger.warning("Vision extraction produced invalid schema: %s", errors)

        recipes = _parse_recipes_payload(data)
        if not recipes:
            return ExtractionResult(
                success=False,
                error_message="No recipes found in AI response",
                error_code="AI_NO_RECIPE_FOUND",
                extractor_used="vision_ai",
                ai_cost_cents=cost_cents,
            )

        return ExtractionResult(
            success=True,
            recipes=recipes,
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


def _parse_recipes_payload(data: dict) -> list[ExtractedRecipe]:
    """Parse the vision-AI response into a list of ExtractedRecipe.

    Accepts both the new multi-recipe shape (`{"recipes": [...]}`) and
    the legacy bare-recipe shape. A bare object is silently wrapped in a
    length-1 list so the pipeline keeps working if the model ignores the
    new instruction.
    """
    raw_list = data.get("recipes")
    if isinstance(raw_list, list):
        return [
            _parse_response(item)
            for item in raw_list
            if isinstance(item, dict)
        ]
    logger.warning(
        "vision_extractor: model returned bare recipe instead of {'recipes': [...]}; wrapping"
    )
    return [_parse_response(data)]


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
