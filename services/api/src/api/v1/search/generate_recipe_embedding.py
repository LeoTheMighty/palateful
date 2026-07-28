"""Helper to generate recipe embeddings via OpenAI text-embedding-3-small."""

import json
import logging

logger = logging.getLogger(__name__)


async def generate_recipe_embedding(
    recipe_name: str,
    description: str | None,
    tags: list[str] | None,
    primary_vibe: str | None = None,
) -> list[float] | None:
    """Generate a 384-dim embedding for a recipe via OpenAI.

    Uses text-embedding-3-small with dimensions=384 to stay compatible with
    the existing Vector(384) column and ix_recipe_embedding_hnsw HNSW index.

    Returns None on any failure so callers never block on embedding generation.
    """
    vibe_text = f" Vibe: {primary_vibe}" if primary_vibe else ""
    input_text = f"{recipe_name}. {description or ''}. Tags: {', '.join(tags or [])}{vibe_text}"
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()  # reads OPENAI_API_KEY from env
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=input_text,
            dimensions=384,
        )
        return resp.data[0].embedding
    except Exception:
        return None


async def assign_vibes_for_recipe(
    recipe_name: str,
    description: str | None,
    ingredients_text: str | None = None,
) -> tuple[str | None, str | None]:
    """Assign vibes using a lightweight GPT-4o-mini call.

    Used for recipes that bypass AI extraction (JSON-LD, manual creation).
    Returns (primary_vibe, secondary_vibe).
    """
    from utils.constants import VALID_VIBES

    prompt_text = recipe_name
    if description:
        prompt_text += f". {description}"
    if ingredients_text:
        prompt_text += f". Ingredients: {ingredients_text}"

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Assign 1-2 vibes to this recipe. "
                        f"Valid vibes: {VALID_VIBES}. "
                        'Return JSON: {"primary_vibe": "...", "secondary_vibe": "..." or null}'
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
        return (
            primary if primary in VALID_VIBES else None,
            secondary if secondary in VALID_VIBES else None,
        )
    except Exception:
        logger.debug("Failed to assign vibes for recipe: %s", recipe_name)
        return None, None
