"""Data models for scraped ingredients.

These models map directly to the database Ingredient model for easy CSV export/import.
See: libraries/utils/utils/models/ingredient.py

CSV columns match the database schema:
- canonical_name (str, unique, required)
- aliases (JSON array as string)
- category (str, nullable)
- flavor_profile (JSON array as string)
- default_unit (str, nullable)
- is_canonical (bool, default True)
- pending_review (bool, default False)
- image_url (str, nullable)
- embedding (JSON array as string, 384 floats)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import csv
import json
from io import StringIO


class IngredientCategory(str, Enum):
    """Top-level ingredient categories matching the database."""

    PRODUCE = "produce"
    PROTEIN = "protein"
    DAIRY = "dairy"
    PANTRY = "pantry"
    HERBS_SPICES = "herbs_spices"
    CONDIMENTS = "condiments"
    BEVERAGES = "beverages"
    GRAINS = "grains"
    LEGUMES = "legumes"
    NUTS_SEEDS = "nuts_seeds"
    OILS_FATS = "oils_fats"
    SWEETENERS = "sweeteners"
    SEAFOOD = "seafood"
    BAKING = "baking"
    OTHER = "other"


class SubstitutionContext(str, Enum):
    """Context for when a substitution is appropriate."""

    BAKING = "baking"
    COOKING = "cooking"
    RAW = "raw"
    ANY = "any"


class SubstitutionQuality(str, Enum):
    """Quality rating for substitutions."""

    PERFECT = "perfect"
    GOOD = "good"
    WORKABLE = "workable"


# CSV column headers that map to the Ingredient database model
INGREDIENT_CSV_COLUMNS = [
    "canonical_name",
    "aliases",
    "category",
    "flavor_profile",
    "default_unit",
    "is_canonical",
    "pending_review",
    "image_url",
    "embedding",
]

SUBSTITUTION_CSV_COLUMNS = [
    "ingredient",
    "substitute",
    "context",
    "quality",
    "ratio",
    "notes",
]


@dataclass
class ScrapedIngredient:
    """An ingredient scraped from an external source.

    Maps directly to the database Ingredient model fields.
    """

    # Required field - must be unique in database
    canonical_name: str

    # Scraping metadata (not stored in DB, used for tracking)
    source: str = "manual"
    source_id: str | None = None

    # Database fields
    aliases: list[str] = field(default_factory=list)
    category: str | None = None
    flavor_profile: list[str] = field(default_factory=list)
    default_unit: str | None = None
    is_canonical: bool = True
    pending_review: bool = False
    image_url: str | None = None
    embedding: list[float] | None = None

    # Extra metadata (not in DB, but useful for processing)
    description: str | None = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)

    def to_csv_row(self) -> dict[str, str]:
        """Convert to a CSV row dict matching the database Ingredient model."""
        return {
            "canonical_name": self.canonical_name,
            "aliases": json.dumps(self.aliases) if self.aliases else "[]",
            "category": self.category or "",
            "flavor_profile": json.dumps(self.flavor_profile) if self.flavor_profile else "[]",
            "default_unit": self.default_unit or "",
            "is_canonical": str(self.is_canonical).lower(),
            "pending_review": str(self.pending_review).lower(),
            "image_url": self.image_url or "",
            "embedding": json.dumps(self.embedding) if self.embedding else "",
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "ScrapedIngredient":
        """Create from a CSV row dict."""
        aliases = json.loads(row.get("aliases", "[]")) if row.get("aliases") else []
        flavor_profile = json.loads(row.get("flavor_profile", "[]")) if row.get("flavor_profile") else []
        embedding = json.loads(row.get("embedding")) if row.get("embedding") else None

        return cls(
            canonical_name=row["canonical_name"],
            aliases=aliases,
            category=row.get("category") or None,
            flavor_profile=flavor_profile,
            default_unit=row.get("default_unit") or None,
            is_canonical=row.get("is_canonical", "true").lower() == "true",
            pending_review=row.get("pending_review", "false").lower() == "true",
            image_url=row.get("image_url") or None,
            embedding=embedding,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "canonical_name": self.canonical_name,
            "source": self.source,
            "source_id": self.source_id,
            "aliases": self.aliases,
            "category": self.category,
            "flavor_profile": self.flavor_profile,
            "default_unit": self.default_unit,
            "is_canonical": self.is_canonical,
            "pending_review": self.pending_review,
            "image_url": self.image_url,
            "embedding": self.embedding,
            "description": self.description,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScrapedIngredient":
        """Create from dictionary."""
        scraped_at = data.get("scraped_at")
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at)
        elif scraped_at is None:
            scraped_at = datetime.utcnow()

        return cls(
            canonical_name=data["canonical_name"],
            source=data.get("source", "manual"),
            source_id=data.get("source_id"),
            aliases=data.get("aliases", []),
            category=data.get("category"),
            flavor_profile=data.get("flavor_profile", []),
            default_unit=data.get("default_unit"),
            is_canonical=data.get("is_canonical", True),
            pending_review=data.get("pending_review", False),
            image_url=data.get("image_url"),
            embedding=data.get("embedding"),
            description=data.get("description"),
            scraped_at=scraped_at,
        )

    def merge_with(self, other: "ScrapedIngredient") -> "ScrapedIngredient":
        """Merge another ingredient's data into this one, preferring non-null values."""
        merged_aliases = list(set(self.aliases + other.aliases))
        merged_flavors = list(set(self.flavor_profile + other.flavor_profile))

        return ScrapedIngredient(
            canonical_name=self.canonical_name,
            source=f"{self.source},{other.source}",
            source_id=self.source_id or other.source_id,
            aliases=merged_aliases,
            category=self.category or other.category,
            flavor_profile=merged_flavors,
            default_unit=self.default_unit or other.default_unit,
            is_canonical=self.is_canonical,
            pending_review=self.pending_review and other.pending_review,
            image_url=self.image_url or other.image_url,
            embedding=self.embedding or other.embedding,
            description=self.description or other.description,
            scraped_at=min(self.scraped_at, other.scraped_at),
        )


@dataclass
class Substitution:
    """A substitution relationship between ingredients.

    Maps to the IngredientSubstitution database model.
    """

    ingredient: str  # canonical_name of the original ingredient
    substitute: str  # canonical_name of the substitute
    context: SubstitutionContext = SubstitutionContext.ANY
    quality: SubstitutionQuality = SubstitutionQuality.GOOD
    ratio: float = 1.0
    notes: str | None = None

    def to_csv_row(self) -> dict[str, str]:
        """Convert to a CSV row dict."""
        return {
            "ingredient": self.ingredient,
            "substitute": self.substitute,
            "context": self.context.value,
            "quality": self.quality.value,
            "ratio": str(self.ratio),
            "notes": self.notes or "",
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "Substitution":
        """Create from a CSV row dict."""
        return cls(
            ingredient=row["ingredient"],
            substitute=row["substitute"],
            context=SubstitutionContext(row.get("context", "any")),
            quality=SubstitutionQuality(row.get("quality", "good")),
            ratio=float(row.get("ratio", 1.0)),
            notes=row.get("notes") or None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ingredient": self.ingredient,
            "substitute": self.substitute,
            "context": self.context.value,
            "quality": self.quality.value,
            "ratio": self.ratio,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Substitution":
        """Create from dictionary."""
        return cls(
            ingredient=data["ingredient"],
            substitute=data["substitute"],
            context=SubstitutionContext(data.get("context", "any")),
            quality=SubstitutionQuality(data.get("quality", "good")),
            ratio=data.get("ratio", 1.0),
            notes=data.get("notes"),
        )


@dataclass
class NutritionInfo:
    """Nutrition information per 100g (for enrichment, not stored in main DB)."""

    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    fiber: float | None = None
    sugar: float | None = None
    sodium: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dictionary."""
        return {
            "calories": self.calories,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
            "fiber": self.fiber,
            "sugar": self.sugar,
            "sodium": self.sodium,
        }
