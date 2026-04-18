"""Base extractor class for recipe extraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedIngredient:
    """Extracted ingredient from a recipe."""

    text: str  # Display string shown next to quantity+unit, e.g. "all-purpose flour, sifted" — must NOT include the quantity or unit
    quantity: float | None = None
    unit: str | None = None
    name: str | None = None  # Canonical ingredient name, stripped of quantity/unit/prep
    notes: str | None = None
    is_optional: bool = False


@dataclass
class ExtractedStep:
    """A single structured recipe step.

    `order` is 1-indexed. `instruction` is the text of the step as the
    user would read it. Additional fields (duration_seconds,
    ingredient_refs, etc.) may be added later without breaking existing
    extractors — all downstream consumers default-handle missing keys.
    """

    order: int
    instruction: str


@dataclass
class ExtractedRecipe:
    """Extracted recipe data."""

    name: str
    description: str | None = None
    ingredients: list[ExtractedIngredient] = field(default_factory=list)
    # Legacy fallback: joined, numbered string. Still populated by every
    # extractor for display purposes and as a safety net when structured
    # steps are unavailable or malformed.
    instructions: str | None = None
    # Structured recipe steps. Populated by extractors that can produce
    # structured output (currently: text_extractor). Extractors that
    # still emit only a joined instructions string leave this as None,
    # and downstream code falls back to parsing `instructions`.
    steps: list[ExtractedStep] | None = None
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    author: str | None = None
    cuisine: str | None = None
    category: str | None = None
    keywords: list[str] = field(default_factory=list)
    primary_vibe: str | None = None
    secondary_vibe: str | None = None
    # irrd-3 — self-reported model score (or heuristic fallback). `None`
    # means "model declined AND heuristic has not yet run"; downstream
    # serialization MUST resolve to a numeric score via
    # `apply_confidence_score()` before persistence so the UI never sees
    # null unless both paths failed.
    confidence_score: float | None = None
    confidence_source: str | None = None  # "model" | "heuristic"
    raw_data: dict = field(default_factory=dict)  # Original structured data


@dataclass
class ExtractionResult:
    """Result of a recipe extraction attempt.

    The canonical shape is `recipes: list[ExtractedRecipe]` — extractors
    may emit multiple recipes from a single source (e.g. a cookbook page
    with two recipes side-by-side). Single-recipe inputs produce a
    length-1 list.

    The `recipe` field is a DEPRECATED alias kept for one cycle to ease
    migration (the eval framework still reads it). Callers should move
    to `recipes`. `__post_init__` keeps the two in sync: setting either
    one populates the other, and both reference the same underlying
    object so mutations propagate.
    """

    success: bool
    recipes: list[ExtractedRecipe] = field(default_factory=list)
    # DEPRECATED: remove in next extractor-touching epic.
    recipe: ExtractedRecipe | None = None
    error_message: str | None = None
    error_code: str | None = None
    extractor_used: str | None = None
    ai_cost_cents: int = 0

    def __post_init__(self):
        if self.recipes:
            if self.recipe is None:
                self.recipe = self.recipes[0]
        elif self.recipe is not None:
            self.recipes = [self.recipe]


def validate_vibe(vibe: str | None) -> str | None:
    """Validate a vibe value against the allowed list."""
    from utils.constants import VALID_VIBES

    if vibe and vibe in VALID_VIBES:
        return vibe
    return None


class BaseExtractor(ABC):
    """Abstract base class for recipe extractors."""

    name: str = "base"

    @abstractmethod
    def can_extract(self, html_content: str, url: str | None = None) -> bool:
        """Check if this extractor can handle the given content.

        Args:
            html_content: The HTML content to check.
            url: Optional URL of the page.

        Returns:
            True if this extractor can handle the content.
        """

    @abstractmethod
    def extract(self, html_content: str, url: str | None = None) -> ExtractionResult:
        """Extract recipe data from the given content.

        Args:
            html_content: The HTML content to extract from.
            url: Optional URL of the page.

        Returns:
            ExtractionResult with the extracted recipe or error information.
        """

    def _parse_duration(self, duration_str: str | None) -> int | None:
        """Parse ISO 8601 duration string to minutes.

        Args:
            duration_str: Duration string like "PT30M" or "PT1H30M".

        Returns:
            Duration in minutes or None if parsing fails.
        """
        if not duration_str:
            return None

        import re

        # Handle ISO 8601 duration format (PT1H30M)
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str.upper())
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 60 + minutes + (1 if seconds > 0 else 0)

        # Try parsing as just a number (assume minutes)
        try:
            return int(duration_str)
        except (ValueError, TypeError):
            return None

    def _clean_text(self, text: Any) -> str | None:
        """Clean and normalize text content.

        Args:
            text: Text to clean.

        Returns:
            Cleaned text or None if empty.
        """
        if text is None:
            return None
        if isinstance(text, list):
            text = " ".join(str(t) for t in text)
        text = str(text).strip()
        return text if text else None

    def _parse_servings(self, servings: Any) -> int | None:
        """Parse servings from various formats.

        Args:
            servings: Servings value.

        Returns:
            Integer servings or None.
        """
        if servings is None:
            return None

        import re

        servings_str = str(servings).strip()

        # Try to extract first number
        match = re.search(r"\d+", servings_str)
        if match:
            return int(match.group())

        return None
