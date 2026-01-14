"""Ingredient categorization using rule-based classification.

Assigns categories to ingredients that don't have one yet.
Uses keyword matching and pattern recognition.
"""

import re

from rich.console import Console

from ..models import ScrapedIngredient, IngredientCategory

console = Console()


# Category keyword mappings (order matters - more specific first)
CATEGORY_KEYWORDS = {
    IngredientCategory.SEAFOOD: [
        # Fish
        "salmon", "tuna", "cod", "tilapia", "trout", "bass", "halibut",
        "mackerel", "sardine", "anchovy", "swordfish", "mahi", "snapper",
        "flounder", "sole", "haddock", "perch", "catfish", "herring",
        # Shellfish
        "shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster",
        "scallop", "squid", "calamari", "octopus", "crayfish", "crawfish",
    ],
    IngredientCategory.PROTEIN: [
        # Poultry
        "chicken", "turkey", "duck", "goose", "quail", "pheasant",
        "cornish hen", "poultry",
        # Beef
        "beef", "steak", "brisket", "ribeye", "sirloin", "tenderloin",
        "ground beef", "veal",
        # Pork
        "pork", "bacon", "ham", "prosciutto", "pancetta", "chorizo",
        "sausage", "salami", "pepperoni",
        # Lamb/Game
        "lamb", "mutton", "venison", "bison", "rabbit", "goat",
        # Plant-based protein
        "tofu", "tempeh", "seitan", "tvp", "beyond meat", "impossible",
        # Other
        "egg", "eggs",
    ],
    IngredientCategory.DAIRY: [
        # Milk products
        "milk", "cream", "half and half", "buttermilk", "evaporated milk",
        "condensed milk", "whipping cream", "heavy cream", "sour cream",
        # Cheese
        "cheese", "cheddar", "mozzarella", "parmesan", "swiss", "feta",
        "brie", "camembert", "gouda", "gruyere", "ricotta", "mascarpone",
        "cream cheese", "cottage cheese", "blue cheese", "gorgonzola",
        # Other dairy
        "butter", "ghee", "yogurt", "kefir", "creme fraiche",
    ],
    IngredientCategory.HERBS_SPICES: [
        # Fresh herbs
        "basil", "cilantro", "parsley", "mint", "dill", "chive",
        "tarragon", "oregano", "thyme", "rosemary", "sage", "marjoram",
        "bay leaf", "lemongrass", "chervil",
        # Dried herbs
        "dried basil", "dried oregano", "dried thyme", "herbes de provence",
        "italian seasoning", "bouquet garni",
        # Spices
        "cumin", "coriander", "paprika", "turmeric", "cinnamon", "nutmeg",
        "clove", "cardamom", "ginger", "allspice", "mace", "saffron",
        "cayenne", "chili powder", "curry powder", "garam masala",
        "five spice", "za'atar", "sumac", "fenugreek", "anise", "star anise",
        "fennel seed", "caraway", "mustard seed", "celery seed", "poppy seed",
        # Peppers (spice)
        "black pepper", "white pepper", "pink pepper", "szechuan pepper",
        "peppercorn",
    ],
    IngredientCategory.PRODUCE: [
        # Leafy greens
        "lettuce", "spinach", "kale", "arugula", "chard", "collard",
        "cabbage", "bok choy", "endive", "radicchio", "watercress",
        # Root vegetables
        "carrot", "potato", "sweet potato", "yam", "beet", "turnip",
        "parsnip", "radish", "rutabaga", "celeriac", "jicama",
        # Alliums
        "onion", "garlic", "shallot", "leek", "scallion", "green onion",
        "chive",
        # Nightshades
        "tomato", "pepper", "bell pepper", "eggplant", "tomatillo",
        # Squash
        "zucchini", "squash", "pumpkin", "cucumber", "gourd",
        # Cruciferous
        "broccoli", "cauliflower", "brussels sprout", "kohlrabi",
        # Other vegetables
        "asparagus", "artichoke", "celery", "fennel", "corn", "pea",
        "green bean", "snap pea", "snow pea", "okra", "rhubarb",
        # Mushrooms
        "mushroom", "shiitake", "portobello", "cremini", "oyster mushroom",
        "chanterelle", "porcini", "enoki", "maitake",
        # Fruits
        "apple", "banana", "orange", "lemon", "lime", "grapefruit",
        "tangerine", "clementine", "mandarin",
        "strawberry", "blueberry", "raspberry", "blackberry", "cranberry",
        "peach", "plum", "apricot", "nectarine", "cherry",
        "mango", "pineapple", "papaya", "kiwi", "passion fruit",
        "watermelon", "cantaloupe", "honeydew", "melon",
        "grape", "fig", "date", "pomegranate", "persimmon",
        "pear", "quince", "guava", "lychee", "dragon fruit",
        "avocado", "coconut", "olive",
    ],
    IngredientCategory.GRAINS: [
        # Rice
        "rice", "basmati", "jasmine rice", "arborio", "sushi rice",
        "brown rice", "wild rice", "risotto",
        # Pasta
        "pasta", "spaghetti", "penne", "fusilli", "rigatoni", "linguine",
        "fettuccine", "lasagna", "macaroni", "orzo", "couscous",
        "noodle", "ramen", "udon", "soba", "rice noodle",
        # Other grains
        "quinoa", "bulgur", "farro", "barley", "millet", "buckwheat",
        "polenta", "cornmeal", "grits", "oat", "oatmeal", "rolled oat",
        # Bread
        "bread", "tortilla", "pita", "naan", "focaccia", "ciabatta",
        "baguette", "sourdough", "brioche", "croissant",
        # Flour
        "flour", "all-purpose flour", "bread flour", "whole wheat flour",
        "almond flour", "coconut flour", "rice flour", "cornstarch",
    ],
    IngredientCategory.LEGUMES: [
        "bean", "black bean", "kidney bean", "pinto bean", "navy bean",
        "cannellini", "great northern", "lima bean", "fava bean",
        "lentil", "red lentil", "green lentil", "brown lentil",
        "chickpea", "garbanzo", "hummus",
        "split pea", "black-eyed pea",
        "edamame", "soybean",
    ],
    IngredientCategory.NUTS_SEEDS: [
        # Nuts
        "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut",
        "macadamia", "brazil nut", "pine nut", "chestnut", "peanut",
        # Seeds
        "sesame", "sunflower seed", "pumpkin seed", "pepita",
        "flax", "flaxseed", "chia", "chia seed", "hemp seed",
        # Nut butters
        "peanut butter", "almond butter", "tahini", "nut butter",
    ],
    IngredientCategory.OILS_FATS: [
        "oil", "olive oil", "vegetable oil", "canola oil", "coconut oil",
        "sesame oil", "peanut oil", "avocado oil", "sunflower oil",
        "grapeseed oil", "walnut oil", "truffle oil",
        "shortening", "lard", "tallow", "schmaltz",
        "cooking spray", "nonstick spray",
    ],
    IngredientCategory.SWEETENERS: [
        "sugar", "brown sugar", "powdered sugar", "confectioners sugar",
        "cane sugar", "coconut sugar", "turbinado",
        "honey", "maple syrup", "agave", "molasses", "corn syrup",
        "stevia", "monk fruit", "erythritol", "xylitol",
        "simple syrup", "golden syrup", "treacle",
    ],
    IngredientCategory.BAKING: [
        "baking powder", "baking soda", "yeast", "active dry yeast",
        "instant yeast", "cream of tartar",
        "vanilla", "vanilla extract", "almond extract",
        "cocoa", "cocoa powder", "chocolate", "chocolate chip",
        "gelatin", "pectin", "agar",
        "food coloring", "sprinkles",
    ],
    IngredientCategory.CONDIMENTS: [
        # Sauces
        "soy sauce", "tamari", "worcestershire", "fish sauce",
        "oyster sauce", "hoisin", "teriyaki", "ponzu",
        "hot sauce", "sriracha", "tabasco", "sambal",
        "bbq sauce", "barbecue sauce",
        "tomato sauce", "marinara", "pasta sauce",
        # Spreads
        "ketchup", "mustard", "mayonnaise", "mayo",
        "aioli", "tartar sauce", "remoulade",
        # Vinegars
        "vinegar", "balsamic", "red wine vinegar", "white wine vinegar",
        "apple cider vinegar", "rice vinegar", "sherry vinegar",
        # Pickled/fermented
        "pickle", "relish", "caper", "kimchi", "sauerkraut",
        "miso", "miso paste",
        # Pastes
        "tomato paste", "curry paste", "harissa", "gochujang",
        # Dressings
        "dressing", "ranch", "caesar", "vinaigrette",
    ],
    IngredientCategory.BEVERAGES: [
        "water", "sparkling water", "soda water", "tonic water",
        "juice", "orange juice", "apple juice", "lemon juice", "lime juice",
        "coffee", "espresso", "tea", "green tea", "black tea",
        "wine", "red wine", "white wine", "cooking wine", "sherry",
        "beer", "ale", "stout",
        "broth", "stock", "chicken stock", "beef stock", "vegetable stock",
        "bouillon",
        "coconut milk", "almond milk", "oat milk", "soy milk",
    ],
    IngredientCategory.PANTRY: [
        # Canned goods
        "canned tomato", "crushed tomato", "diced tomato", "tomato puree",
        "canned bean", "canned corn", "canned pea",
        # Dried goods not in other categories
        "breadcrumb", "panko", "crouton",
        "sun-dried tomato",
        # Misc
        "nutritional yeast", "msg", "liquid smoke",
    ],
}


class IngredientCategorizer:
    """Assigns categories to ingredients using rule-based classification."""

    def categorize(self, ingredients: list[ScrapedIngredient]) -> list[ScrapedIngredient]:
        """Categorize a list of ingredients.

        Only assigns categories to ingredients that don't already have one.

        Args:
            ingredients: List of ingredients

        Returns:
            List with categories assigned
        """
        console.print(f"[bold blue]Categorizing {len(ingredients)} ingredients...[/bold blue]")

        categorized = 0
        already_categorized = 0

        for ing in ingredients:
            if ing.category:
                already_categorized += 1
                continue

            category = self.infer_category(ing.canonical_name, ing.description)
            if category:
                ing.category = category.value
                categorized += 1

        console.print(
            f"[green]Categorized {categorized} ingredients "
            f"({already_categorized} already had categories)[/green]"
        )
        return ingredients

    def infer_category(
        self, name: str, description: str | None = None
    ) -> IngredientCategory | None:
        """Infer category from ingredient name and description.

        Args:
            name: Ingredient canonical name
            description: Optional description

        Returns:
            Inferred category or None
        """
        text = f"{name} {description or ''}".lower()

        # Check each category's keywords
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                # Match as whole word or at word boundaries
                pattern = rf"\b{re.escape(keyword)}\b"
                if re.search(pattern, text):
                    return category

        return None

    def get_category_stats(
        self, ingredients: list[ScrapedIngredient]
    ) -> dict[str, int]:
        """Get category distribution statistics.

        Args:
            ingredients: List of ingredients

        Returns:
            Dict mapping category name to count
        """
        stats: dict[str, int] = {}

        for ing in ingredients:
            category = ing.category or "uncategorized"
            stats[category] = stats.get(category, 0) + 1

        return dict(sorted(stats.items(), key=lambda x: -x[1]))
