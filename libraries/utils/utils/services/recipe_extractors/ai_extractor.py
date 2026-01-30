"""AI-based recipe extractor using OpenAI."""

import json
import logging
import re
from typing import Any

from utils.services.recipe_extractors.base import (
    BaseExtractor,
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens for gpt-4o-mini (input + output averaged)
GPT4O_MINI_COST_PER_1K_TOKENS = 0.00015  # $0.00015 per 1K tokens average


EXTRACTION_PROMPT = """Extract the recipe from the following HTML content and return it as JSON.

Return a JSON object with the following structure:
{
    "name": "Recipe name",
    "description": "Brief description",
    "ingredients": [
        {"text": "2 cups all-purpose flour", "quantity": 2, "unit": "cups", "name": "all-purpose flour"}
    ],
    "instructions": "Step-by-step instructions as a single string",
    "servings": 4,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "image_url": "https://example.com/image.jpg",
    "author": "Author name",
    "cuisine": "Italian",
    "category": "Main Course"
}

Rules:
- Only include fields you can find in the content
- For ingredients, always include the full "text" field with the original text
- Parse quantity as a number (e.g., "1/2" should be 0.5)
- Parse unit and ingredient name separately when possible
- If you cannot find recipe content, return {"error": "No recipe found"}

HTML Content:
"""


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
                        "content": EXTRACTION_PROMPT + cleaned_html,
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

            # Parse into ExtractedRecipe
            recipe = self._parse_ai_response(data, url)

            return ExtractionResult(
                success=True,
                recipe=recipe,
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
            source_url=url,
            author=data.get("author"),
            cuisine=data.get("cuisine"),
            category=data.get("category"),
            keywords=data.get("keywords", []),
            raw_data=data,
        )
