"""CLI entry point for the evaluation suite."""

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from src.config import EvalConfig, load_config, set_config
from src.reporters import ConsoleReporter, HTMLReporter, JSONReporter
from src.runner import EvalRunner

console = Console()


@click.group()
@click.option("--env-file", "-e", default=None, help="Path to .env file")
@click.option("--config", "-c", default=None, help="Path to YAML config file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, env_file: str | None, config: str | None, verbose: bool) -> None:
    """Palateful AI/OCR Evaluation Suite.

    Run evaluations against AI and OCR features using configurable test datasets.
    """
    ctx.ensure_object(dict)

    # Load and store config
    eval_config = load_config(env_file=env_file, config_file=config)
    eval_config.verbose = verbose or eval_config.verbose
    set_config(eval_config)
    ctx.obj["config"] = eval_config


@cli.command()
@click.option("--suite", "-s", multiple=True, help="Evaluation suites to run (ocr, recipe_extraction, ingredient_matching)")
@click.option("--tags", "-t", multiple=True, help="Only run cases with these tags")
@click.option("--skip-tags", multiple=True, help="Skip cases with these tags")
@click.option("--compare", help="Compare results with a previous run (JSON file path)")
@click.option("--output", "-o", help="Output file for results")
@click.pass_context
def run(
    ctx: click.Context,
    suite: tuple[str, ...],
    tags: tuple[str, ...],
    skip_tags: tuple[str, ...],
    compare: str | None,
    output: str | None,
) -> None:
    """Run evaluation suites."""
    config: EvalConfig = ctx.obj["config"]

    # Apply tag filters
    if tags:
        config.only_tags = list(tags)
    if skip_tags:
        config.skip_tags = list(skip_tags)

    # Determine which suites to run
    available_suites = ["ocr", "recipe_extraction", "ingredient_matching"]
    suites_to_run = list(suite) if suite else available_suites

    invalid_suites = set(suites_to_run) - set(available_suites)
    if invalid_suites:
        console.print(f"[red]Error: Unknown suites: {invalid_suites}[/red]")
        console.print(f"Available suites: {available_suites}")
        sys.exit(1)

    # Run evaluations
    runner = EvalRunner(config)
    console.print("\n[bold blue]Palateful AI/OCR Evaluation Suite[/bold blue]")
    console.print(f"Running suites: {', '.join(suites_to_run)}\n")

    results = runner.run(suites_to_run)

    # Report results
    console_reporter = ConsoleReporter()
    console_reporter.report(results)

    # Compare with baseline if provided
    if compare:
        compare_path = Path(compare)
        if compare_path.exists():
            console.print(f"\n[bold]Comparing with baseline: {compare}[/bold]")
            runner.compare_results(results, compare_path)
        else:
            console.print(f"[yellow]Warning: Comparison file not found: {compare}[/yellow]")

    # Save results
    output_path = Path(output) if output else config.output_dir / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_reporter = JSONReporter()
    json_reporter.save(results, output_path)
    console.print(f"\n[green]Results saved to: {output_path}[/green]")

    # Exit with error code if any suite failed thresholds
    if any(not r.passed_threshold for r in results.suite_results.values()):
        sys.exit(1)


@cli.command()
@click.option("--format", "-f", type=click.Choice(["html", "json", "console"]), default="html", help="Report format")
@click.option("--input", "-i", "input_file", help="Input results file (JSON)")
@click.option("--output", "-o", help="Output file path")
@click.option("--open", "open_browser", is_flag=True, help="Open HTML report in browser")
@click.pass_context
def report(
    ctx: click.Context,
    format: str,
    input_file: str | None,
    output: str | None,
    open_browser: bool,
) -> None:
    """Generate evaluation reports from saved results."""
    config: EvalConfig = ctx.obj["config"]

    # Find the most recent results file if not specified
    if not input_file:
        results_dir = config.output_dir
        json_files = sorted(results_dir.glob("eval_*.json"), reverse=True)
        if not json_files:
            console.print("[red]Error: No results files found. Run evaluations first.[/red]")
            sys.exit(1)
        input_file = str(json_files[0])

    console.print(f"Loading results from: {input_file}")

    # Load results
    json_reporter = JSONReporter()
    results = json_reporter.load(Path(input_file))

    if format == "html":
        html_reporter = HTMLReporter()
        output_path = Path(output) if output else config.output_dir / "report.html"
        html_reporter.save(results, output_path)
        console.print(f"[green]HTML report saved to: {output_path}[/green]")

        if open_browser:
            import webbrowser
            webbrowser.open(f"file://{output_path.absolute()}")

    elif format == "json":
        if output:
            json_reporter.save(results, Path(output))
            console.print(f"[green]JSON results saved to: {output}[/green]")
        else:
            import json
            console.print(json.dumps(results.to_dict(), indent=2))

    else:  # console
        console_reporter = ConsoleReporter()
        console_reporter.report(results)


@cli.command("add-case")
@click.option("--suite", "-s", type=click.Choice(["ocr", "recipe_extraction", "ingredient_matching"]), required=True, help="Suite to add case to")
@click.option("--id", "case_id", help="Case ID (auto-generated if not provided)")
@click.option("--input", "-i", "input_path", required=True, help="Path to input file (image/HTML)")
@click.option("--expected", "-x", help="Path to expected output file")
@click.option("--tags", "-t", multiple=True, help="Tags for the case")
@click.pass_context
def add_case(
    ctx: click.Context,
    suite: str,
    case_id: str | None,
    input_path: str,
    expected: str | None,
    tags: tuple[str, ...],
) -> None:
    """Add a new test case to a suite."""
    import shutil

    import yaml

    config: EvalConfig = ctx.obj["config"]

    input_file = Path(input_path)
    if not input_file.exists():
        console.print(f"[red]Error: Input file not found: {input_path}[/red]")
        sys.exit(1)

    # Generate case ID if not provided
    if not case_id:
        case_id = input_file.stem

    # Determine suite paths
    suite_dir = config.dataset_dir / suite
    manifest_path = suite_dir / "manifest.yaml"

    if suite == "ocr":
        input_dest = suite_dir / "images" / input_file.name
        expected_dest = suite_dir / "expected" / f"{case_id}.md" if expected else None
    elif suite == "recipe_extraction":
        input_dest = suite_dir / "html" / input_file.name
        expected_dest = suite_dir / "expected" / f"{case_id}.json" if expected else None
    else:  # ingredient_matching
        console.print("[yellow]For ingredient_matching, edit cases.yaml directly[/yellow]")
        sys.exit(0)

    # Copy input file
    input_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(input_file, input_dest)
    console.print(f"[green]Copied input to: {input_dest}[/green]")

    # Copy expected file if provided
    if expected and expected_dest:
        expected_file = Path(expected)
        if expected_file.exists():
            expected_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(expected_file, expected_dest)
            console.print(f"[green]Copied expected to: {expected_dest}[/green]")

    # Update manifest
    manifest: dict = {"cases": [], "config": {"timeout_seconds": 60, "skip_tags": []}}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or manifest

    # Add new case
    new_case = {
        "id": case_id,
        "image" if suite == "ocr" else "html": str(input_dest.relative_to(suite_dir)),
        "tags": list(tags) if tags else [],
    }
    if expected_dest:
        new_case["expected"] = str(expected_dest.relative_to(suite_dir))

    # Check for duplicate
    existing_ids = {c["id"] for c in manifest.get("cases", [])}
    if case_id in existing_ids:
        console.print(f"[yellow]Warning: Case {case_id} already exists, updating...[/yellow]")
        manifest["cases"] = [c for c in manifest["cases"] if c["id"] != case_id]

    manifest["cases"].append(new_case)

    # Save manifest
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]Added case '{case_id}' to {manifest_path}[/green]")


if __name__ == "__main__":
    cli()
