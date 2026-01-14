"""Statistics generator for ingredient datasets."""

from collections import Counter
from typing import Any

from rich.console import Console
from rich.table import Table

from ..models import ScrapedIngredient, Substitution

console = Console()


class StatsGenerator:
    """Generates and displays statistics about ingredient datasets."""

    def generate(
        self,
        ingredients: list[ScrapedIngredient],
        substitutions: list[Substitution] | None = None,
    ) -> dict[str, Any]:
        """Generate statistics for a dataset.

        Args:
            ingredients: List of ingredients
            substitutions: Optional list of substitutions

        Returns:
            Dict of statistics
        """
        substitutions = substitutions or []

        # Category distribution
        categories = Counter(ing.category or "uncategorized" for ing in ingredients)

        # Source distribution
        sources = Counter()
        for ing in ingredients:
            for source in ing.source.split(","):
                sources[source.strip()] += 1

        # Data completeness
        with_aliases = sum(1 for ing in ingredients if ing.aliases)
        with_category = sum(1 for ing in ingredients if ing.category)
        with_unit = sum(1 for ing in ingredients if ing.default_unit)
        with_image = sum(1 for ing in ingredients if ing.image_url)
        with_embedding = sum(1 for ing in ingredients if ing.embedding)
        with_description = sum(1 for ing in ingredients if ing.description)

        # Substitution stats
        sub_by_context = Counter(sub.context.value for sub in substitutions)
        sub_by_quality = Counter(sub.quality.value for sub in substitutions)

        return {
            "total_ingredients": len(ingredients),
            "total_substitutions": len(substitutions),
            "categories": dict(categories.most_common()),
            "sources": dict(sources.most_common()),
            "completeness": {
                "with_aliases": with_aliases,
                "with_category": with_category,
                "with_default_unit": with_unit,
                "with_image_url": with_image,
                "with_embedding": with_embedding,
                "with_description": with_description,
            },
            "substitution_contexts": dict(sub_by_context),
            "substitution_qualities": dict(sub_by_quality),
        }

    def display(
        self,
        ingredients: list[ScrapedIngredient],
        substitutions: list[Substitution] | None = None,
    ) -> None:
        """Display statistics in a nice table format.

        Args:
            ingredients: List of ingredients
            substitutions: Optional list of substitutions
        """
        stats = self.generate(ingredients, substitutions)

        # Overview table
        console.print("\n[bold]Dataset Overview[/bold]")
        overview_table = Table(show_header=False, box=None)
        overview_table.add_column("Metric", style="cyan")
        overview_table.add_column("Value", style="green")
        overview_table.add_row("Total Ingredients", str(stats["total_ingredients"]))
        overview_table.add_row("Total Substitutions", str(stats["total_substitutions"]))
        console.print(overview_table)

        # Categories table
        console.print("\n[bold]Categories[/bold]")
        cat_table = Table(show_header=True)
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", style="green", justify="right")
        cat_table.add_column("Percentage", style="yellow", justify="right")

        total = stats["total_ingredients"]
        for cat, count in stats["categories"].items():
            pct = f"{count / total * 100:.1f}%"
            cat_table.add_row(cat, str(count), pct)
        console.print(cat_table)

        # Sources table
        console.print("\n[bold]Sources[/bold]")
        src_table = Table(show_header=True)
        src_table.add_column("Source", style="cyan")
        src_table.add_column("Count", style="green", justify="right")
        for src, count in stats["sources"].items():
            src_table.add_row(src, str(count))
        console.print(src_table)

        # Completeness table
        console.print("\n[bold]Data Completeness[/bold]")
        comp_table = Table(show_header=True)
        comp_table.add_column("Field", style="cyan")
        comp_table.add_column("Count", style="green", justify="right")
        comp_table.add_column("Percentage", style="yellow", justify="right")

        for field, count in stats["completeness"].items():
            pct = f"{count / total * 100:.1f}%"
            field_name = field.replace("with_", "").replace("_", " ").title()
            comp_table.add_row(field_name, str(count), pct)
        console.print(comp_table)

        # Substitution stats (if any)
        if stats["total_substitutions"] > 0:
            console.print("\n[bold]Substitution Breakdown[/bold]")

            # By context
            ctx_table = Table(show_header=True)
            ctx_table.add_column("Context", style="cyan")
            ctx_table.add_column("Count", style="green", justify="right")
            for ctx, count in stats["substitution_contexts"].items():
                ctx_table.add_row(ctx, str(count))
            console.print(ctx_table)

            # By quality
            qual_table = Table(show_header=True)
            qual_table.add_column("Quality", style="cyan")
            qual_table.add_column("Count", style="green", justify="right")
            for qual, count in stats["substitution_qualities"].items():
                qual_table.add_row(qual, str(count))
            console.print(qual_table)
