"""Seed script for common ingredients."""

import os
import sys

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'libraries', 'utils'))

from utils.services.database import Database
from utils.models.ingredient import Ingredient


# Common ingredients organized by category
INGREDIENTS = {
    "produce": [
        "tomato",
        "onion",
        "garlic",
        "carrot",
        "potato",
        "lettuce",
        "spinach",
        "broccoli",
        "bell pepper",
        "cucumber",
        "celery",
        "mushroom",
        "zucchini",
        "lemon",
        "lime",
        "avocado",
        "ginger",
        "green onion",
        "jalapeño",
    ],
    "protein": [
        "chicken breast",
        "chicken thigh",
        "ground beef",
        "beef steak",
        "pork chop",
        "bacon",
        "salmon",
        "shrimp",
        "tuna",
        "tofu",
        "eggs",
    ],
    "dairy": [
        "milk",
        "butter",
        "cheddar cheese",
        "parmesan cheese",
        "mozzarella cheese",
        "cream cheese",
        "heavy cream",
        "sour cream",
        "yogurt",
    ],
    "pantry": [
        "pasta",
        "rice",
        "bread",
        "all-purpose flour",
        "sugar",
        "brown sugar",
        "salt",
        "olive oil",
        "vegetable oil",
        "soy sauce",
        "vinegar",
        "honey",
        "chicken broth",
        "beef broth",
        "tomato paste",
        "canned tomatoes",
        "black beans",
        "chickpeas",
    ],
    "herbs_spices": [
        "basil",
        "oregano",
        "thyme",
        "rosemary",
        "parsley",
        "cilantro",
        "cumin",
        "paprika",
        "black pepper",
        "red pepper flakes",
        "cinnamon",
        "cayenne pepper",
        "garlic powder",
        "onion powder",
        "italian seasoning",
    ],
}


def seed_ingredients():
    """Seed the database with common ingredients."""
    database = Database()

    created_count = 0
    skipped_count = 0

    for category, ingredients in INGREDIENTS.items():
        for ingredient_name in ingredients:
            # Check if ingredient already exists
            existing = database.find_by(
                Ingredient,
                canonical_name=ingredient_name.lower()
            )
            if existing:
                print(f"  Skipped (exists): {ingredient_name}")
                skipped_count += 1
                continue

            # Create ingredient
            ingredient = Ingredient(
                canonical_name=ingredient_name.lower(),
                category=category,
                is_canonical=True,
                pending_review=False,
            )
            database.create(ingredient)
            database.db.refresh(ingredient)
            print(f"  Created: {ingredient_name} ({category})")
            created_count += 1

    database.close()

    print(f"\nSeeding complete!")
    print(f"  Created: {created_count}")
    print(f"  Skipped: {skipped_count}")


if __name__ == "__main__":
    print("Seeding ingredients...")
    seed_ingredients()
