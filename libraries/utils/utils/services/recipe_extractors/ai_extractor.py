"""AI-based recipe extractor using OpenAI."""

import json
import logging
import re
from typing import Any

from utils.services.recipe_extractors.base import (
    BaseExtractor,
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractedStep,
    ExtractionResult,
    validate_vibe,
)
from utils.services.recipe_extractors.confidence_heuristic import resolve_confidence
from utils.services.recipe_extractors.confidence_prompt import confidence_rule
from utils.services.recipe_extractors.inference_prompt import (
    infer_missing_fields,
    inference_rule,
    parse_inferred_fields,
)
from utils.services.recipe_extractors.unit_prompt import unit_rule

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens for gpt-4o-mini (input + output averaged)
GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015  # $0.00015 per 1K tokens average


# Legacy freeform unit instruction kept for the rollback path
# (EXTRACTOR_EMIT_CANONICAL_UNITS=false).
_FREEFORM_UNIT_RULE = (
    '- "unit": the measurement unit ONLY (e.g. "cup", "tablespoon", "pound", '
    '"ounce", "clove", "can"). Use null for count items ("3 large eggs" -> '
    "unit: null) or when there is no unit. Never include the number or name "
    "here."
)


def _extraction_prompt() -> str:
    """riip-3 + efi-2: build the prompt with the canonical-or-freeform unit rule.

    efi-2 splices the field-inference rule in after the confidence rule.
    The top-level ``inferred_fields`` array is added to the JSON skeleton
    always (empty when nothing was inferred), and the "Only include
    fields you can find" rule is scoped to non-inferable fields when the
    flag is on.
    """
    inference_active = infer_missing_fields()
    general_rule = (
        "Only include non-inferable fields you can find in the content "
        "(the Inference Rule above covers handling of inferable fields)"
        if inference_active
        else "Only include fields you can find in the content"
    )
    # Keep the `inferred_fields` JSON skeleton line OUT of the prompt
    # entirely when the flag is off. AC7 specifies that a flag-off
    # prompt must not mention `inferred_fields` at all — otherwise the
    # model is still primed to emit the key even when we told it not to.
    inferred_skeleton = (
        ',\n            "inferred_fields": []' if inference_active else ""
    )
    return f"""Extract every recipe from the following HTML content and return them as JSON.

If the page contains MULTIPLE DISTINCT recipes (with separate titles and separate ingredient lists), emit each as a separate object in the "recipes" array. A "Variation" or "Notes" section is NOT a distinct recipe. If there is only one recipe, return a length-1 array.

Return a JSON object with the following structure:
{{
    "recipes": [
        {{
            "name": "Recipe name",
            "description": "Brief description",
            "ingredients": [
                {{"text": "all-purpose flour, sifted", "quantity": 2, "unit": "cup", "name": "all-purpose flour", "notes": "sifted", "is_optional": false}}
            ],
            "instructions": "Step-by-step instructions as a single string",
            "steps": [
                {{"order": 1, "instruction": "Simmer for 10 minutes, stirring.", "timers": [{{"duration_minutes": 10, "label": "simmer"}}]}}
            ],
            "servings": 4,
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "image_url": "https://example.com/image.jpg",
            "author": "Author name",
            "cuisine": "Italian",
            "category": "Main Course",
            "primary_vibe": "...",
            "secondary_vibe": "..." or null{inferred_skeleton}
        }}
    ]
}}

Vibes: [light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming]

Ingredient rules — CRITICAL: quantity, unit, and text are rendered together downstream as "<quantity> <unit> <text>". Do NOT duplicate information across these fields or the UI will show things like "9 tbsp 9 tbsp butter".

For every ingredient line, always extract `quantity`, `unit`, and `notes` when they appear in the source, even if the quantity is a fraction, a range, or implied by context. Notes capture preparation hints ("minced", "melted", "room temperature", "to taste"). If the source gives a range like "1-2 cups" or "1 to 2 cups", emit `quantity` as the first value and capture the full range in `notes` (e.g. `{{"quantity": 1, "notes": "to 2 cups"}}`). Respect word boundaries for units: "a pinchful" is NOT "pinch" (unit: null).

- "quantity": a number ONLY. Convert fractions ("1/2" -> 0.5, "1 1/2" -> 1.5). Use null for non-numeric amounts ("a pinch", "to taste"). Never include the unit or name here.
{unit_rule(freeform_fallback=_FREEFORM_UNIT_RULE)}
- "name": the canonical ingredient name, stripped of quantity, unit, and prep notes (e.g. "onion" not "diced yellow onion"; "butter" not "9 tbsp butter").
- "notes": preparation/state qualifiers ("minced", "sauteed", "room temperature", "to taste", "divided") or null. Do NOT hallucinate notes — if the source has no qualifier, notes MUST be null.
- "text": the ingredient DESCRIPTION as it should appear next to the quantity and unit. Keep prep qualifiers in natural order, but STRIP the numeric quantity and the unit off the front. Never begins with a number or a unit. If the source has no quantity/unit to strip (e.g. "Salt"), use the whole line.
- "is_optional": true only if the recipe explicitly marks the ingredient as optional.

Worked examples (source line -> extracted fields):
- "9 tablespoons butter" -> {{"text": "butter", "quantity": 9, "unit": "tbsp", "name": "butter", "notes": null, "is_optional": false}}
- "3 tablespoons minced shallots" -> {{"text": "minced shallots", "quantity": 3, "unit": "tbsp", "name": "shallots", "notes": "minced", "is_optional": false}}
- "1/2 cup diced onion" -> {{"text": "diced onion", "quantity": 0.5, "unit": "cup", "name": "onion", "notes": "diced", "is_optional": false}}
- "3 large eggs" -> {{"text": "large eggs", "quantity": 3, "unit": null, "name": "eggs", "notes": "large", "is_optional": false}}
- "Pinch nutmeg" -> {{"text": "nutmeg", "quantity": null, "unit": "pinch", "name": "nutmeg", "notes": null, "is_optional": false}}
- "Salt to taste" -> {{"text": "salt, to taste", "quantity": null, "unit": null, "name": "salt", "notes": "to taste", "is_optional": false}}
- "1 clove garlic, minced" -> {{"text": "garlic, minced", "quantity": 1, "unit": "clove", "name": "garlic", "notes": "minced", "is_optional": false}}
- "2 stalks celery, chopped" -> {{"text": "celery, chopped", "quantity": 2, "unit": "stalk", "name": "celery", "notes": "chopped", "is_optional": false}}
- "300 gram of vinegar" -> {{"text": "vinegar", "quantity": 300, "unit": "g", "name": "vinegar", "notes": null, "is_optional": false}}
- "1-2 cups water" -> {{"text": "water", "quantity": 1, "unit": "cup", "name": "water", "notes": "to 2 cups", "is_optional": false}}
- "a pinchful of salt" -> {{"text": "salt", "quantity": null, "unit": null, "name": "salt", "notes": "pinchful", "is_optional": false}}
- "2 cups flour" -> {{"text": "flour", "quantity": 2, "unit": "cup", "name": "flour", "notes": null, "is_optional": false}}

BAD examples — do NOT produce these:
- {{"text": "9 tbsp butter", "quantity": 9, "unit": "tbsp", ...}}   # text repeats quantity+unit
- {{"text": "tbsp butter", "quantity": 9, "unit": "tbsp", ...}}     # text repeats unit
- {{"quantity": "9 tbsp", ...}}                                     # quantity must be a number

Step rules (cmt-1) — if you can identify discrete steps, prefer emitting `steps` over a joined `instructions` string. When you emit `steps`, it supersedes `instructions` downstream.
- `order`: 1-indexed.
- `instruction`: the step text as the user would read it.
- `timers`: actively-tended durations (simmer N min, bake N min, fry N min, boil N min). Do NOT include passive waits (rest overnight, marinate 4+ hours, cool completely, rise until doubled) — those are NOT timers.
  - POSITIVE: "Simmer for 10 minutes, stirring." -> timers: [{{"duration_minutes": 10, "label": "simmer"}}]
  - NEGATIVE: "Let dough rise overnight." -> timers: []
  - NEGATIVE: "Refrigerate for at least 4 hours." -> timers: []

General rules:
- {general_rule}
- If you cannot find recipe content, return {{"error": "No recipe found"}}

{confidence_rule()}

{inference_rule()}

HTML Content:
"""


# Backward-compat alias — `EXTRACTION_PROMPT` was a string before riip-3.
# Kept for any test that imports it directly.
EXTRACTION_PROMPT = _extraction_prompt()


def _parse_steps_with_timers(raw_steps: Any) -> list[ExtractedStep] | None:
    """cmt-1: parse the LLM's `steps` array into `ExtractedStep` instances.

    Returns ``None`` when the model omitted `steps` (absent key, empty
    list, wrong type, or every entry malformed). That lets downstream
    fall back to the legacy joined `instructions` string.

    Per-entry rules:
      * non-dict entries are dropped silently.
      * blank or missing `instruction` drops the entry.
      * missing `order` is backfilled by 1-indexed position.
      * non-integer `order` is backfilled by position.
      * `timers` must be a list; anything else coerces to `[]`. Invalid
        per-timer entries pass through verbatim — `create_recipe_task`
        does the strict clamp + filter at persist time (cmt-2).
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
        raw_timers = raw.get("timers")
        timers = list(raw_timers) if isinstance(raw_timers, list) else []
        parsed.append(
            ExtractedStep(
                order=order,
                instruction=instruction.strip(),
                timers=timers,
            )
        )
    return parsed or None


class AIExtractor(BaseExtractor):
    """Extracts recipes using OpenAI's gpt-4o-mini model.

    This is the fallback extractor used when structured data extraction fails.
    It costs approximately $0.002 per recipe extraction.
    """

    name = "ai"

    def __init__(self, openai_client: Any = None):
        """Initialize the AI extractor.

        Args:
            openai_client: Optional OpenAI client instance. If not provided,
                          will be created when needed.
        """
        self._client = openai_client

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI()
        return self._client

    def can_extract(self, html_content: str, url: str | None = None) -> bool:
        """AI extractor can always attempt extraction."""
        # Only return True if there's substantial content
        # Strip tags and check text length
        text_content = re.sub(r"<[^>]+>", " ", html_content)
        text_content = re.sub(r"\s+", " ", text_content).strip()
        return len(text_content) > 100

    def extract(self, html_content: str, url: str | None = None) -> ExtractionResult:
        """Extract recipe using OpenAI."""
        try:
            # Clean HTML to reduce token usage
            cleaned_html = self._clean_html(html_content)

            # Truncate if too long (approximately 8K tokens = 32K chars)
            max_chars = 32000
            if len(cleaned_html) > max_chars:
                cleaned_html = cleaned_html[:max_chars] + "..."

            # Call OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a recipe extraction assistant. Extract recipe data from HTML and return valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": _extraction_prompt() + cleaned_html,
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
            # Minimum 1 cent if we made a call
            if total_tokens > 0 and cost_cents == 0:
                cost_cents = 1

            # Parse response
            content = response.choices[0].message.content
            if not content:
                return ExtractionResult(
                    success=False,
                    error_message="Empty response from AI",
                    error_code="AI_EMPTY_RESPONSE",
                    extractor_used=self.name,
                    ai_cost_cents=cost_cents,
                )

            data = json.loads(content)

            # Check for error response
            if "error" in data:
                return ExtractionResult(
                    success=False,
                    error_message=data["error"],
                    error_code="AI_NO_RECIPE_FOUND",
                    extractor_used=self.name,
                    ai_cost_cents=cost_cents,
                )

            recipes = self._parse_recipes_payload(data, url)
            if not recipes:
                return ExtractionResult(
                    success=False,
                    error_message="No recipes found in AI response",
                    error_code="AI_NO_RECIPE_FOUND",
                    extractor_used=self.name,
                    ai_cost_cents=cost_cents,
                )

            return ExtractionResult(
                success=True,
                recipes=recipes,
                extractor_used=self.name,
                ai_cost_cents=cost_cents,
            )

        except json.JSONDecodeError as e:
            logger.exception("Failed to parse AI response as JSON")
            return ExtractionResult(
                success=False,
                error_message=f"Failed to parse AI response: {e}",
                error_code="AI_JSON_PARSE_ERROR",
                extractor_used=self.name,
            )
        except Exception as e:
            logger.exception("Error during AI extraction")
            return ExtractionResult(
                success=False,
                error_message=str(e),
                error_code="AI_EXTRACTION_ERROR",
                extractor_used=self.name,
            )

    def _clean_html(self, html: str) -> str:
        """Clean HTML to reduce token usage.

        Removes scripts, styles, and other non-content elements.
        """
        # Remove script and style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Remove header, footer, nav elements (usually not recipe content)
        html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove excessive whitespace
        html = re.sub(r"\s+", " ", html)

        return html.strip()

    def _parse_recipes_payload(
        self, data: dict, url: str | None = None
    ) -> list[ExtractedRecipe]:
        """Parse the AI response into a list of ExtractedRecipe.

        Accepts both the multi-recipe shape (`{"recipes": [...]}`) and
        the legacy bare-recipe shape. A bare object is wrapped in a
        length-1 list with a warning.
        """
        raw_list = data.get("recipes")
        if isinstance(raw_list, list):
            return [
                self._parse_ai_response(item, url)
                for item in raw_list
                if isinstance(item, dict)
            ]
        logger.warning(
            "ai_extractor: model returned bare recipe instead of {'recipes': [...]}; wrapping"
        )
        return [self._parse_ai_response(data, url)]

    def _parse_ai_response(self, data: dict, url: str | None = None) -> ExtractedRecipe:
        """Parse AI response into ExtractedRecipe."""
        # Parse ingredients
        ingredients = []
        raw_ingredients = data.get("ingredients", [])
        for ing in raw_ingredients:
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
            instructions=data.get("instructions"),
            steps=_parse_steps_with_timers(data.get("steps")),
            servings=data.get("servings"),
            prep_time_minutes=data.get("prep_time_minutes"),
            cook_time_minutes=data.get("cook_time_minutes"),
            total_time_minutes=data.get("total_time_minutes"),
            image_url=data.get("image_url"),
            source_url=url,
            author=data.get("author"),
            cuisine=data.get("cuisine"),
            category=data.get("category"),
            keywords=data.get("keywords", []),
            primary_vibe=validate_vibe(data.get("primary_vibe")),
            secondary_vibe=validate_vibe(data.get("secondary_vibe")),
            inferred_fields=parse_inferred_fields(data.get("inferred_fields")),
            raw_data=data,
        )
        score, source = resolve_confidence(data, recipe)
        recipe.confidence_score = score
        recipe.confidence_source = source
        return recipe
