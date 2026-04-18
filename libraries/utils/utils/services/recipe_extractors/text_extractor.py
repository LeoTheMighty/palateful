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
from utils.services.recipe_extractors.confidence_heuristic import resolve_confidence
from utils.services.recipe_extractors.confidence_prompt import confidence_rule
from utils.services.recipe_extractors.unit_prompt import unit_rule

logger = logging.getLogger(__name__)

GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015

# Legacy freeform unit instruction kept for the rollback path
# (EXTRACTOR_EMIT_CANONICAL_UNITS=false).
_FREEFORM_UNIT_RULE = (
    '- "unit": the measurement unit ONLY, lowercase, singular or the original '
    'form (e.g. "cup", "tablespoon", "teaspoon", "pound", "ounce", "clove", '
    '"piece", "can", "recipe"). Use null for count items ("3 large eggs" -> '
    "unit: null) and for quantity-less items. Never include the number or "
    "the ingredient name here."
)


def _text_extraction_prompt() -> str:
    """riip-3: build the prompt with the canonical-or-freeform unit rule."""
    return f"""Extract every recipe from the following OCR text and return them as JSON.

The text was obtained via OCR from a photograph of a physical recipe (cookbook page, recipe card, handwritten note, etc.).
It may contain OCR artifacts such as:
- Character substitutions (digits for letters: "f1our" -> "flour", "sa1t" -> "salt", "0nion" -> "onion")
- Coordinate noise or bounding-box numbers from OCR engines (ignore any stray numbers not part of the recipe)
- Irregular line breaks, merged words, or split words across lines
- Garbled text, repeated characters, or missing spaces
- Headers, footers, page numbers, or watermarks mixed in

Do your best to interpret and correct these OCR errors to produce clean, accurate recipes.

Multi-recipe detection:
- If the OCR text contains MULTIPLE DISTINCT recipes (e.g. a cookbook facing-page spread, two recipe cards side-by-side, a three-panel layout), emit EACH as a separate object in the "recipes" array.
- A recipe is "distinct" when it has its own title AND its own ingredient list. Emit them in the order they read top-to-bottom, left-to-right.
- A "Variation", "Substitution Notes", "Make-Ahead Tips", or "Serving Suggestions" subsection is NOT a distinct recipe — it belongs to the preceding recipe (fold notes into that recipe's description or ignore).
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
            "steps": [
                {{"instruction": "Preheat oven to 350F.", "order": 1}},
                {{"instruction": "Mix dry ingredients in a large bowl.", "order": 2}},
                {{"instruction": "Bake for 25 minutes.", "order": 3}}
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
        }}
    ]
}}

Ingredient rules — CRITICAL: quantity, unit, and text are rendered together downstream as "<quantity> <unit> <text>". Do NOT duplicate information across these fields or the UI will show things like "9 tbsp 9 tbsp butter".

- "quantity": a number ONLY. Convert fractions ("1/2" -> 0.5, "1 1/2" -> 1.5). Use null when the source has no numeric quantity ("a pinch", "to taste", "Salt"). Never include the unit or the ingredient name here.
{unit_rule(freeform_fallback=_FREEFORM_UNIT_RULE)}
- "name": the canonical ingredient name with quantity, unit, AND preparation notes stripped off. Use the most generic form: "onion" not "diced yellow onion", "flour" or "all-purpose flour" not "2 cup sifted flour".
- "notes": preparation or state qualifiers that do not belong in the name ("chopped", "minced", "sauteed", "room temperature", "divided", "to taste", "optional"). null if none.
- "text": the ingredient DESCRIPTION as it should appear next to the quantity and unit — i.e. the ingredient with prep/state qualifiers kept in natural order, but with the numeric quantity AND the unit STRIPPED OFF. Think of it as "what you'd say after reading the amount aloud." Never begins with a number or a unit. If the source line has no quantity/unit to strip (e.g. "Salt"), use the whole line.
- "is_optional": true only if the recipe explicitly marks the ingredient as optional.

Worked examples (source line -> extracted fields):
- "9 tablespoons butter" ->
    {{"text": "butter", "quantity": 9, "unit": "tbsp", "name": "butter", "notes": null, "is_optional": false}}
- "3 tablespoons minced shallots" ->
    {{"text": "minced shallots", "quantity": 3, "unit": "tbsp", "name": "shallots", "notes": "minced", "is_optional": false}}
- "1 cup roasted butternut squash puree" ->
    {{"text": "roasted butternut squash puree", "quantity": 1, "unit": "cup", "name": "butternut squash puree", "notes": "roasted", "is_optional": false}}
- "1/2 cup diced onion, sauteed" ->
    {{"text": "diced onion, sauteed", "quantity": 0.5, "unit": "cup", "name": "onion", "notes": "diced, sauteed", "is_optional": false}}
- "3 tablespoons grated Parmesan-Reggiano cheese, plus 2 ounces" ->
    {{"text": "grated Parmesan-Reggiano cheese, plus 2 oz", "quantity": 3, "unit": "tbsp", "name": "Parmesan-Reggiano cheese", "notes": "grated, plus 2 oz", "is_optional": false}}
- "Pinch nutmeg" ->
    {{"text": "nutmeg", "quantity": null, "unit": "pinch", "name": "nutmeg", "notes": null, "is_optional": false}}
- "Salt" ->
    {{"text": "salt", "quantity": null, "unit": null, "name": "salt", "notes": null, "is_optional": false}}
- "3 large eggs" ->
    {{"text": "large eggs", "quantity": 3, "unit": null, "name": "eggs", "notes": "large", "is_optional": false}}
- "12 fresh sage leaves" ->
    {{"text": "fresh sage leaves", "quantity": 12, "unit": null, "name": "sage leaves", "notes": "fresh", "is_optional": false}}

BAD examples — do NOT produce these:
- {{"text": "9 tbsp butter", "quantity": 9, "unit": "tbsp", ...}}    # text repeats quantity+unit
- {{"text": "tbsp butter", "quantity": 9, "unit": "tbsp", ...}}      # text repeats unit
- {{"quantity": "9 tbsp", "unit": "tbsp", ...}}                      # quantity is not a number

Vibe assignment:
- Choose a primary_vibe that best captures the dish's character
- Choose a secondary_vibe only if a second vibe clearly applies; otherwise set to null
- Valid vibes: light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming

General rules:
- Only include fields you can actually find or reasonably infer from the text
- Set missing fields to null rather than guessing
- If you cannot find recipe content at all, return {{"error": "No recipe found"}}
- Return ONLY valid JSON. No markdown fences, no explanation text.

{confidence_rule()}

OCR Text:
"""


# Backward-compat alias — `TEXT_EXTRACTION_PROMPT` was a string before riip-3.
# Kept for any test that imports it directly.
TEXT_EXTRACTION_PROMPT = _text_extraction_prompt()


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
                    "content": _text_extraction_prompt() + cleaned_text,
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

        recipes = _parse_recipes_payload(data)
        if not recipes:
            return ExtractionResult(
                success=False,
                error_message="No recipes found in AI response",
                error_code="AI_NO_RECIPE_FOUND",
                extractor_used="text_ai",
                ai_cost_cents=cost_cents,
            )

        return ExtractionResult(
            success=True,
            recipes=recipes,
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


def _parse_recipes_payload(data: dict) -> list[ExtractedRecipe]:
    """Parse the AI response into a list of ExtractedRecipe.

    Accepts both the new multi-recipe shape (`{"recipes": [...]}`) and
    the legacy bare-recipe shape (a recipe object at the top level). A
    bare object is silently wrapped in a length-1 list; this keeps the
    pipeline working when the model ignores the new instruction.
    """
    raw_list = data.get("recipes")
    if isinstance(raw_list, list):
        return [
            _parse_response(item)
            for item in raw_list
            if isinstance(item, dict)
        ]
    logger.warning(
        "text_extractor: model returned bare recipe instead of {'recipes': [...]}; wrapping"
    )
    return [_parse_response(data)]


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

    recipe = ExtractedRecipe(
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
    score, source = resolve_confidence(data, recipe)
    recipe.confidence_score = score
    recipe.confidence_source = source
    return recipe
