"""Recipe extractors for importing recipes from various sources."""

import logging
from typing import Any

import httpx

from utils.services.recipe_extractors.ai_extractor import AIExtractor
from utils.services.recipe_extractors.base import (
    BaseExtractor,
    ExtractedIngredient,
    ExtractedRecipe,
    ExtractionResult,
)
from utils.services.recipe_extractors.json_ld import JsonLdExtractor

logger = logging.getLogger(__name__)

__all__ = [
    "BaseExtractor",
    "ExtractedIngredient",
    "ExtractedRecipe",
    "ExtractionResult",
    "JsonLdExtractor",
    "AIExtractor",
    "RecipeExtractorRegistry",
    "extract_recipe_from_url",
    "extract_recipe_from_html",
]


class RecipeExtractorRegistry:
    """Registry of recipe extractors with tiered extraction."""

    def __init__(self, openai_client: Any = None):
        """Initialize the registry with default extractors.

        Args:
            openai_client: Optional OpenAI client for AI extraction.
        """
        self._extractors: list[BaseExtractor] = [
            JsonLdExtractor(),
            # Add more extractors here in priority order
            # e.g., MicrodataExtractor(), SiteSpecificExtractor()
        ]
        self._ai_extractor = AIExtractor(openai_client)

    def add_extractor(self, extractor: BaseExtractor, priority: int | None = None):
        """Add an extractor to the registry.

        Args:
            extractor: The extractor to add.
            priority: Optional priority (lower = higher priority). If None, adds at end.
        """
        if priority is not None and priority < len(self._extractors):
            self._extractors.insert(priority, extractor)
        else:
            self._extractors.append(extractor)

    def extract(
        self,
        html_content: str,
        url: str | None = None,
        use_ai_fallback: bool = True,
    ) -> ExtractionResult:
        """Extract recipe using tiered approach.

        Tries each extractor in order until one succeeds.
        Falls back to AI extraction if all free extractors fail.

        Args:
            html_content: The HTML content to extract from.
            url: Optional URL of the page.
            use_ai_fallback: Whether to use AI extraction as fallback.

        Returns:
            ExtractionResult with the extracted recipe or error information.
        """
        # Try free extractors first
        for extractor in self._extractors:
            if extractor.can_extract(html_content, url):
                logger.info("Attempting extraction with %s", extractor.name)
                result = extractor.extract(html_content, url)
                if result.success:
                    logger.info("Successfully extracted recipe with %s", extractor.name)
                    return result
                logger.debug(
                    "Extractor %s failed: %s",
                    extractor.name,
                    result.error_message,
                )

        # Fall back to AI extraction
        if use_ai_fallback and self._ai_extractor.can_extract(html_content, url):
            logger.info("Falling back to AI extraction")
            return self._ai_extractor.extract(html_content, url)

        return ExtractionResult(
            success=False,
            error_message="No extractor could extract recipe from content",
            error_code="NO_EXTRACTOR_SUCCEEDED",
        )


# Default registry instance
_default_registry = None


def get_default_registry(openai_client: Any = None) -> RecipeExtractorRegistry:
    """Get the default extractor registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = RecipeExtractorRegistry(openai_client)
    return _default_registry


async def fetch_url_content(url: str, timeout: float = 30.0) -> str:
    """Fetch HTML content from a URL.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        HTML content as string.

    Raises:
        httpx.HTTPError: If the request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Palateful/1.0; +https://palateful.app)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


async def extract_recipe_from_url(
    url: str,
    use_ai_fallback: bool = True,
    openai_client: Any = None,
) -> ExtractionResult:
    """Extract recipe from a URL.

    This is the main entry point for URL-based recipe extraction.
    It fetches the URL content and runs it through the extractor pipeline.

    Args:
        url: The recipe URL to extract from.
        use_ai_fallback: Whether to use AI extraction as fallback.
        openai_client: Optional OpenAI client for AI extraction.

    Returns:
        ExtractionResult with the extracted recipe or error information.
    """
    try:
        html_content = await fetch_url_content(url)
    except httpx.HTTPError as e:
        logger.exception("Failed to fetch URL: %s", url)
        return ExtractionResult(
            success=False,
            error_message=f"Failed to fetch URL: {e}",
            error_code="URL_FETCH_ERROR",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching URL: %s", url)
        return ExtractionResult(
            success=False,
            error_message=f"Unexpected error: {e}",
            error_code="URL_FETCH_ERROR",
        )

    return extract_recipe_from_html(
        html_content,
        url=url,
        use_ai_fallback=use_ai_fallback,
        openai_client=openai_client,
    )


def extract_recipe_from_html(
    html_content: str,
    url: str | None = None,
    use_ai_fallback: bool = True,
    openai_client: Any = None,
) -> ExtractionResult:
    """Extract recipe from HTML content.

    Args:
        html_content: The HTML content to extract from.
        url: Optional URL of the page.
        use_ai_fallback: Whether to use AI extraction as fallback.
        openai_client: Optional OpenAI client for AI extraction.

    Returns:
        ExtractionResult with the extracted recipe or error information.
    """
    registry = get_default_registry(openai_client)
    return registry.extract(html_content, url, use_ai_fallback)
