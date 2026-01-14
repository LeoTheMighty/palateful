"""Ingredient deduplication using fuzzy string matching.

Merges duplicate ingredients from different sources while preserving
the most complete metadata from each.
"""

from collections import defaultdict

from rapidfuzz import fuzz, process
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import settings
from ..models import ScrapedIngredient

console = Console()


class IngredientDeduplicator:
    """Deduplicates ingredients using fuzzy matching."""

    def __init__(self, similarity_threshold: float | None = None):
        """Initialize deduplicator.

        Args:
            similarity_threshold: Minimum similarity score (0-100) to consider
                                  ingredients as duplicates. Default from settings.
        """
        self.threshold = similarity_threshold or (settings.dedup_similarity_threshold * 100)

    def deduplicate(self, ingredients: list[ScrapedIngredient]) -> list[ScrapedIngredient]:
        """Deduplicate a list of ingredients.

        Strategy:
        1. Group exact matches by canonical name
        2. Find fuzzy matches within a threshold
        3. Merge metadata from duplicates

        Args:
            ingredients: List of ingredients (may contain duplicates)

        Returns:
            Deduplicated list with merged metadata
        """
        console.print(f"[bold blue]Deduplicating {len(ingredients)} ingredients...[/bold blue]")

        if not ingredients:
            return []

        # Step 1: Group by exact canonical name match
        exact_groups = self._group_exact_matches(ingredients)
        console.print(f"[dim]  Found {len(exact_groups)} unique names after exact matching[/dim]")

        # Step 2: Merge exact matches
        merged_exact = [
            self._merge_group(group) for group in exact_groups.values()
        ]

        # Step 3: Find and merge fuzzy matches
        deduplicated = self._find_and_merge_fuzzy(merged_exact)

        console.print(f"[green]Deduplicated to {len(deduplicated)} unique ingredients[/green]")
        return deduplicated

    def _group_exact_matches(
        self, ingredients: list[ScrapedIngredient]
    ) -> dict[str, list[ScrapedIngredient]]:
        """Group ingredients by exact canonical name match.

        Args:
            ingredients: List of ingredients

        Returns:
            Dict mapping canonical name to list of ingredients
        """
        groups: dict[str, list[ScrapedIngredient]] = defaultdict(list)

        for ing in ingredients:
            key = ing.canonical_name.lower().strip()
            groups[key].append(ing)

        return groups

    def _merge_group(self, group: list[ScrapedIngredient]) -> ScrapedIngredient:
        """Merge a group of ingredients with the same name.

        Args:
            group: List of ingredients to merge

        Returns:
            Single merged ingredient
        """
        if len(group) == 1:
            return group[0]

        # Start with the first ingredient and merge others into it
        result = group[0]
        for other in group[1:]:
            result = result.merge_with(other)

        return result

    def _find_and_merge_fuzzy(
        self, ingredients: list[ScrapedIngredient]
    ) -> list[ScrapedIngredient]:
        """Find and merge fuzzy matches.

        Uses a greedy approach:
        1. Sort by name length (prefer shorter, more canonical names)
        2. For each ingredient, find fuzzy matches
        3. Merge matches and mark them as processed

        Args:
            ingredients: List of ingredients (already exact-merged)

        Returns:
            List with fuzzy duplicates merged
        """
        if len(ingredients) <= 1:
            return ingredients

        # Sort by name length (shorter names are more likely to be canonical)
        sorted_ings = sorted(ingredients, key=lambda x: len(x.canonical_name))

        # Build a mapping of name -> ingredient for fast lookup
        name_to_ing: dict[str, ScrapedIngredient] = {
            ing.canonical_name: ing for ing in sorted_ings
        }
        names = list(name_to_ing.keys())

        # Track which names have been merged into others
        merged_into: dict[str, str] = {}  # name -> canonical name it was merged into

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Finding fuzzy matches...", total=len(names))

            for i, name in enumerate(names):
                progress.update(task, advance=1)

                # Skip if this name was already merged into another
                if name in merged_into:
                    continue

                # Find fuzzy matches (excluding self and already-merged)
                candidates = [
                    n for n in names[i + 1:]
                    if n not in merged_into
                ]

                if not candidates:
                    continue

                # Use rapidfuzz to find matches above threshold
                matches = process.extract(
                    name,
                    candidates,
                    scorer=fuzz.ratio,
                    limit=None,
                    score_cutoff=self.threshold,
                )

                for match_name, score, _ in matches:
                    # Merge the match into the current ingredient
                    match_ing = name_to_ing[match_name]
                    current_ing = name_to_ing[name]

                    # Add the match name as an alias
                    if match_name not in current_ing.aliases:
                        current_ing.aliases.append(match_name)

                    # Merge metadata
                    merged = current_ing.merge_with(match_ing)
                    name_to_ing[name] = merged

                    # Mark match as merged
                    merged_into[match_name] = name

        # Collect results (excluding merged ingredients)
        result = [
            ing for name, ing in name_to_ing.items()
            if name not in merged_into
        ]

        return result

    def find_similar(
        self,
        ingredient: ScrapedIngredient,
        candidates: list[ScrapedIngredient],
        top_n: int = 5,
    ) -> list[tuple[ScrapedIngredient, float]]:
        """Find ingredients similar to a given ingredient.

        Args:
            ingredient: The ingredient to match
            candidates: List of candidate ingredients
            top_n: Number of top matches to return

        Returns:
            List of (ingredient, similarity_score) tuples
        """
        if not candidates:
            return []

        candidate_names = [c.canonical_name for c in candidates]
        name_to_ing = {c.canonical_name: c for c in candidates}

        matches = process.extract(
            ingredient.canonical_name,
            candidate_names,
            scorer=fuzz.ratio,
            limit=top_n,
        )

        return [
            (name_to_ing[name], score)
            for name, score, _ in matches
        ]
