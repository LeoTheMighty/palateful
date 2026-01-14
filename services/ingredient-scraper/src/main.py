"""Ingredient Scraper CLI.

A CLI tool for building a comprehensive ingredient database by scraping
from multiple food data sources, normalizing, deduplicating, and enriching
the data with embeddings and substitution suggestions.

Usage:
    # Scrape from all sources
    python -m src.main scrape --all

    # Scrape from a specific source with limit
    python -m src.main scrape --source themealdb --limit 100

    # Run the full pipeline (scrape + process + export)
    python -m src.main pipeline --all

    # Export to CSV
    python -m src.main export --output ./output

    # Show statistics for existing data
    python -m src.main stats

    # List available versions
    python -m src.main versions
"""

import asyncio
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from .config import settings
from .models import ScrapedIngredient, Substitution
from .scrapers import TheMealDBScraper, USDAFoodDataScraper, OpenFoodFactsScraper
from .pipeline import (
    IngredientNormalizer,
    IngredientDeduplicator,
    IngredientCategorizer,
    IngredientEnricher,
)
from .output import CSVWriter, StatsGenerator

console = Console()
app = typer.Typer(
    name="ingredient-scraper",
    help="Build a comprehensive ingredient database from multiple sources.",
    add_completion=False,
)


class Source(str, Enum):
    """Available data sources."""
    themealdb = "themealdb"
    usda = "usda"
    openfoodfacts = "openfoodfacts"
    all = "all"


@app.command()
def scrape(
    source: Annotated[
        Source,
        typer.Option("--source", "-s", help="Data source to scrape from")
    ] = Source.themealdb,
    all_sources: Annotated[
        bool,
        typer.Option("--all", "-a", help="Scrape from all sources")
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", "-l", help="Maximum ingredients per source")
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory")
    ] = Path("./output"),
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Disable request caching")
    ] = False,
) -> None:
    """Scrape ingredients from external sources."""

    async def _scrape():
        all_ingredients: list[ScrapedIngredient] = []

        sources_to_scrape = []
        if all_sources or source == Source.all:
            sources_to_scrape = [Source.themealdb, Source.usda, Source.openfoodfacts]
        else:
            sources_to_scrape = [source]

        for src in sources_to_scrape:
            ingredients = await _scrape_source(src, limit, no_cache)
            all_ingredients.extend(ingredients)

        if all_ingredients:
            console.print(f"\n[bold]Total scraped: {len(all_ingredients)} ingredients[/bold]")

            # Save raw output
            output.mkdir(parents=True, exist_ok=True)
            writer = CSVWriter(output / "raw")
            writer.write(all_ingredients, notes=f"Raw scrape from {source}")

    asyncio.run(_scrape())


async def _scrape_source(
    source: Source, limit: int | None, no_cache: bool
) -> list[ScrapedIngredient]:
    """Scrape from a single source."""
    cache_ttl = 0 if no_cache else 24

    if source == Source.themealdb:
        async with TheMealDBScraper(cache_ttl_hours=cache_ttl) as scraper:
            return await scraper.scrape(limit=limit)

    elif source == Source.usda:
        if not settings.usda_api_key:
            console.print("[yellow]Skipping USDA - no API key configured[/yellow]")
            console.print("[dim]Set USDA_API_KEY environment variable[/dim]")
            return []
        async with USDAFoodDataScraper(cache_ttl_hours=cache_ttl) as scraper:
            return await scraper.scrape(limit=limit)

    elif source == Source.openfoodfacts:
        async with OpenFoodFactsScraper(cache_ttl_hours=cache_ttl) as scraper:
            return await scraper.scrape(limit=limit)

    return []


@app.command()
def process(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Input directory with raw CSV")
    ] = Path("./output/raw"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for processed data")
    ] = Path("./output/processed"),
    skip_normalize: Annotated[
        bool,
        typer.Option("--skip-normalize", help="Skip normalization step")
    ] = False,
    skip_dedup: Annotated[
        bool,
        typer.Option("--skip-dedup", help="Skip deduplication step")
    ] = False,
    skip_categorize: Annotated[
        bool,
        typer.Option("--skip-categorize", help="Skip categorization step")
    ] = False,
) -> None:
    """Process raw scraped data (normalize, deduplicate, categorize)."""
    # Load raw data
    reader = CSVWriter(input_dir)
    ingredients, _ = reader.load_latest()

    if not ingredients:
        console.print("[red]No ingredients found in input directory[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Loaded {len(ingredients)} raw ingredients[/bold]\n")

    # Normalize
    if not skip_normalize:
        normalizer = IngredientNormalizer()
        ingredients = normalizer.normalize(ingredients)

    # Deduplicate
    if not skip_dedup:
        deduplicator = IngredientDeduplicator()
        ingredients = deduplicator.deduplicate(ingredients)

    # Categorize
    if not skip_categorize:
        categorizer = IngredientCategorizer()
        ingredients = categorizer.categorize(ingredients)

    # Save processed output
    writer = CSVWriter(output)
    writer.write(ingredients, notes="Processed (normalized, deduplicated, categorized)")

    console.print(f"\n[bold green]Processed {len(ingredients)} ingredients[/bold green]")


@app.command()
def enrich(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Input directory with processed CSV")
    ] = Path("./output/processed"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for enriched data")
    ] = Path("./output/enriched"),
    embeddings: Annotated[
        bool,
        typer.Option("--embeddings", "-e", help="Generate embeddings")
    ] = True,
    substitutions: Annotated[
        bool,
        typer.Option("--substitutions", "-s", help="Generate substitutions with OpenAI")
    ] = False,
) -> None:
    """Enrich ingredients with embeddings and substitutions."""
    # Load processed data
    reader = CSVWriter(input_dir)
    ingredients, existing_subs = reader.load_latest()

    if not ingredients:
        console.print("[red]No ingredients found in input directory[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Loaded {len(ingredients)} ingredients[/bold]\n")

    # Enrich
    enricher = IngredientEnricher()
    ingredients, new_subs = enricher.enrich(
        ingredients,
        generate_embeddings=embeddings,
        generate_subs=substitutions,
    )

    # Combine substitutions
    all_subs = existing_subs + new_subs

    # Save enriched output
    writer = CSVWriter(output)
    features = []
    if embeddings:
        features.append("embeddings")
    if substitutions:
        features.append("substitutions")
    writer.write(
        ingredients,
        all_subs,
        notes=f"Enriched with: {', '.join(features)}"
    )

    console.print(f"\n[bold green]Enriched {len(ingredients)} ingredients[/bold green]")
    if all_subs:
        console.print(f"[bold green]Generated {len(new_subs)} new substitutions[/bold green]")


@app.command()
def pipeline(
    all_sources: Annotated[
        bool,
        typer.Option("--all", "-a", help="Scrape from all sources")
    ] = False,
    source: Annotated[
        Source,
        typer.Option("--source", "-s", help="Data source to scrape from")
    ] = Source.themealdb,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", "-l", help="Maximum ingredients per source")
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory")
    ] = Path("./output"),
    embeddings: Annotated[
        bool,
        typer.Option("--embeddings/--no-embeddings", help="Generate embeddings")
    ] = True,
    substitutions: Annotated[
        bool,
        typer.Option("--substitutions", help="Generate substitutions with OpenAI")
    ] = False,
    merge: Annotated[
        bool,
        typer.Option("--merge", "-m", help="Merge with existing data")
    ] = False,
) -> None:
    """Run the full pipeline: scrape -> process -> enrich -> export."""

    async def _pipeline():
        console.print("[bold cyan]Starting ingredient scraper pipeline[/bold cyan]\n")

        # Step 1: Scrape
        console.print("[bold]Step 1: Scraping[/bold]")
        all_ingredients: list[ScrapedIngredient] = []

        sources_to_scrape = []
        if all_sources or source == Source.all:
            sources_to_scrape = [Source.themealdb, Source.usda, Source.openfoodfacts]
        else:
            sources_to_scrape = [source]

        for src in sources_to_scrape:
            ingredients = await _scrape_source(src, limit, no_cache=False)
            all_ingredients.extend(ingredients)

        if not all_ingredients:
            console.print("[red]No ingredients scraped[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Scraped {len(all_ingredients)} ingredients[/green]\n")

        # Step 2: Normalize
        console.print("[bold]Step 2: Normalizing[/bold]")
        normalizer = IngredientNormalizer()
        all_ingredients = normalizer.normalize(all_ingredients)

        # Step 3: Deduplicate
        console.print("\n[bold]Step 3: Deduplicating[/bold]")
        deduplicator = IngredientDeduplicator()
        all_ingredients = deduplicator.deduplicate(all_ingredients)

        # Step 4: Categorize
        console.print("\n[bold]Step 4: Categorizing[/bold]")
        categorizer = IngredientCategorizer()
        all_ingredients = categorizer.categorize(all_ingredients)

        # Step 5: Enrich
        console.print("\n[bold]Step 5: Enriching[/bold]")
        enricher = IngredientEnricher()
        all_ingredients, subs = enricher.enrich(
            all_ingredients,
            generate_embeddings=embeddings,
            generate_subs=substitutions,
        )

        # Step 6: Merge (if requested)
        if merge:
            console.print("\n[bold]Step 6: Merging with existing[/bold]")
            writer = CSVWriter(output / "final")
            all_ingredients, subs = writer.merge_with_existing(all_ingredients, subs)

        # Step 7: Export
        console.print("\n[bold]Step 7: Exporting[/bold]")
        writer = CSVWriter(output / "final")
        version = writer.write(
            all_ingredients,
            subs,
            notes=f"Full pipeline from {', '.join(s.value for s in sources_to_scrape)}"
        )

        # Show stats
        console.print("\n[bold]Final Statistics[/bold]")
        stats = StatsGenerator()
        stats.display(all_ingredients, subs)

        console.print(f"\n[bold green]Pipeline complete! Version: {version}[/bold green]")
        console.print(f"[dim]Output: {output / 'final'}[/dim]")

    asyncio.run(_pipeline())


@app.command()
def export(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Input directory with CSV data")
    ] = Path("./output/final"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for seed files")
    ] = Path("../../services/migrator/seeds"),
    version: Annotated[
        Optional[str],
        typer.Option("--version", "-v", help="Specific version to export")
    ] = None,
) -> None:
    """Export CSV files to the migrator seeds directory."""
    reader = CSVWriter(input_dir)

    if version:
        ingredients, subs = reader.load_version(version)
    else:
        ingredients, subs = reader.load_latest()
        version = reader.get_latest_version()

    if not ingredients:
        console.print("[red]No ingredients found[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Exporting version {version}[/bold]")
    console.print(f"[dim]  {len(ingredients)} ingredients[/dim]")
    console.print(f"[dim]  {len(subs)} substitutions[/dim]")

    # Write to output
    output.mkdir(parents=True, exist_ok=True)
    writer = CSVWriter(output)
    writer.write(ingredients, subs, version=version, notes="Exported for database seeding")

    console.print(f"\n[bold green]Exported to {output}[/bold green]")


@app.command()
def stats(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Input directory with CSV data")
    ] = Path("./output/final"),
) -> None:
    """Display statistics for the ingredient dataset."""
    reader = CSVWriter(input_dir)
    ingredients, subs = reader.load_latest()

    if not ingredients:
        console.print("[red]No ingredients found[/red]")
        raise typer.Exit(1)

    stats = StatsGenerator()
    stats.display(ingredients, subs)


@app.command()
def versions(
    input_dir: Annotated[
        Path,
        typer.Option("--input", "-i", help="Directory to check for versions")
    ] = Path("./output/final"),
) -> None:
    """List all available versions."""
    reader = CSVWriter(input_dir)
    versions_list = reader.list_versions()

    if not versions_list:
        console.print("[yellow]No versions found[/yellow]")
        return

    from rich.table import Table

    table = Table(title="Available Versions")
    table.add_column("Version", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Ingredients", justify="right")
    table.add_column("Substitutions", justify="right")
    table.add_column("Notes")

    for v in versions_list:
        table.add_row(
            v["version"],
            v["created_at"][:10],
            str(v["ingredient_count"]),
            str(v["substitution_count"]),
            v.get("notes", "")[:50],
        )

    console.print(table)


@app.command()
def clear_cache(
    source: Annotated[
        Optional[Source],
        typer.Option("--source", "-s", help="Source to clear cache for")
    ] = None,
) -> None:
    """Clear the HTTP response cache."""
    cache_dir = settings.scraper_cache_dir

    if source and source != Source.all:
        source_dir = cache_dir / source.value
        if source_dir.exists():
            import shutil
            shutil.rmtree(source_dir)
            console.print(f"[green]Cleared cache for {source.value}[/green]")
        else:
            console.print(f"[yellow]No cache found for {source.value}[/yellow]")
    else:
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            console.print("[green]Cleared all caches[/green]")
        else:
            console.print("[yellow]No cache found[/yellow]")


if __name__ == "__main__":
    app()
