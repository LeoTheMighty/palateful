"""TheMealDB scraper for curated ingredient list with images.

API Documentation: https://www.themealdb.com/api.php
No API key required for basic access.
"""

from rich.console import Console

from .base import BaseScraper
from ..models import ScrapedIngredient

console = Console()


class TheMealDBScraper(BaseScraper):
    """Scraper for TheMealDB ingredient database.

    TheMealDB provides a curated list of ~500 cooking ingredients with:
    - Ingredient name
    - Description
    - Image URL

    No API key required.
    """

    SOURCE_NAME = "themealdb"
    BASE_URL = "https://www.themealdb.com/api/json/v1/1"

    # Image URL template
    IMAGE_URL_TEMPLATE = "https://www.themealdb.com/images/ingredients/{name}.png"
    IMAGE_URL_SMALL_TEMPLATE = "https://www.themealdb.com/images/ingredients/{name}-Small.png"

    async def scrape(self, limit: int | None = None) -> list[ScrapedIngredient]:
        """Scrape all ingredients from TheMealDB.

        Args:
            limit: Maximum number of ingredients to return

        Returns:
            List of scraped ingredients
        """
        console.print(f"[bold blue]Scraping TheMealDB...[/bold blue]")

        # Fetch the ingredient list
        url = f"{self.BASE_URL}/list.php"
        data = await self._fetch(url, params={"i": "list"})

        meals_list = data.get("meals", [])
        if not meals_list:
            console.print("[yellow]No ingredients found in TheMealDB[/yellow]")
            return []

        console.print(f"[green]Found {len(meals_list)} ingredients[/green]")

        ingredients: list[ScrapedIngredient] = []

        for item in meals_list:
            if limit and len(ingredients) >= limit:
                break

            ingredient = self._parse_ingredient(item)
            if ingredient:
                ingredients.append(ingredient)

        console.print(f"[green]Scraped {len(ingredients)} ingredients from TheMealDB[/green]")
        return ingredients

    def _parse_ingredient(self, data: dict) -> ScrapedIngredient | None:
        """Parse a TheMealDB ingredient response into a ScrapedIngredient.

        Args:
            data: Raw ingredient data from API

        Returns:
            Parsed ingredient or None if invalid
        """
        name = data.get("strIngredient")
        if not name:
            return None

        # Clean the name
        canonical_name = name.strip().lower()

        # Get description if available
        description = data.get("strDescription")
        if description:
            description = description.strip()
            # Some descriptions are just "null" string
            if description.lower() == "null":
                description = None

        # Build image URL
        # TheMealDB uses the original name (with spaces) for image URLs
        image_url = self.IMAGE_URL_TEMPLATE.format(name=name.replace(" ", "%20"))

        # Try to infer category from the name or description
        category = self._infer_category(canonical_name, description)

        return ScrapedIngredient(
            canonical_name=canonical_name,
            source=self.SOURCE_NAME,
            source_id=data.get("idIngredient"),
            description=description,
            image_url=image_url,
            category=category,
            is_canonical=True,
            pending_review=False,
        )

    def _infer_category(self, name: str, description: str | None) -> str | None:
        """Try to infer category from ingredient name and description.

        Args:
            name: Ingredient name (lowercase)
            description: Ingredient description

        Returns:
            Inferred category or None
        """
        name_lower = name.lower()
        desc_lower = (description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Protein indicators
        protein_keywords = [
            "chicken", "beef", "pork", "lamb", "turkey", "duck", "goose",
            "fish", "salmon", "tuna", "cod", "tilapia", "trout", "bass",
            "shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop",
            "bacon", "ham", "sausage", "mince", "steak", "fillet",
            "tofu", "tempeh", "seitan",
        ]
        for keyword in protein_keywords:
            if keyword in name_lower:
                if keyword in ["fish", "salmon", "tuna", "cod", "tilapia", "trout", "bass",
                              "shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop"]:
                    return "seafood"
                return "protein"

        # Dairy indicators
        dairy_keywords = [
            "milk", "cream", "cheese", "butter", "yogurt", "yoghurt",
            "creme", "mascarpone", "ricotta", "mozzarella", "parmesan",
            "cheddar", "feta", "brie", "camembert", "gouda",
        ]
        for keyword in dairy_keywords:
            if keyword in name_lower:
                return "dairy"

        # Produce - vegetables
        vegetable_keywords = [
            "lettuce", "spinach", "kale", "cabbage", "broccoli", "cauliflower",
            "carrot", "potato", "onion", "garlic", "celery", "cucumber",
            "tomato", "pepper", "zucchini", "squash", "eggplant", "aubergine",
            "mushroom", "asparagus", "artichoke", "leek", "shallot",
            "beetroot", "turnip", "radish", "parsnip", "swede",
        ]
        for keyword in vegetable_keywords:
            if keyword in name_lower:
                return "produce"

        # Produce - fruits
        fruit_keywords = [
            "apple", "banana", "orange", "lemon", "lime", "grapefruit",
            "strawberry", "blueberry", "raspberry", "blackberry", "cherry",
            "peach", "plum", "apricot", "nectarine", "mango", "pineapple",
            "watermelon", "melon", "grape", "kiwi", "papaya", "coconut",
            "avocado", "fig", "date", "raisin", "prune", "cranberry",
        ]
        for keyword in fruit_keywords:
            if keyword in name_lower:
                return "produce"

        # Herbs and spices
        herb_spice_keywords = [
            "basil", "oregano", "thyme", "rosemary", "sage", "parsley",
            "cilantro", "coriander", "mint", "dill", "chive", "tarragon",
            "bay leaf", "cumin", "paprika", "turmeric", "cinnamon", "nutmeg",
            "ginger", "clove", "cardamom", "saffron", "curry", "chili",
            "pepper", "cayenne", "mustard seed", "fennel seed", "caraway",
        ]
        for keyword in herb_spice_keywords:
            if keyword in name_lower:
                return "herbs_spices"

        # Grains
        grain_keywords = [
            "rice", "pasta", "noodle", "bread", "flour", "oat", "wheat",
            "barley", "quinoa", "couscous", "bulgur", "corn", "polenta",
            "tortilla", "pita", "naan", "ramen", "udon", "soba",
        ]
        for keyword in grain_keywords:
            if keyword in name_lower:
                return "grains"

        # Legumes
        legume_keywords = [
            "bean", "lentil", "chickpea", "pea", "edamame", "hummus",
        ]
        for keyword in legume_keywords:
            if keyword in name_lower:
                return "legumes"

        # Oils and fats
        oil_keywords = [
            "oil", "ghee", "lard", "shortening", "margarine",
        ]
        for keyword in oil_keywords:
            if keyword in name_lower:
                return "oils_fats"

        # Sweeteners
        sweetener_keywords = [
            "sugar", "honey", "maple", "syrup", "molasses", "agave",
        ]
        for keyword in sweetener_keywords:
            if keyword in name_lower:
                return "sweeteners"

        # Baking
        baking_keywords = [
            "yeast", "baking powder", "baking soda", "vanilla extract",
            "cocoa", "chocolate", "gelatin",
        ]
        for keyword in baking_keywords:
            if keyword in name_lower:
                return "baking"

        # Condiments
        condiment_keywords = [
            "sauce", "ketchup", "mayonnaise", "mustard", "vinegar",
            "soy sauce", "worcestershire", "hot sauce", "salsa",
        ]
        for keyword in condiment_keywords:
            if keyword in name_lower:
                return "condiments"

        # Nuts and seeds
        nut_keywords = [
            "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut",
            "peanut", "macadamia", "pine nut", "chestnut",
            "sesame", "sunflower", "pumpkin seed", "flax", "chia",
        ]
        for keyword in nut_keywords:
            if keyword in name_lower:
                return "nuts_seeds"

        # Check description for category hints
        if "spice" in desc_lower or "herb" in desc_lower:
            return "herbs_spices"
        if "vegetable" in desc_lower:
            return "produce"
        if "fruit" in desc_lower:
            return "produce"
        if "meat" in desc_lower:
            return "protein"
        if "dairy" in desc_lower or "milk" in desc_lower:
            return "dairy"

        return None
