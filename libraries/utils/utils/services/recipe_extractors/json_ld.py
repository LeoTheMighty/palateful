"""JSON-LD/Schema.org recipe extractor."""

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


class JsonLdExtractor(BaseExtractor):
    """Extracts recipes from JSON-LD Schema.org structured data.

    This is the preferred extraction method as it provides clean, structured data.
    Most modern recipe sites include JSON-LD markup with Schema.org Recipe type.
    """

    name = "json_ld"

    def can_extract(self, html_content: str, url: str | None = None) -> bool:
        """Check if the content contains JSON-LD recipe data."""
        return self._find_recipe_json_ld(html_content) is not None

    def extract(self, html_content: str, url: str | None = None) -> ExtractionResult:
        """Extract recipe from JSON-LD data."""
        try:
            recipe_data = self._find_recipe_json_ld(html_content)
            if not recipe_data:
                return ExtractionResult(
                    success=False,
                    error_message="No JSON-LD recipe data found",
                    error_code="NO_JSON_LD",
                    extractor_used=self.name,
                )

            recipe = self._parse_recipe_data(recipe_data, url)
            return ExtractionResult(
                success=True,
                recipe=recipe,
                extractor_used=self.name,
            )
        except Exception as e:
            logger.exception("Error extracting JSON-LD recipe")
            return ExtractionResult(
                success=False,
                error_message=str(e),
                error_code="JSON_LD_PARSE_ERROR",
                extractor_used=self.name,
            )

    def _find_recipe_json_ld(self, html_content: str) -> dict | None:
        """Find and parse JSON-LD recipe data from HTML.

        Args:
            html_content: The HTML content to search.

        Returns:
            Recipe data dict or None if not found.
        """
        # Find all <script type="application/ld+json"> tags
        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            try:
                data = json.loads(match)
                recipe = self._find_recipe_in_data(data)
                if recipe:
                    return recipe
            except json.JSONDecodeError:
                continue

        return None

    def _find_recipe_in_data(self, data: Any) -> dict | None:
        """Recursively find Recipe object in JSON-LD data.

        Args:
            data: JSON-LD data structure.

        Returns:
            Recipe dict or None.
        """
        if isinstance(data, dict):
            # Check if this is a Recipe
            schema_type = data.get("@type")
            if isinstance(schema_type, list):
                schema_type = schema_type[0] if schema_type else None

            if schema_type == "Recipe":
                return data

            # Check @graph for nested items
            if "@graph" in data:
                for item in data["@graph"]:
                    recipe = self._find_recipe_in_data(item)
                    if recipe:
                        return recipe

            # Recursively search nested objects
            for value in data.values():
                if isinstance(value, dict | list):
                    recipe = self._find_recipe_in_data(value)
                    if recipe:
                        return recipe

        elif isinstance(data, list):
            for item in data:
                recipe = self._find_recipe_in_data(item)
                if recipe:
                    return recipe

        return None

    def _parse_recipe_data(self, data: dict, url: str | None = None) -> ExtractedRecipe:
        """Parse Schema.org Recipe data into ExtractedRecipe.

        Args:
            data: Recipe JSON-LD data.
            url: Source URL.

        Returns:
            ExtractedRecipe object.
        """
        # Parse ingredients
        ingredients = []
        raw_ingredients = data.get("recipeIngredient", [])
        if isinstance(raw_ingredients, str):
            raw_ingredients = [raw_ingredients]

        for ing_text in raw_ingredients:
            if isinstance(ing_text, str) and ing_text.strip():
                ingredients.append(
                    ExtractedIngredient(text=ing_text.strip())
                )

        # Parse instructions
        instructions = self._parse_instructions(data.get("recipeInstructions"))

        # Parse times
        prep_time = self._parse_duration(data.get("prepTime"))
        cook_time = self._parse_duration(data.get("cookTime"))
        total_time = self._parse_duration(data.get("totalTime"))

        # Parse image
        image_url = self._parse_image(data.get("image"))

        # Parse author
        author = self._parse_author(data.get("author"))

        # Parse keywords
        keywords = self._parse_keywords(data.get("keywords"))

        return ExtractedRecipe(
            name=self._clean_text(data.get("name")) or "Untitled Recipe",
            description=self._clean_text(data.get("description")),
            ingredients=ingredients,
            instructions=instructions,
            servings=self._parse_servings(data.get("recipeYield")),
            prep_time_minutes=prep_time,
            cook_time_minutes=cook_time,
            total_time_minutes=total_time,
            image_url=image_url,
            source_url=url,
            author=author,
            cuisine=self._clean_text(data.get("recipeCuisine")),
            category=self._clean_text(data.get("recipeCategory")),
            keywords=keywords,
            raw_data=data,
        )

    def _parse_instructions(self, instructions: Any) -> str | None:
        """Parse instructions from various formats.

        Args:
            instructions: Recipe instructions in Schema.org format.

        Returns:
            Instructions as a single string.
        """
        if not instructions:
            return None

        if isinstance(instructions, str):
            return instructions.strip()

        if isinstance(instructions, list):
            steps = []
            for idx, item in enumerate(instructions, 1):
                if isinstance(item, str):
                    steps.append(f"{idx}. {item.strip()}")
                elif isinstance(item, dict):
                    # HowToStep or HowToSection
                    if item.get("@type") == "HowToSection":
                        section_name = item.get("name", "")
                        if section_name:
                            steps.append(f"\n**{section_name}**")
                        for step in item.get("itemListElement", []):
                            if isinstance(step, dict):
                                text = step.get("text", "")
                                if text:
                                    steps.append(f"{len(steps) + 1}. {text.strip()}")
                    else:
                        text = item.get("text", "")
                        if text:
                            steps.append(f"{idx}. {text.strip()}")

            return "\n".join(steps) if steps else None

        return None

    def _parse_image(self, image: Any) -> str | None:
        """Parse image URL from various formats.

        Args:
            image: Image data.

        Returns:
            Image URL or None.
        """
        if not image:
            return None

        if isinstance(image, str):
            return image

        if isinstance(image, list):
            image = image[0] if image else None
            if isinstance(image, str):
                return image
            if isinstance(image, dict):
                return image.get("url") or image.get("contentUrl")

        if isinstance(image, dict):
            return image.get("url") or image.get("contentUrl")

        return None

    def _parse_author(self, author: Any) -> str | None:
        """Parse author from various formats.

        Args:
            author: Author data.

        Returns:
            Author name or None.
        """
        if not author:
            return None

        if isinstance(author, str):
            return author.strip()

        if isinstance(author, list):
            author = author[0] if author else None

        if isinstance(author, dict):
            return author.get("name")

        return None

    def _parse_keywords(self, keywords: Any) -> list[str]:
        """Parse keywords from various formats.

        Args:
            keywords: Keywords data.

        Returns:
            List of keyword strings.
        """
        if not keywords:
            return []

        if isinstance(keywords, str):
            # Split by comma
            return [k.strip() for k in keywords.split(",") if k.strip()]

        if isinstance(keywords, list):
            return [str(k).strip() for k in keywords if k]

        return []
