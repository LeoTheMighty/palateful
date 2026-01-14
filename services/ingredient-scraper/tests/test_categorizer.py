"""Tests for the ingredient categorizer."""

import pytest

from src.pipeline.categorizer import IngredientCategorizer
from src.models import ScrapedIngredient, IngredientCategory


class TestIngredientCategorizer:
    """Tests for IngredientCategorizer."""

    @pytest.fixture
    def categorizer(self):
        """Create a categorizer instance."""
        return IngredientCategorizer()

    def test_protein_poultry(self, categorizer):
        """Test categorization of poultry."""
        assert categorizer.infer_category("chicken breast") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("turkey") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("duck") == IngredientCategory.PROTEIN

    def test_protein_beef(self, categorizer):
        """Test categorization of beef."""
        assert categorizer.infer_category("ground beef") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("steak") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("beef brisket") == IngredientCategory.PROTEIN

    def test_protein_pork(self, categorizer):
        """Test categorization of pork."""
        assert categorizer.infer_category("bacon") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("ham") == IngredientCategory.PROTEIN
        assert categorizer.infer_category("pork chop") == IngredientCategory.PROTEIN

    def test_seafood(self, categorizer):
        """Test categorization of seafood."""
        assert categorizer.infer_category("salmon") == IngredientCategory.SEAFOOD
        assert categorizer.infer_category("shrimp") == IngredientCategory.SEAFOOD
        assert categorizer.infer_category("tuna") == IngredientCategory.SEAFOOD
        assert categorizer.infer_category("lobster") == IngredientCategory.SEAFOOD

    def test_dairy(self, categorizer):
        """Test categorization of dairy."""
        assert categorizer.infer_category("milk") == IngredientCategory.DAIRY
        assert categorizer.infer_category("cheddar cheese") == IngredientCategory.DAIRY
        assert categorizer.infer_category("butter") == IngredientCategory.DAIRY
        assert categorizer.infer_category("yogurt") == IngredientCategory.DAIRY

    def test_produce_vegetables(self, categorizer):
        """Test categorization of vegetables."""
        assert categorizer.infer_category("carrot") == IngredientCategory.PRODUCE
        assert categorizer.infer_category("broccoli") == IngredientCategory.PRODUCE
        assert categorizer.infer_category("spinach") == IngredientCategory.PRODUCE
        assert categorizer.infer_category("tomato") == IngredientCategory.PRODUCE

    def test_produce_fruits(self, categorizer):
        """Test categorization of fruits."""
        assert categorizer.infer_category("apple") == IngredientCategory.PRODUCE
        assert categorizer.infer_category("banana") == IngredientCategory.PRODUCE
        assert categorizer.infer_category("strawberry") == IngredientCategory.PRODUCE

    def test_herbs_spices(self, categorizer):
        """Test categorization of herbs and spices."""
        assert categorizer.infer_category("basil") == IngredientCategory.HERBS_SPICES
        assert categorizer.infer_category("cumin") == IngredientCategory.HERBS_SPICES
        assert categorizer.infer_category("oregano") == IngredientCategory.HERBS_SPICES
        assert categorizer.infer_category("cinnamon") == IngredientCategory.HERBS_SPICES

    def test_grains(self, categorizer):
        """Test categorization of grains."""
        assert categorizer.infer_category("rice") == IngredientCategory.GRAINS
        assert categorizer.infer_category("pasta") == IngredientCategory.GRAINS
        assert categorizer.infer_category("bread") == IngredientCategory.GRAINS
        assert categorizer.infer_category("all-purpose flour") == IngredientCategory.GRAINS

    def test_legumes(self, categorizer):
        """Test categorization of legumes."""
        assert categorizer.infer_category("black bean") == IngredientCategory.LEGUMES
        assert categorizer.infer_category("lentil") == IngredientCategory.LEGUMES
        assert categorizer.infer_category("chickpea") == IngredientCategory.LEGUMES

    def test_nuts_seeds(self, categorizer):
        """Test categorization of nuts and seeds."""
        assert categorizer.infer_category("almond") == IngredientCategory.NUTS_SEEDS
        assert categorizer.infer_category("walnut") == IngredientCategory.NUTS_SEEDS
        assert categorizer.infer_category("sesame") == IngredientCategory.NUTS_SEEDS
        assert categorizer.infer_category("peanut butter") == IngredientCategory.NUTS_SEEDS

    def test_oils_fats(self, categorizer):
        """Test categorization of oils and fats."""
        assert categorizer.infer_category("olive oil") == IngredientCategory.OILS_FATS
        assert categorizer.infer_category("vegetable oil") == IngredientCategory.OILS_FATS
        assert categorizer.infer_category("coconut oil") == IngredientCategory.OILS_FATS

    def test_sweeteners(self, categorizer):
        """Test categorization of sweeteners."""
        assert categorizer.infer_category("sugar") == IngredientCategory.SWEETENERS
        assert categorizer.infer_category("honey") == IngredientCategory.SWEETENERS
        assert categorizer.infer_category("maple syrup") == IngredientCategory.SWEETENERS

    def test_condiments(self, categorizer):
        """Test categorization of condiments."""
        assert categorizer.infer_category("soy sauce") == IngredientCategory.CONDIMENTS
        assert categorizer.infer_category("ketchup") == IngredientCategory.CONDIMENTS
        assert categorizer.infer_category("mustard") == IngredientCategory.CONDIMENTS

    def test_baking(self, categorizer):
        """Test categorization of baking items."""
        assert categorizer.infer_category("baking powder") == IngredientCategory.BAKING
        assert categorizer.infer_category("vanilla extract") == IngredientCategory.BAKING
        assert categorizer.infer_category("cocoa powder") == IngredientCategory.BAKING

    def test_unknown(self, categorizer):
        """Test that unknown items return None."""
        assert categorizer.infer_category("xyzabc123") is None

    def test_categorize_list(self, categorizer):
        """Test categorizing a list of ingredients."""
        ingredients = [
            ScrapedIngredient(canonical_name="chicken", source="test"),
            ScrapedIngredient(canonical_name="tomato", source="test"),
            ScrapedIngredient(canonical_name="unknown_item", source="test"),
        ]

        categorized = categorizer.categorize(ingredients)

        assert categorized[0].category == "protein"
        assert categorized[1].category == "produce"
        assert categorized[2].category is None

    def test_skip_already_categorized(self, categorizer):
        """Test that already categorized items are not changed."""
        ingredients = [
            ScrapedIngredient(
                canonical_name="chicken", source="test", category="custom_category"
            ),
        ]

        categorized = categorizer.categorize(ingredients)

        # Should keep the existing category
        assert categorized[0].category == "custom_category"

    def test_category_stats(self, categorizer):
        """Test generating category statistics."""
        ingredients = [
            ScrapedIngredient(canonical_name="chicken", source="test", category="protein"),
            ScrapedIngredient(canonical_name="beef", source="test", category="protein"),
            ScrapedIngredient(canonical_name="tomato", source="test", category="produce"),
            ScrapedIngredient(canonical_name="mystery", source="test"),
        ]

        stats = categorizer.get_category_stats(ingredients)

        assert stats["protein"] == 2
        assert stats["produce"] == 1
        assert stats["uncategorized"] == 1
