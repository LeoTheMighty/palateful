"""Backfill vibes for existing recipes missing vibe assignments.

Usage:
    python scripts/backfill_vibes.py

Requires DATABASE_URL and OPENAI_API_KEY environment variables.
Uses GPT-4o-mini for lightweight vibe assignment (~$0.001 per recipe).
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VALID_VIBES = [
    "light_fresh", "hearty", "comfort", "energizing",
    "carb_load", "indulgent", "warming",
]

BATCH_SIZE = 50


def get_db_connection():
    """Create a database connection using DATABASE_URL."""
    from sqlalchemy import create_engine
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)
    return create_engine(database_url)


def fetch_recipes_without_vibes(engine, batch_size: int):
    """Fetch recipes that need vibe assignment."""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT id, name, description FROM recipes "
                "WHERE primary_vibe IS NULL AND archived_at IS NULL "
                "LIMIT :limit"
            ),
            {"limit": batch_size},
        )
        return [dict(row._mapping) for row in result]


def assign_vibes_batch(recipes: list[dict], client) -> list[dict]:
    """Assign vibes to a batch of recipes using GPT-4o-mini."""
    results = []
    for recipe in recipes:
        prompt_text = recipe["name"]
        if recipe.get("description"):
            prompt_text += f". {recipe['description']}"

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Assign 1-2 vibes to this recipe. "
                            f"Valid vibes: {VALID_VIBES}. "
                            'Return JSON: {{"primary_vibe": "...", "secondary_vibe": "..." or null}}'
                        ),
                    },
                    {"role": "user", "content": prompt_text},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=50,
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            primary = data.get("primary_vibe")
            secondary = data.get("secondary_vibe")
            results.append({
                "id": recipe["id"],
                "primary_vibe": primary if primary in VALID_VIBES else None,
                "secondary_vibe": secondary if secondary in VALID_VIBES else None,
            })
        except Exception as e:
            logger.warning("Failed to assign vibes for recipe %s: %s", recipe["id"], e)
            results.append({"id": recipe["id"], "primary_vibe": None, "secondary_vibe": None})

    return results


def update_recipes(engine, assignments: list[dict]):
    """Update recipes with assigned vibes."""
    from sqlalchemy import text
    with engine.begin() as conn:
        for assignment in assignments:
            if assignment["primary_vibe"]:
                conn.execute(
                    text(
                        "UPDATE recipes SET primary_vibe = :primary, secondary_vibe = :secondary "
                        "WHERE id = :id"
                    ),
                    {
                        "id": assignment["id"],
                        "primary": assignment["primary_vibe"],
                        "secondary": assignment["secondary_vibe"],
                    },
                )


def main():
    """Run the backfill."""
    from openai import OpenAI

    engine = get_db_connection()
    client = OpenAI()

    total_processed = 0
    total_assigned = 0

    while True:
        recipes = fetch_recipes_without_vibes(engine, BATCH_SIZE)
        if not recipes:
            break

        logger.info("Processing batch of %d recipes...", len(recipes))
        assignments = assign_vibes_batch(recipes, client)

        successful = [a for a in assignments if a["primary_vibe"]]
        update_recipes(engine, successful)

        total_processed += len(recipes)
        total_assigned += len(successful)
        logger.info(
            "Batch complete: %d/%d assigned. Total: %d processed, %d assigned.",
            len(successful), len(recipes), total_processed, total_assigned,
        )

    logger.info("Backfill complete. %d recipes processed, %d vibes assigned.", total_processed, total_assigned)


if __name__ == "__main__":
    main()
