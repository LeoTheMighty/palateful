"""Store section configuration and utilities."""

from typing import Literal

# Standard store sections in typical grocery store order
STORE_SECTIONS = [
    ("produce", "Produce", 1),
    ("bakery", "Bakery", 2),
    ("deli", "Deli & Prepared Foods", 3),
    ("meat", "Meat & Poultry", 4),
    ("seafood", "Seafood", 5),
    ("dairy", "Dairy & Eggs", 6),
    ("frozen", "Frozen Foods", 7),
    ("canned", "Canned & Jarred", 8),
    ("pasta", "Pasta & Grains", 9),
    ("baking", "Baking & Spices", 10),
    ("condiments", "Condiments & Sauces", 11),
    ("snacks", "Snacks & Chips", 12),
    ("beverages", "Beverages", 13),
    ("breakfast", "Breakfast & Cereal", 14),
    ("international", "International Foods", 15),
    ("health", "Health & Beauty", 16),
    ("household", "Household & Cleaning", 17),
    ("other", "Other", 99),
]

SECTION_ORDER = {section[0]: section[2] for section in STORE_SECTIONS}
SECTION_NAMES = {section[0]: section[1] for section in STORE_SECTIONS}

StoreSectionType = Literal[
    "produce",
    "bakery",
    "deli",
    "meat",
    "seafood",
    "dairy",
    "frozen",
    "canned",
    "pasta",
    "baking",
    "condiments",
    "snacks",
    "beverages",
    "breakfast",
    "international",
    "health",
    "household",
    "other",
]


# Category to section mapping for auto-assignment
CATEGORY_TO_SECTION: dict[str, StoreSectionType] = {
    # Produce
    "fruit": "produce",
    "fruits": "produce",
    "vegetable": "produce",
    "vegetables": "produce",
    "produce": "produce",
    "herbs": "produce",
    "fresh herbs": "produce",
    "salad": "produce",
    "greens": "produce",
    # Bakery
    "bread": "bakery",
    "bakery": "bakery",
    "baked goods": "bakery",
    "pastry": "bakery",
    "tortillas": "bakery",
    # Meat
    "meat": "meat",
    "poultry": "meat",
    "chicken": "meat",
    "beef": "meat",
    "pork": "meat",
    "lamb": "meat",
    "ground meat": "meat",
    # Seafood
    "seafood": "seafood",
    "fish": "seafood",
    "shellfish": "seafood",
    "shrimp": "seafood",
    # Dairy
    "dairy": "dairy",
    "milk": "dairy",
    "cheese": "dairy",
    "eggs": "dairy",
    "yogurt": "dairy",
    "butter": "dairy",
    "cream": "dairy",
    # Frozen
    "frozen": "frozen",
    "frozen vegetables": "frozen",
    "frozen fruit": "frozen",
    "ice cream": "frozen",
    # Canned/Jarred
    "canned": "canned",
    "canned goods": "canned",
    "canned vegetables": "canned",
    "canned fruit": "canned",
    "tomato": "canned",
    "beans": "canned",
    "legumes": "canned",
    # Pasta/Grains
    "pasta": "pasta",
    "grains": "pasta",
    "rice": "pasta",
    "noodles": "pasta",
    "quinoa": "pasta",
    # Baking/Spices
    "baking": "baking",
    "spices": "baking",
    "seasonings": "baking",
    "flour": "baking",
    "sugar": "baking",
    "baking supplies": "baking",
    # Condiments
    "condiments": "condiments",
    "sauces": "condiments",
    "dressing": "condiments",
    "oil": "condiments",
    "vinegar": "condiments",
    "mayo": "condiments",
    "ketchup": "condiments",
    "mustard": "condiments",
    # Snacks
    "snacks": "snacks",
    "chips": "snacks",
    "crackers": "snacks",
    "nuts": "snacks",
    "candy": "snacks",
    # Beverages
    "beverages": "beverages",
    "drinks": "beverages",
    "juice": "beverages",
    "soda": "beverages",
    "water": "beverages",
    "coffee": "beverages",
    "tea": "beverages",
    # Breakfast
    "breakfast": "breakfast",
    "cereal": "breakfast",
    "oatmeal": "breakfast",
    "pancake": "breakfast",
    # International
    "international": "international",
    "asian": "international",
    "mexican": "international",
    "italian": "international",
    "indian": "international",
    # Health/Beauty
    "health": "health",
    "vitamins": "health",
    "supplements": "health",
    "personal care": "health",
    # Household
    "household": "household",
    "cleaning": "household",
    "paper goods": "household",
    "laundry": "household",
}


def get_section_for_category(category: str | None) -> StoreSectionType:
    """Get the store section for a given category.

    Args:
        category: The item category (e.g., "vegetables", "dairy")

    Returns:
        The store section key
    """
    if not category:
        return "other"

    normalized = category.lower().strip()
    return CATEGORY_TO_SECTION.get(normalized, "other")


def get_section_order(section: str | None) -> int:
    """Get the sort order for a store section.

    Args:
        section: The store section key

    Returns:
        Sort order (lower = earlier in store)
    """
    if not section:
        return 99
    return SECTION_ORDER.get(section.lower(), 99)


def get_section_display_name(section: str | None) -> str:
    """Get the display name for a store section.

    Args:
        section: The store section key

    Returns:
        Human-readable section name
    """
    if not section:
        return "Other"
    return SECTION_NAMES.get(section.lower(), section.title())
