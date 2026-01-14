"""Ingredient name normalization pipeline.

Handles:
- Lowercasing
- Removing qualifiers (raw, cooked, fresh, etc.)
- Singularizing plurals
- Standardizing spelling variations
"""

import re

import inflect
from rich.console import Console

from ..models import ScrapedIngredient

console = Console()

# Initialize inflect engine for singularization
_inflect_engine = inflect.engine()


# Common qualifiers to remove from ingredient names
REMOVE_QUALIFIERS = [
    # Cooking states
    "raw", "cooked", "roasted", "baked", "fried", "grilled", "boiled",
    "steamed", "sauteed", "sautéed", "braised", "poached", "smoked",
    "cured", "pickled", "fermented", "marinated",
    # Freshness/processing
    "fresh", "frozen", "canned", "dried", "dehydrated", "freeze-dried",
    "preserved", "jarred", "bottled",
    # Preparation
    "chopped", "diced", "minced", "sliced", "shredded", "grated",
    "crushed", "ground", "whole", "halved", "quartered",
    "peeled", "unpeeled", "pitted", "unpitted", "seeded", "seedless",
    # Quality
    "organic", "natural", "pure", "premium", "select", "choice",
    "grade a", "grade b", "extra", "fine", "coarse",
    # Other
    "unsalted", "salted", "sweetened", "unsweetened",
    "reduced fat", "low fat", "fat free", "nonfat", "skim",
    "reduced sodium", "low sodium", "no salt added",
]

# Spelling variations to standardize
SPELLING_VARIATIONS = {
    "yoghurt": "yogurt",
    "colour": "color",
    "flavour": "flavor",
    "grey": "gray",
    "centre": "center",
    "fibre": "fiber",
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "coriander leaves": "cilantro",
    "coriander": "cilantro",  # when referring to leaves
    "rocket": "arugula",
    "capsicum": "bell pepper",
    "prawns": "shrimp",
    "minced meat": "ground meat",
    "mince": "ground meat",
    "spring onion": "green onion",
    "scallion": "green onion",
    "maize": "corn",
    "sweetcorn": "corn",
    "bicarbonate of soda": "baking soda",
    "bicarb": "baking soda",
    "icing sugar": "powdered sugar",
    "confectioners sugar": "powdered sugar",
    "caster sugar": "superfine sugar",
    "plain flour": "all-purpose flour",
    "self raising flour": "self-rising flour",
    "wholemeal": "whole wheat",
    "wholewheat": "whole wheat",
    "double cream": "heavy cream",
    "single cream": "light cream",
    "streaky bacon": "bacon",
    "back bacon": "canadian bacon",
    "gammon": "ham",
    "broad beans": "fava beans",
    "haricot beans": "navy beans",
    "mangetout": "snow peas",
    "swede": "rutabaga",
    "beetroot": "beet",
}

# Words that should not be singularized
NO_SINGULARIZE = {
    "hummus", "couscous", "asparagus", "molasses", "swiss", "series",
    "species", "quinoa", "pasta", "feta", "ricotta", "polenta",
    "gnocchi", "panko", "miso", "tofu", "tempeh", "seitan",
    "tahini", "harissa", "sriracha", "kimchi", "sauerkraut",
}


class IngredientNormalizer:
    """Normalizes ingredient names for consistency."""

    def __init__(self):
        self.inflect = _inflect_engine

    def normalize(self, ingredients: list[ScrapedIngredient]) -> list[ScrapedIngredient]:
        """Normalize a list of ingredients.

        Args:
            ingredients: List of ingredients to normalize

        Returns:
            List of normalized ingredients
        """
        console.print(f"[bold blue]Normalizing {len(ingredients)} ingredients...[/bold blue]")

        normalized = []
        for ing in ingredients:
            normalized_ing = self.normalize_ingredient(ing)
            if normalized_ing:
                normalized.append(normalized_ing)

        console.print(f"[green]Normalized to {len(normalized)} ingredients[/green]")
        return normalized

    def normalize_ingredient(self, ingredient: ScrapedIngredient) -> ScrapedIngredient | None:
        """Normalize a single ingredient.

        Args:
            ingredient: The ingredient to normalize

        Returns:
            Normalized ingredient or None if invalid
        """
        # Normalize the canonical name
        canonical = self.normalize_name(ingredient.canonical_name)
        if not canonical or len(canonical) < 2:
            return None

        # Normalize aliases
        normalized_aliases = []
        for alias in ingredient.aliases:
            norm_alias = self.normalize_name(alias)
            if norm_alias and norm_alias != canonical and len(norm_alias) >= 2:
                normalized_aliases.append(norm_alias)

        # Remove duplicate aliases
        normalized_aliases = list(set(normalized_aliases))

        # Create normalized ingredient
        return ScrapedIngredient(
            canonical_name=canonical,
            source=ingredient.source,
            source_id=ingredient.source_id,
            aliases=normalized_aliases,
            category=ingredient.category,
            flavor_profile=ingredient.flavor_profile,
            default_unit=ingredient.default_unit,
            is_canonical=ingredient.is_canonical,
            pending_review=ingredient.pending_review,
            image_url=ingredient.image_url,
            embedding=ingredient.embedding,
            description=ingredient.description,
            scraped_at=ingredient.scraped_at,
        )

    def normalize_name(self, name: str) -> str:
        """Normalize an ingredient name.

        Args:
            name: Raw ingredient name

        Returns:
            Normalized name
        """
        if not name:
            return ""

        # Lowercase
        name = name.lower().strip()

        # Apply spelling variations
        for variant, standard in SPELLING_VARIATIONS.items():
            # Use word boundaries to avoid partial matches
            pattern = rf"\b{re.escape(variant)}\b"
            name = re.sub(pattern, standard, name)

        # Remove parenthetical content
        name = re.sub(r"\([^)]*\)", "", name)
        name = re.sub(r"\[[^\]]*\]", "", name)

        # Remove qualifiers
        for qualifier in REMOVE_QUALIFIERS:
            # Match as whole word
            pattern = rf"\b{re.escape(qualifier)}\b"
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        # Remove common punctuation
        name = re.sub(r"[,;:\-–—]", " ", name)

        # Normalize whitespace
        name = " ".join(name.split())

        # Singularize
        name = self.singularize(name)

        return name.strip()

    def singularize(self, name: str) -> str:
        """Convert plural ingredient name to singular.

        Args:
            name: Ingredient name (may be plural)

        Returns:
            Singular form
        """
        # Check if it's in our no-singularize list
        if name.lower() in NO_SINGULARIZE:
            return name

        # Handle compound names (e.g., "green beans" -> "green bean")
        words = name.split()
        if len(words) > 1:
            # Only singularize the last word
            last_word = words[-1]
            if last_word.lower() not in NO_SINGULARIZE:
                singular = self.inflect.singular_noun(last_word)
                if singular and singular != last_word:
                    words[-1] = singular
            return " ".join(words)

        # Single word
        singular = self.inflect.singular_noun(name)
        if singular and singular != name:
            return singular

        return name
