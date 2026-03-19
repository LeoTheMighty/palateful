"""Helper to generate recipe embeddings via OpenAI text-embedding-3-small."""


def generate_recipe_embedding(
    recipe_name: str,
    description: str | None,
    tags: list[str] | None,
) -> list[float] | None:
    """Generate a 384-dim embedding for a recipe via OpenAI.

    Uses text-embedding-3-small with dimensions=384 to stay compatible with
    the existing Vector(384) column and ix_recipe_embedding_hnsw HNSW index.

    Returns None on any failure so callers never block on embedding generation.
    """
    input_text = f"{recipe_name}. {description or ''}. Tags: {', '.join(tags or [])}"
    try:
        from openai import OpenAI

        client = OpenAI()  # reads OPENAI_API_KEY from env
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=input_text,
            dimensions=384,
        )
        return resp.data[0].embedding
    except Exception:
        return None
