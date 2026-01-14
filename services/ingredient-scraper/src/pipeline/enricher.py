"""Ingredient enrichment with embeddings and AI-generated substitutions.

Generates:
- Semantic embeddings using sentence-transformers
- Substitution suggestions using OpenAI
"""

import json
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
from sentence_transformers import SentenceTransformer

from ..config import settings
from ..models import ScrapedIngredient, Substitution, SubstitutionContext, SubstitutionQuality

console = Console()


class IngredientEnricher:
    """Enriches ingredients with embeddings and substitution suggestions."""

    def __init__(
        self,
        embedding_model: str | None = None,
        openai_api_key: str | None = None,
    ):
        """Initialize enricher.

        Args:
            embedding_model: Name of the sentence-transformers model
            openai_api_key: OpenAI API key for substitution generation
        """
        self.embedding_model_name = embedding_model or settings.embedding_model
        self.openai_api_key = openai_api_key or settings.openai_api_key

        self._embedding_model: SentenceTransformer | None = None
        self._openai_client: OpenAI | None = None

    @property
    def embedding_model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            console.print(f"[dim]Loading embedding model: {self.embedding_model_name}[/dim]")
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model

    @property
    def openai_client(self) -> OpenAI | None:
        """Get OpenAI client if API key is available."""
        if self._openai_client is None and self.openai_api_key:
            self._openai_client = OpenAI(api_key=self.openai_api_key)
        return self._openai_client

    def generate_embeddings(
        self, ingredients: list[ScrapedIngredient]
    ) -> list[ScrapedIngredient]:
        """Generate embeddings for ingredients.

        Creates embeddings from: canonical_name + aliases + category

        Args:
            ingredients: List of ingredients

        Returns:
            Ingredients with embeddings populated
        """
        console.print(f"[bold blue]Generating embeddings for {len(ingredients)} ingredients...[/bold blue]")

        # Prepare texts for embedding
        texts = []
        for ing in ingredients:
            # Combine name, aliases, and category for richer embedding
            parts = [ing.canonical_name]
            if ing.aliases:
                parts.extend(ing.aliases[:3])  # Limit aliases to avoid too much noise
            if ing.category:
                parts.append(ing.category.replace("_", " "))
            texts.append(" ".join(parts))

        # Generate embeddings in batches
        batch_size = settings.embedding_batch_size

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Generating embeddings...", total=len(texts))

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_embeddings = self.embedding_model.encode(
                    batch_texts,
                    show_progress_bar=False,
                )

                # Assign embeddings to ingredients
                for j, embedding in enumerate(batch_embeddings):
                    ingredients[i + j].embedding = embedding.tolist()

                progress.update(task, advance=len(batch_texts))

        console.print(f"[green]Generated {len(ingredients)} embeddings[/green]")
        return ingredients

    async def generate_substitutions(
        self,
        ingredients: list[ScrapedIngredient],
        batch_size: int | None = None,
    ) -> list[Substitution]:
        """Generate substitution suggestions using OpenAI.

        Args:
            ingredients: List of ingredients to generate substitutions for
            batch_size: Number of ingredients per API call

        Returns:
            List of substitution suggestions
        """
        if not self.openai_client:
            console.print("[yellow]No OpenAI API key - skipping substitution generation[/yellow]")
            return []

        console.print(f"[bold blue]Generating substitutions for {len(ingredients)} ingredients...[/bold blue]")

        batch_size = batch_size or settings.substitution_batch_size
        all_substitutions: list[Substitution] = []

        # Create a mapping of canonical names for validation
        valid_names = {ing.canonical_name for ing in ingredients}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Generating substitutions...", total=len(ingredients))

            for i in range(0, len(ingredients), batch_size):
                batch = ingredients[i:i + batch_size]

                try:
                    substitutions = self._generate_batch_substitutions(batch, valid_names)
                    all_substitutions.extend(substitutions)
                except Exception as e:
                    console.print(f"[yellow]Error generating substitutions: {e}[/yellow]")

                progress.update(task, advance=len(batch))

        console.print(f"[green]Generated {len(all_substitutions)} substitutions[/green]")
        return all_substitutions

    def _generate_batch_substitutions(
        self,
        ingredients: list[ScrapedIngredient],
        valid_names: set[str],
    ) -> list[Substitution]:
        """Generate substitutions for a batch of ingredients.

        Args:
            ingredients: Batch of ingredients
            valid_names: Set of valid ingredient names (for validation)

        Returns:
            List of substitutions
        """
        if not self.openai_client:
            return []

        # Build the prompt
        ingredient_list = "\n".join(
            f"- {ing.canonical_name} ({ing.category or 'uncategorized'})"
            for ing in ingredients
        )

        prompt = f"""For each of the following cooking ingredients, suggest 2-3 practical substitutes that a home cook might use. Consider dietary restrictions, flavor profiles, and availability.

Ingredients:
{ingredient_list}

For each substitution, provide:
1. The original ingredient (exact match from list)
2. The substitute ingredient (use simple, common names)
3. Context: "baking", "cooking", "raw", or "any"
4. Quality: "perfect" (nearly identical), "good" (works well), or "workable" (acceptable in a pinch)
5. Ratio: how much substitute to use (e.g., 1.0 for same amount, 0.5 for half)
6. Brief note explaining the substitution

Respond with a JSON array of objects with keys: ingredient, substitute, context, quality, ratio, notes

Example:
[
  {{"ingredient": "butter", "substitute": "coconut oil", "context": "baking", "quality": "good", "ratio": 1.0, "notes": "Works well in most baking, adds slight coconut flavor"}},
  {{"ingredient": "butter", "substitute": "olive oil", "context": "cooking", "quality": "good", "ratio": 0.75, "notes": "Use 3/4 the amount for sautéing"}}
]"""

        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a culinary expert helping home cooks find ingredient substitutions. Respond only with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=settings.openai_max_tokens,
            )

            # Parse the response
            content = response.choices[0].message.content
            if not content:
                return []

            # Extract JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code block
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            data = json.loads(content)

            substitutions = []
            for item in data:
                # Validate the substitution
                ingredient = item.get("ingredient", "").lower().strip()
                substitute = item.get("substitute", "").lower().strip()

                if not ingredient or not substitute:
                    continue

                # Check if ingredient is in our list
                if ingredient not in valid_names:
                    continue

                try:
                    sub = Substitution(
                        ingredient=ingredient,
                        substitute=substitute,
                        context=SubstitutionContext(item.get("context", "any")),
                        quality=SubstitutionQuality(item.get("quality", "good")),
                        ratio=float(item.get("ratio", 1.0)),
                        notes=item.get("notes"),
                    )
                    substitutions.append(sub)
                except (ValueError, KeyError):
                    continue

            return substitutions

        except json.JSONDecodeError as e:
            console.print(f"[yellow]Failed to parse substitution response: {e}[/yellow]")
            return []
        except Exception as e:
            console.print(f"[yellow]OpenAI API error: {e}[/yellow]")
            return []

    def enrich(
        self,
        ingredients: list[ScrapedIngredient],
        generate_embeddings: bool = True,
        generate_subs: bool = False,
    ) -> tuple[list[ScrapedIngredient], list[Substitution]]:
        """Run the full enrichment pipeline.

        Args:
            ingredients: List of ingredients to enrich
            generate_embeddings: Whether to generate embeddings
            generate_subs: Whether to generate substitutions

        Returns:
            Tuple of (enriched ingredients, substitutions)
        """
        substitutions: list[Substitution] = []

        if generate_embeddings:
            ingredients = self.generate_embeddings(ingredients)

        if generate_subs:
            import asyncio
            substitutions = asyncio.run(self.generate_substitutions(ingredients))

        return ingredients, substitutions
