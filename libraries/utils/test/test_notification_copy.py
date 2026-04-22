"""Unit tests for `notification_copy` — the central title/body library."""

from utils.services.notification_copy import import_needs_review, recipe_added


class TestImportNeedsReview:
    def test_single_with_recipe_name(self):
        title, body = import_needs_review(
            recipe_name="Sweet Potato Quiche", count=1
        )
        assert "Sweet Potato Quiche" in title
        assert "ready" in title.lower()
        assert "🍳" in title
        assert body == "Tap to confirm the details we extracted."

    def test_single_with_no_recipe_name(self):
        title, body = import_needs_review(recipe_name=None, count=1)
        assert title == "Your recipe is ready to review"
        assert body == "Tap to confirm the details we extracted."

    def test_single_with_empty_string_name_falls_back(self):
        title, _ = import_needs_review(recipe_name="", count=1)
        # Empty string is falsy → uses fallback.
        assert title == "Your recipe is ready to review"

    def test_bulk_uses_count_only(self):
        title, body = import_needs_review(recipe_name="Ignored", count=5)
        assert title == "Your bulk import is ready"
        assert body == "5 recipes need a quick review."

    def test_bulk_default_count_is_1_so_singular(self):
        title, _ = import_needs_review(recipe_name=None)
        # default count=1 → singular variant
        assert title == "Your recipe is ready to review"


class TestRecipeAdded:
    def test_basic(self):
        title, body = recipe_added(
            actor_name="Sarah",
            recipe_name="Banana Bread",
            book_name="Weeknight Dinners",
        )
        assert "Weeknight Dinners" in title
        assert "🍳" in title
        assert body == "Sarah added Banana Bread"

    def test_unicode_in_recipe_name(self):
        title, body = recipe_added(
            actor_name="Léa",
            recipe_name="Crêpes",
            book_name="Brunch 🥞",
        )
        assert "Brunch 🥞" in title
        assert body == "Léa added Crêpes"
