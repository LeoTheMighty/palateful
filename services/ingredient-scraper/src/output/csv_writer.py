"""CSV output writer with versioning support.

Generates versioned CSV files that map directly to the database schema.
Supports incremental updates by loading existing versions and merging.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from ..models import (
    ScrapedIngredient,
    Substitution,
    INGREDIENT_CSV_COLUMNS,
    SUBSTITUTION_CSV_COLUMNS,
)

console = Console()


class CSVWriter:
    """Writes ingredients and substitutions to versioned CSV files.

    File naming convention:
    - ingredients_v{version}.csv
    - substitutions_v{version}.csv
    - manifest.json (tracks versions and metadata)
    """

    def __init__(self, output_dir: Path):
        """Initialize CSV writer.

        Args:
            output_dir: Directory to write CSV files to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "manifest.json"

    def get_manifest(self) -> dict[str, Any]:
        """Load or create the manifest file.

        Returns:
            Manifest dict with version history
        """
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                return json.load(f)

        return {
            "created_at": datetime.now().isoformat(),
            "versions": [],
            "latest_version": None,
        }

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        """Save the manifest file.

        Args:
            manifest: Manifest dict to save
        """
        manifest["updated_at"] = datetime.now().isoformat()
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    def get_next_version(self) -> str:
        """Get the next version number.

        Returns:
            Version string (e.g., "1.0.0")
        """
        manifest = self.get_manifest()
        versions = manifest.get("versions", [])

        if not versions:
            return "1.0.0"

        # Parse latest version and increment patch
        latest = versions[-1]["version"]
        parts = latest.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)

    def get_latest_version(self) -> str | None:
        """Get the latest version number.

        Returns:
            Latest version string or None if no versions exist
        """
        manifest = self.get_manifest()
        return manifest.get("latest_version")

    def load_version(
        self, version: str
    ) -> tuple[list[ScrapedIngredient], list[Substitution]]:
        """Load ingredients and substitutions from a specific version.

        Args:
            version: Version string to load

        Returns:
            Tuple of (ingredients, substitutions)
        """
        ing_path = self.output_dir / f"ingredients_v{version}.csv"
        sub_path = self.output_dir / f"substitutions_v{version}.csv"

        ingredients = []
        substitutions = []

        if ing_path.exists():
            with open(ing_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ingredients.append(ScrapedIngredient.from_csv_row(row))

        if sub_path.exists():
            with open(sub_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    substitutions.append(Substitution.from_csv_row(row))

        return ingredients, substitutions

    def load_latest(self) -> tuple[list[ScrapedIngredient], list[Substitution]]:
        """Load the latest version of ingredients and substitutions.

        Returns:
            Tuple of (ingredients, substitutions)
        """
        version = self.get_latest_version()
        if not version:
            return [], []
        return self.load_version(version)

    def write(
        self,
        ingredients: list[ScrapedIngredient],
        substitutions: list[Substitution] | None = None,
        version: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Write ingredients and substitutions to CSV files.

        Args:
            ingredients: List of ingredients to write
            substitutions: List of substitutions to write
            version: Version string (auto-generated if not provided)
            notes: Optional notes about this version

        Returns:
            The version string used
        """
        version = version or self.get_next_version()
        substitutions = substitutions or []

        console.print(f"[bold blue]Writing version {version}...[/bold blue]")

        # Write ingredients CSV
        ing_path = self.output_dir / f"ingredients_v{version}.csv"
        self._write_ingredients_csv(ing_path, ingredients)
        console.print(f"[green]  Wrote {len(ingredients)} ingredients to {ing_path.name}[/green]")

        # Write substitutions CSV
        if substitutions:
            sub_path = self.output_dir / f"substitutions_v{version}.csv"
            self._write_substitutions_csv(sub_path, substitutions)
            console.print(f"[green]  Wrote {len(substitutions)} substitutions to {sub_path.name}[/green]")

        # Update manifest
        manifest = self.get_manifest()
        version_info = {
            "version": version,
            "created_at": datetime.now().isoformat(),
            "ingredient_count": len(ingredients),
            "substitution_count": len(substitutions),
            "notes": notes,
        }
        manifest["versions"].append(version_info)
        manifest["latest_version"] = version
        self.save_manifest(manifest)

        return version

    def _write_ingredients_csv(
        self, path: Path, ingredients: list[ScrapedIngredient]
    ) -> None:
        """Write ingredients to a CSV file.

        Args:
            path: Path to write to
            ingredients: List of ingredients
        """
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INGREDIENT_CSV_COLUMNS)
            writer.writeheader()

            for ing in ingredients:
                writer.writerow(ing.to_csv_row())

    def _write_substitutions_csv(
        self, path: Path, substitutions: list[Substitution]
    ) -> None:
        """Write substitutions to a CSV file.

        Args:
            path: Path to write to
            substitutions: List of substitutions
        """
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SUBSTITUTION_CSV_COLUMNS)
            writer.writeheader()

            for sub in substitutions:
                writer.writerow(sub.to_csv_row())

    def merge_with_existing(
        self,
        new_ingredients: list[ScrapedIngredient],
        new_substitutions: list[Substitution] | None = None,
    ) -> tuple[list[ScrapedIngredient], list[Substitution]]:
        """Merge new ingredients with the latest version.

        New ingredients are added if they don't exist.
        Existing ingredients are updated if the new version has more data.

        Args:
            new_ingredients: New ingredients to merge
            new_substitutions: New substitutions to merge

        Returns:
            Tuple of (merged_ingredients, merged_substitutions)
        """
        existing_ings, existing_subs = self.load_latest()
        new_substitutions = new_substitutions or []

        console.print(
            f"[dim]Merging {len(new_ingredients)} new ingredients "
            f"with {len(existing_ings)} existing[/dim]"
        )

        # Build a map of existing ingredients by canonical name
        existing_map = {ing.canonical_name: ing for ing in existing_ings}

        # Merge new ingredients
        for new_ing in new_ingredients:
            if new_ing.canonical_name in existing_map:
                # Merge with existing
                existing = existing_map[new_ing.canonical_name]
                merged = existing.merge_with(new_ing)
                existing_map[new_ing.canonical_name] = merged
            else:
                # Add new
                existing_map[new_ing.canonical_name] = new_ing

        merged_ingredients = list(existing_map.values())

        # Merge substitutions (simple dedup by ingredient+substitute pair)
        sub_keys = {(s.ingredient, s.substitute) for s in existing_subs}
        merged_subs = list(existing_subs)

        for new_sub in new_substitutions:
            key = (new_sub.ingredient, new_sub.substitute)
            if key not in sub_keys:
                merged_subs.append(new_sub)
                sub_keys.add(key)

        console.print(
            f"[green]Merged to {len(merged_ingredients)} ingredients "
            f"and {len(merged_subs)} substitutions[/green]"
        )

        return merged_ingredients, merged_subs

    def list_versions(self) -> list[dict[str, Any]]:
        """List all available versions.

        Returns:
            List of version info dicts
        """
        manifest = self.get_manifest()
        return manifest.get("versions", [])


# Alias for backwards compatibility
JSONSeedWriter = CSVWriter
