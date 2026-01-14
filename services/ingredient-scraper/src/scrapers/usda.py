"""USDA FoodData Central scraper for comprehensive food database.

API Documentation: https://fdc.nal.usda.gov/api-guide.html
Requires API key from: https://fdc.nal.usda.gov/api-key-signup.html

Data types:
- Foundation: ~2,000 foods with extensive nutrient data
- SR Legacy: ~8,000 standard reference foods
- Survey (FNDDS): ~8,000 foods from dietary surveys
- Branded: ~400,000 branded food products (skip these)
"""

from rich.console import Console

from .base import BaseScraper
from ..config import settings
from ..models import ScrapedIngredient

console = Console()


# USDA food category mapping to our categories
USDA_CATEGORY_MAP = {
    # Dairy and Egg Products
    "Dairy and Egg Products": "dairy",
    # Spices and Herbs
    "Spices and Herbs": "herbs_spices",
    # Baby Foods - skip
    "Baby Foods": None,
    # Fats and Oils
    "Fats and Oils": "oils_fats",
    # Poultry Products
    "Poultry Products": "protein",
    # Soups, Sauces, and Gravies
    "Soups, Sauces, and Gravies": "condiments",
    # Sausages and Luncheon Meats
    "Sausages and Luncheon Meats": "protein",
    # Breakfast Cereals
    "Breakfast Cereals": "grains",
    # Fruits and Fruit Juices
    "Fruits and Fruit Juices": "produce",
    # Pork Products
    "Pork Products": "protein",
    # Vegetables and Vegetable Products
    "Vegetables and Vegetable Products": "produce",
    # Nut and Seed Products
    "Nut and Seed Products": "nuts_seeds",
    # Beef Products
    "Beef Products": "protein",
    # Beverages
    "Beverages": "beverages",
    # Finfish and Shellfish Products
    "Finfish and Shellfish Products": "seafood",
    # Legumes and Legume Products
    "Legumes and Legume Products": "legumes",
    # Lamb, Veal, and Game Products
    "Lamb, Veal, and Game Products": "protein",
    # Baked Products
    "Baked Products": "baking",
    # Sweets
    "Sweets": "sweeteners",
    # Cereal Grains and Pasta
    "Cereal Grains and Pasta": "grains",
    # Fast Foods - skip
    "Fast Foods": None,
    # Meals, Entrees, and Side Dishes - skip
    "Meals, Entrees, and Side Dishes": None,
    # Snacks
    "Snacks": "pantry",
    # American Indian/Alaska Native Foods - skip
    "American Indian/Alaska Native Foods": None,
    # Restaurant Foods - skip
    "Restaurant Foods": None,
}


class USDAFoodDataScraper(BaseScraper):
    """Scraper for USDA FoodData Central.

    Focuses on Foundation and SR Legacy data types which contain
    basic ingredients rather than branded/processed foods.
    """

    SOURCE_NAME = "usda"
    BASE_URL = "https://api.nal.usda.gov/fdc/v1"

    # Data types to fetch (Foundation has best data, SR Legacy is comprehensive)
    TARGET_DATA_TYPES = ["Foundation", "SR Legacy"]

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or settings.usda_api_key

        if not self.api_key:
            console.print(
                "[yellow]Warning: No USDA API key provided. "
                "Get one at https://fdc.nal.usda.gov/api-key-signup.html[/yellow]"
            )

    async def scrape(self, limit: int | None = None) -> list[ScrapedIngredient]:
        """Scrape ingredients from USDA FoodData Central.

        Args:
            limit: Maximum number of ingredients to return

        Returns:
            List of scraped ingredients
        """
        if not self.api_key:
            console.print("[red]Cannot scrape USDA without API key[/red]")
            return []

        console.print(f"[bold blue]Scraping USDA FoodData Central...[/bold blue]")

        all_ingredients: list[ScrapedIngredient] = []

        for data_type in self.TARGET_DATA_TYPES:
            if limit and len(all_ingredients) >= limit:
                break

            console.print(f"[cyan]Fetching {data_type} foods...[/cyan]")

            remaining = limit - len(all_ingredients) if limit else None
            ingredients = await self._scrape_data_type(data_type, limit=remaining)
            all_ingredients.extend(ingredients)

            console.print(f"[green]Got {len(ingredients)} from {data_type}[/green]")

        console.print(f"[green]Scraped {len(all_ingredients)} total ingredients from USDA[/green]")
        return all_ingredients

    async def _scrape_data_type(
        self, data_type: str, limit: int | None = None
    ) -> list[ScrapedIngredient]:
        """Scrape a specific data type from USDA.

        Args:
            data_type: The USDA data type (Foundation, SR Legacy, etc.)
            limit: Maximum number of ingredients

        Returns:
            List of scraped ingredients
        """
        url = f"{self.BASE_URL}/foods/list"
        page_size = 200  # Max allowed by USDA API
        page = 1
        ingredients: list[ScrapedIngredient] = []

        while True:
            if limit and len(ingredients) >= limit:
                break

            params = {
                "api_key": self.api_key,
                "dataType": [data_type],
                "pageSize": page_size,
                "pageNumber": page,
            }

            try:
                data = await self._fetch(url, params=params)
            except Exception as e:
                console.print(f"[red]Error fetching page {page}: {e}[/red]")
                break

            if not data:
                break

            for food in data:
                if limit and len(ingredients) >= limit:
                    break

                ingredient = self._parse_food(food)
                if ingredient:
                    ingredients.append(ingredient)

            console.print(f"[dim]  Page {page}: {len(data)} foods[/dim]")

            if len(data) < page_size:
                break

            page += 1

        return ingredients

    def _parse_food(self, food: dict) -> ScrapedIngredient | None:
        """Parse a USDA food item into a ScrapedIngredient.

        Args:
            food: Raw food data from USDA API

        Returns:
            Parsed ingredient or None if should be skipped
        """
        description = food.get("description", "")
        if not description:
            return None

        # Skip entries that are clearly not base ingredients
        skip_patterns = [
            "baby food",
            "infant formula",
            "fast food",
            "restaurant",
            "mcdonald",
            "burger king",
            "frozen meal",
            "tv dinner",
        ]
        desc_lower = description.lower()
        if any(pattern in desc_lower for pattern in skip_patterns):
            return None

        # Get category
        food_category = food.get("foodCategory", "")
        category = USDA_CATEGORY_MAP.get(food_category)

        # Skip categories we don't want
        if category is None and food_category in USDA_CATEGORY_MAP:
            return None

        # Clean the name
        canonical_name = self._clean_name(description)
        if not canonical_name:
            return None

        # Extract any aliases from the description
        aliases = self._extract_aliases(description, canonical_name)

        # Try to infer default unit based on category
        default_unit = self._infer_default_unit(canonical_name, category)

        return ScrapedIngredient(
            canonical_name=canonical_name,
            source=self.SOURCE_NAME,
            source_id=str(food.get("fdcId")),
            aliases=aliases,
            category=category,
            default_unit=default_unit,
            description=description if description != canonical_name else None,
            is_canonical=True,
            pending_review=False,
        )

    def _clean_name(self, description: str) -> str:
        """Clean a USDA food description into a canonical name.

        USDA descriptions often include qualifiers like:
        - "Chicken, breast, meat only, cooked, roasted"
        - "Apples, raw, with skin"
        - "Cheese, cheddar"

        We want to extract just the base ingredient name.
        """
        # Split by comma and take relevant parts
        parts = [p.strip().lower() for p in description.split(",")]

        if not parts:
            return ""

        # Start with the first part as the base
        name = parts[0]

        # For some categories, include the second part
        if len(parts) > 1:
            second = parts[1].strip()
            # Include variety/type qualifiers
            include_second = [
                "breast", "thigh", "leg", "wing",  # chicken parts
                "ground", "steak", "roast", "chop",  # meat cuts
                "cheddar", "mozzarella", "parmesan", "swiss", "feta",  # cheese types
                "white", "brown", "wild", "basmati", "jasmine",  # rice types
                "all-purpose", "whole wheat", "bread",  # flour types
                "extra virgin", "virgin",  # oil types
            ]
            if any(qual in second.lower() for qual in include_second):
                name = f"{name} {second}"

        # Remove common qualifiers that don't add to the ingredient identity
        remove_suffixes = [
            "raw", "cooked", "roasted", "baked", "fried", "grilled",
            "boiled", "steamed", "fresh", "frozen", "canned", "dried",
            "with skin", "without skin", "meat only", "meat and skin",
            "separable lean and fat", "separable lean only",
        ]
        for suffix in remove_suffixes:
            if name.endswith(f" {suffix}"):
                name = name[: -(len(suffix) + 1)]

        return name.strip()

    def _extract_aliases(self, description: str, canonical_name: str) -> list[str]:
        """Extract potential aliases from the description.

        Args:
            description: Full USDA description
            canonical_name: The cleaned canonical name

        Returns:
            List of aliases
        """
        aliases = []

        # The full description (cleaned) can be an alias if different
        full_clean = description.lower().replace(",", " ").strip()
        full_clean = " ".join(full_clean.split())  # normalize whitespace
        if full_clean != canonical_name and len(full_clean) < 100:
            aliases.append(full_clean)

        return aliases

    def _infer_default_unit(self, name: str, category: str | None) -> str | None:
        """Infer a reasonable default unit for an ingredient.

        Args:
            name: Ingredient name
            category: Ingredient category

        Returns:
            Default unit abbreviation or None
        """
        # Liquids
        if category == "beverages" or category == "oils_fats":
            return "cup"

        # Protein typically by weight
        if category == "protein" or category == "seafood":
            return "lb"

        # Dairy varies
        if category == "dairy":
            if "milk" in name or "cream" in name:
                return "cup"
            if "cheese" in name:
                return "oz"
            if "butter" in name:
                return "tbsp"
            return "cup"

        # Produce by piece or weight
        if category == "produce":
            countable = ["apple", "banana", "orange", "lemon", "lime", "onion",
                        "potato", "tomato", "pepper", "carrot", "egg"]
            if any(c in name for c in countable):
                return "count"
            return "cup"

        # Grains by cup
        if category == "grains":
            return "cup"

        # Herbs/spices by teaspoon
        if category == "herbs_spices":
            return "tsp"

        # Nuts/seeds by cup
        if category == "nuts_seeds":
            return "cup"

        return None
