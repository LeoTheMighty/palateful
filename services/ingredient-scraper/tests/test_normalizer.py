"""Tests for the ingredient normalizer."""

import pytest

from src.pipeline.normalizer import IngredientNormalizer
from src.models import ScrapedIngredient


class TestIngredientNormalizer:
    """Tests for IngredientNormalizer."""

    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance."""
        return IngredientNormalizer()

    def test_lowercase(self, normalizer):
        """Test that names are lowercased."""
        assert normalizer.normalize_name("CHICKEN") == "chicken"
        assert normalizer.normalize_name("Tomato") == "tomato"

    def test_remove_qualifiers(self, normalizer):
        """Test removal of cooking qualifiers."""
        assert normalizer.normalize_name("chicken raw") == "chicken"
        assert normalizer.normalize_name("cooked beef") == "beef"
        assert normalizer.normalize_name("fresh tomatoes") == "tomato"
        assert normalizer.normalize_name("organic spinach") == "spinach"

    def test_spelling_variations(self, normalizer):
        """Test standardization of spelling variations."""
        assert normalizer.normalize_name("yoghurt") == "yogurt"
        assert normalizer.normalize_name("aubergine") == "eggplant"
        assert normalizer.normalize_name("courgette") == "zucchini"
        assert normalizer.normalize_name("coriander leaves") == "cilantro"
        assert normalizer.normalize_name("rocket") == "arugula"

    def test_singularization(self, normalizer):
        """Test singularization of plural names."""
        assert normalizer.normalize_name("tomatoes") == "tomato"
        assert normalizer.normalize_name("potatoes") == "potato"
        assert normalizer.normalize_name("green beans") == "green bean"
        assert normalizer.normalize_name("apples") == "apple"

    def test_no_singularize_exceptions(self, normalizer):
        """Test that certain words are not singularized."""
        assert normalizer.normalize_name("hummus") == "hummus"
        assert normalizer.normalize_name("couscous") == "couscous"
        assert normalizer.normalize_name("asparagus") == "asparagus"
        assert normalizer.normalize_name("quinoa") == "quinoa"

    def test_remove_parentheticals(self, normalizer):
        """Test removal of parenthetical content."""
        assert normalizer.normalize_name("chicken (raw)") == "chicken"
        assert normalizer.normalize_name("tomatoes [canned]") == "tomato"

    def test_normalize_whitespace(self, normalizer):
        """Test whitespace normalization."""
        assert normalizer.normalize_name("  chicken   breast  ") == "chicken breast"

    def test_empty_and_short(self, normalizer):
        """Test handling of empty and very short names."""
        assert normalizer.normalize_name("") == ""
        assert normalizer.normalize_name("a") == "a"

    def test_normalize_ingredient(self, normalizer):
        """Test normalizing a full ingredient object."""
        ing = ScrapedIngredient(
            canonical_name="Fresh Tomatoes",
            source="test",
            aliases=["Roma Tomatoes", "Cherry Tomatoes"],
        )

        normalized = normalizer.normalize_ingredient(ing)

        assert normalized.canonical_name == "tomato"
        assert "roma tomato" in normalized.aliases
        assert "cherry tomato" in normalized.aliases

    def test_normalize_list(self, normalizer):
        """Test normalizing a list of ingredients."""
        ingredients = [
            ScrapedIngredient(canonical_name="Tomatoes", source="test"),
            ScrapedIngredient(canonical_name="ONION", source="test"),
            ScrapedIngredient(canonical_name="fresh garlic", source="test"),
        ]

        normalized = normalizer.normalize(ingredients)

        assert len(normalized) == 3
        names = [ing.canonical_name for ing in normalized]
        assert "tomato" in names
        assert "onion" in names
        assert "garlic" in names
