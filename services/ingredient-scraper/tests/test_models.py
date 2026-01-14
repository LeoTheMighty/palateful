"""Tests for data models."""

import json
import pytest
from datetime import datetime

from src.models import (
    ScrapedIngredient,
    Substitution,
    SubstitutionContext,
    SubstitutionQuality,
    INGREDIENT_CSV_COLUMNS,
)


class TestScrapedIngredient:
    """Tests for ScrapedIngredient model."""

    def test_create_minimal(self):
        """Test creating an ingredient with minimal fields."""
        ing = ScrapedIngredient(canonical_name="chicken")
        assert ing.canonical_name == "chicken"
        assert ing.source == "manual"
        assert ing.aliases == []
        assert ing.is_canonical is True
        assert ing.pending_review is False

    def test_create_full(self):
        """Test creating an ingredient with all fields."""
        ing = ScrapedIngredient(
            canonical_name="chicken breast",
            source="usda",
            source_id="12345",
            aliases=["chicken fillet", "boneless chicken"],
            category="protein",
            flavor_profile=["savory", "mild"],
            default_unit="lb",
            image_url="https://example.com/chicken.jpg",
        )
        assert ing.canonical_name == "chicken breast"
        assert ing.source == "usda"
        assert len(ing.aliases) == 2
        assert ing.category == "protein"

    def test_to_csv_row(self):
        """Test converting to CSV row format."""
        ing = ScrapedIngredient(
            canonical_name="tomato",
            aliases=["roma tomato"],
            category="produce",
        )
        row = ing.to_csv_row()

        assert row["canonical_name"] == "tomato"
        assert row["category"] == "produce"
        assert json.loads(row["aliases"]) == ["roma tomato"]
        assert row["is_canonical"] == "true"
        assert all(col in row for col in INGREDIENT_CSV_COLUMNS)

    def test_from_csv_row(self):
        """Test creating from CSV row."""
        row = {
            "canonical_name": "onion",
            "aliases": '["yellow onion", "white onion"]',
            "category": "produce",
            "flavor_profile": '["pungent", "sweet"]',
            "default_unit": "count",
            "is_canonical": "true",
            "pending_review": "false",
            "image_url": "",
            "embedding": "",
        }
        ing = ScrapedIngredient.from_csv_row(row)

        assert ing.canonical_name == "onion"
        assert ing.aliases == ["yellow onion", "white onion"]
        assert ing.flavor_profile == ["pungent", "sweet"]
        assert ing.is_canonical is True

    def test_to_dict(self):
        """Test converting to dictionary."""
        ing = ScrapedIngredient(
            canonical_name="garlic",
            category="produce",
        )
        d = ing.to_dict()

        assert d["canonical_name"] == "garlic"
        assert d["category"] == "produce"
        assert "scraped_at" in d

    def test_from_dict(self):
        """Test creating from dictionary."""
        d = {
            "canonical_name": "basil",
            "source": "themealdb",
            "category": "herbs_spices",
            "aliases": ["sweet basil"],
        }
        ing = ScrapedIngredient.from_dict(d)

        assert ing.canonical_name == "basil"
        assert ing.source == "themealdb"
        assert ing.aliases == ["sweet basil"]

    def test_merge_with(self):
        """Test merging two ingredients."""
        ing1 = ScrapedIngredient(
            canonical_name="chicken",
            source="usda",
            aliases=["poultry"],
            category="protein",
        )
        ing2 = ScrapedIngredient(
            canonical_name="chicken",
            source="themealdb",
            aliases=["chicken meat"],
            image_url="https://example.com/chicken.jpg",
        )

        merged = ing1.merge_with(ing2)

        assert merged.canonical_name == "chicken"
        assert merged.source == "usda,themealdb"
        assert "poultry" in merged.aliases
        assert "chicken meat" in merged.aliases
        assert merged.category == "protein"  # from ing1
        assert merged.image_url == "https://example.com/chicken.jpg"  # from ing2


class TestSubstitution:
    """Tests for Substitution model."""

    def test_create_minimal(self):
        """Test creating a substitution with minimal fields."""
        sub = Substitution(ingredient="butter", substitute="coconut oil")
        assert sub.ingredient == "butter"
        assert sub.substitute == "coconut oil"
        assert sub.context == SubstitutionContext.ANY
        assert sub.quality == SubstitutionQuality.GOOD
        assert sub.ratio == 1.0

    def test_create_full(self):
        """Test creating a substitution with all fields."""
        sub = Substitution(
            ingredient="butter",
            substitute="olive oil",
            context=SubstitutionContext.COOKING,
            quality=SubstitutionQuality.GOOD,
            ratio=0.75,
            notes="Use 75% the amount",
        )
        assert sub.context == SubstitutionContext.COOKING
        assert sub.ratio == 0.75
        assert sub.notes == "Use 75% the amount"

    def test_to_csv_row(self):
        """Test converting to CSV row."""
        sub = Substitution(
            ingredient="milk",
            substitute="oat milk",
            context=SubstitutionContext.BAKING,
            quality=SubstitutionQuality.PERFECT,
        )
        row = sub.to_csv_row()

        assert row["ingredient"] == "milk"
        assert row["substitute"] == "oat milk"
        assert row["context"] == "baking"
        assert row["quality"] == "perfect"

    def test_from_csv_row(self):
        """Test creating from CSV row."""
        row = {
            "ingredient": "eggs",
            "substitute": "flax egg",
            "context": "baking",
            "quality": "workable",
            "ratio": "1.0",
            "notes": "Mix 1 tbsp flax with 3 tbsp water",
        }
        sub = Substitution.from_csv_row(row)

        assert sub.ingredient == "eggs"
        assert sub.substitute == "flax egg"
        assert sub.context == SubstitutionContext.BAKING
        assert sub.quality == SubstitutionQuality.WORKABLE

    def test_to_dict(self):
        """Test converting to dictionary."""
        sub = Substitution(ingredient="cream", substitute="coconut cream")
        d = sub.to_dict()

        assert d["ingredient"] == "cream"
        assert d["substitute"] == "coconut cream"
        assert d["context"] == "any"
