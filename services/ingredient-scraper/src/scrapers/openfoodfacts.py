"""Open Food Facts scraper for supplementary ingredient data.

API Documentation: https://wiki.openfoodfacts.org/API
No API key required.

Note: Open Food Facts is primarily a product database, not an ingredient database.
We use it to supplement ingredient data by searching for simple, unprocessed foods.
"""

from rich.console import Console

from .base import BaseScraper
from ..models import ScrapedIngredient

console = Console()


# Categories to search for base ingredients
SEARCH_CATEGORIES = [
    "en:fresh-fruits",
    "en:fresh-vegetables",
    "en:herbs",
    "en:spices",
    "en:fresh-meats",
    "en:fresh-fish",
    "en:eggs",
    "en:milks",
    "en:cheeses",
    "en:butters",
    "en:cooking-oils",
    "en:flours",
    "en:rices",
    "en:pastas",
    "en:dried-legumes",
    "en:nuts",
    "en:seeds",
    "en:honeys",
    "en:sugars",
    "en:vinegars",
]

# Map OFF categories to our categories
OFF_CATEGORY_MAP = {
    "en:fresh-fruits": "produce",
    "en:fresh-vegetables": "produce",
    "en:herbs": "herbs_spices",
    "en:spices": "herbs_spices",
    "en:fresh-meats": "protein",
    "en:fresh-fish": "seafood",
    "en:eggs": "protein",
    "en:milks": "dairy",
    "en:cheeses": "dairy",
    "en:butters": "dairy",
    "en:cooking-oils": "oils_fats",
    "en:flours": "grains",
    "en:rices": "grains",
    "en:pastas": "grains",
    "en:dried-legumes": "legumes",
    "en:nuts": "nuts_seeds",
    "en:seeds": "nuts_seeds",
    "en:honeys": "sweeteners",
    "en:sugars": "sweeteners",
    "en:vinegars": "condiments",
}


class OpenFoodFactsScraper(BaseScraper):
    """Scraper for Open Food Facts.

    Used to supplement ingredient data from other sources.
    Focuses on unprocessed/simple foods.
    """

    SOURCE_NAME = "openfoodfacts"
    BASE_URL = "https://world.openfoodfacts.org/api/v2"

    def __init__(self, **kwargs):
        # OFF recommends max 10 requests per minute for unauthenticated access
        kwargs.setdefault("rate_limit", 0.15)  # ~9 requests per minute
        super().__init__(**kwargs)

    async def scrape(self, limit: int | None = None) -> list[ScrapedIngredient]:
        """Scrape ingredients from Open Food Facts.

        Args:
            limit: Maximum number of ingredients to return

        Returns:
            List of scraped ingredients
        """
        console.print(f"[bold blue]Scraping Open Food Facts...[/bold blue]")

        all_ingredients: list[ScrapedIngredient] = []
        seen_names: set[str] = set()

        # Calculate per-category limit
        per_category_limit = (limit // len(SEARCH_CATEGORIES) + 1) if limit else 50

        for category_tag in SEARCH_CATEGORIES:
            if limit and len(all_ingredients) >= limit:
                break

            console.print(f"[cyan]Searching category: {category_tag}[/cyan]")

            try:
                ingredients = await self._search_category(
                    category_tag,
                    limit=per_category_limit,
                    seen_names=seen_names,
                )
                all_ingredients.extend(ingredients)

                # Track seen names to avoid duplicates
                for ing in ingredients:
                    seen_names.add(ing.canonical_name)

                console.print(f"[dim]  Found {len(ingredients)} ingredients[/dim]")

            except Exception as e:
                console.print(f"[yellow]Error searching {category_tag}: {e}[/yellow]")
                continue

        console.print(f"[green]Scraped {len(all_ingredients)} ingredients from OFF[/green]")
        return all_ingredients

    async def _search_category(
        self,
        category_tag: str,
        limit: int = 50,
        seen_names: set[str] | None = None,
    ) -> list[ScrapedIngredient]:
        """Search a specific category for ingredients.

        Args:
            category_tag: The OFF category tag to search
            limit: Maximum results
            seen_names: Set of names already seen (to skip duplicates)

        Returns:
            List of ingredients
        """
        seen_names = seen_names or set()
        ingredients: list[ScrapedIngredient] = []

        url = f"{self.BASE_URL}/search"
        params = {
            "categories_tags": category_tag,
            "fields": "code,product_name,generic_name,categories_tags,image_url",
            "page_size": min(limit * 2, 100),  # Fetch extra since we filter
            "page": 1,
        }

        try:
            data = await self._fetch(url, params=params)
        except Exception as e:
            console.print(f"[red]API error: {e}[/red]")
            return []

        products = data.get("products", [])

        for product in products:
            if len(ingredients) >= limit:
                break

            ingredient = self._parse_product(product, category_tag)

            if ingredient and ingredient.canonical_name not in seen_names:
                ingredients.append(ingredient)

        return ingredients

    def _parse_product(self, product: dict, search_category: str) -> ScrapedIngredient | None:
        """Parse an OFF product into a ScrapedIngredient.

        Args:
            product: Raw product data
            search_category: The category we searched for

        Returns:
            Parsed ingredient or None if not suitable
        """
        # Prefer generic_name (e.g., "whole milk") over product_name (brand name)
        name = product.get("generic_name") or product.get("product_name")
        if not name:
            return None

        # Skip if name is too long (probably a branded product description)
        if len(name) > 50:
            return None

        # Skip if name contains brand indicators
        skip_indicators = ["®", "™", "brand", "company", "inc.", "ltd."]
        name_lower = name.lower()
        if any(indicator in name_lower for indicator in skip_indicators):
            return None

        # Clean the name
        canonical_name = self._clean_name(name)
        if not canonical_name or len(canonical_name) < 2:
            return None

        # Get category from our map
        category = OFF_CATEGORY_MAP.get(search_category)

        # Get image URL
        image_url = product.get("image_url")

        return ScrapedIngredient(
            canonical_name=canonical_name,
            source=self.SOURCE_NAME,
            source_id=product.get("code"),
            category=category,
            image_url=image_url,
            is_canonical=True,
            pending_review=False,
        )

    def _clean_name(self, name: str) -> str:
        """Clean a product name into a canonical ingredient name.

        Args:
            name: Raw product name

        Returns:
            Cleaned canonical name
        """
        # Lowercase
        name = name.lower().strip()

        # Remove common suffixes/prefixes
        remove_patterns = [
            "organic ", "bio ", "natural ", "fresh ",
            "premium ", "select ", "choice ",
            " - ", " | ",
        ]
        for pattern in remove_patterns:
            name = name.replace(pattern, " ")

        # Remove parenthetical content
        import re
        name = re.sub(r"\([^)]*\)", "", name)
        name = re.sub(r"\[[^\]]*\]", "", name)

        # Normalize whitespace
        name = " ".join(name.split())

        return name.strip()
