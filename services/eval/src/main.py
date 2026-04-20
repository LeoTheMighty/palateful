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

ALL_SUITES = ["ocr", "recipe_extraction", "recipe_parse", "chat_agent"]


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
@click.option("--suite", "-s", multiple=True, help=f"Evaluation suites to run ({', '.join(ALL_SUITES)})")
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
    suites_to_run = list(suite) if suite else ALL_SUITES

    invalid_suites = set(suites_to_run) - set(ALL_SUITES)
    if invalid_suites:
        console.print(f"[red]Error: Unknown suites: {invalid_suites}[/red]")
        console.print(f"Available suites: {ALL_SUITES}")
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


@cli.command("eval-llm")
@click.option("--cases", multiple=True, help="Which eval case suites to run (recipe_parse, chat_agent)")
@click.option("--model", default=None, help="Override LLM model for the system under test")
@click.option("--repeats", default=1, type=int, help="Number of trials per question")
@click.option("--fail-under", default=0.0, type=float, help="Minimum pass rate (0.0-1.0) for CI")
@click.option("--detail", is_flag=True, help="Show per-question results")
@click.option("--concurrency", default=4, type=int, help="Max concurrent trials")
@click.option("--output", "-o", default=None, help="Output CSV file path")
@click.pass_context
def eval_llm(
    ctx: click.Context,
    cases: tuple[str, ...],
    model: str | None,
    repeats: int,
    fail_under: float,
    detail: bool,
    concurrency: int,
    output: str | None,
) -> None:
    """Run LLM-as-judge evaluation for recipe parsing and chat agent.

    Loads QA pairs from datasets/, runs production code with mocked deps,
    judges results with LLM, prints summary with pass rate.

    Examples:

        npx nx run eval:eval-llm -- --cases recipe_parse --repeats 3

        npx nx run eval:eval-llm -- --cases chat_agent --detail --fail-under 0.8
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from src.results import CaseSummary, EvalRunSummary, TrialRecord, print_summary, write_csv

    config: EvalConfig = ctx.obj["config"]
    config.repeats = repeats
    config.concurrency = concurrency
    config.fail_under = fail_under

    # Determine which case suites to run
    available = ["recipe_parse", "chat_agent"]
    suites_to_run = list(cases) if cases else available

    invalid = set(suites_to_run) - set(available)
    if invalid:
        console.print(f"[red]Error: Unknown case suites: {invalid}[/red]")
        console.print(f"Available: {available}")
        sys.exit(1)

    console.print("\n[bold blue]Palateful LLM Eval Suite[/bold blue]")
    console.print(f"Suites: {', '.join(suites_to_run)} | Repeats: {repeats} | Concurrency: {concurrency}")
    if model:
        console.print(f"Model override: {model}")
    console.print()

    all_summaries: list[EvalRunSummary] = []

    for suite_name in suites_to_run:
        runner = EvalRunner(config)
        evaluator = runner._get_evaluator(suite_name)
        eval_cases = evaluator.load_cases()

        if not eval_cases:
            console.print(f"[yellow]No cases found for suite: {suite_name}[/yellow]")
            continue

        run_summary = EvalRunSummary(suite_name=suite_name)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {suite_name}...", total=len(eval_cases) * repeats)

            def run_single_trial(case, trial_num):
                """Run a single trial for a case."""
                result = evaluator.evaluate(case)
                progress.advance(task)
                return case.id, trial_num, result

            # Run trials with concurrency
            case_summaries: dict[str, CaseSummary] = {}
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = []
                for case in eval_cases:
                    query_type = case.metadata.get("query_type", "unknown")
                    case_summaries[case.id] = CaseSummary(
                        case_id=case.id,
                        query_type=query_type,
                    )
                    for trial_num in range(1, repeats + 1):
                        futures.append(executor.submit(run_single_trial, case, trial_num))

                for future in as_completed(futures):
                    try:
                        case_id, trial_num, result = future.result()
                        cs = case_summaries[case_id]
                        cs.trials.append(TrialRecord(
                            case_id=case_id,
                            trial_number=trial_num,
                            query_type=cs.query_type,
                            passed=result.passed,
                            reasoning=result.metrics.get("judge_reasoning", ""),
                            duration_ms=result.duration_ms,
                            tokens_used=result.metrics.get("tokens_used", 0),
                            error=result.error,
                        ))
                    except Exception as e:
                        console.print(f"[red]Trial error: {e}[/red]")

        run_summary.cases = list(case_summaries.values())
        run_summary.compute()
        all_summaries.append(run_summary)

        print_summary(run_summary, detail=detail)

        # Write CSV if requested
        if output:
            csv_path = Path(output)
        else:
            csv_path = config.output_dir / f"{suite_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        write_csv(run_summary, csv_path)
        console.print(f"[green]CSV results saved to: {csv_path}[/green]")

    # Check fail-under threshold
    if fail_under > 0:
        for summary in all_summaries:
            if summary.overall_pass_rate < fail_under:
                console.print(
                    f"\n[red]FAIL: {summary.suite_name} pass rate {summary.overall_pass_rate:.1%} "
                    f"< threshold {fail_under:.1%}[/red]"
                )
                sys.exit(1)

    console.print("\n[green]All evals completed.[/green]")


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
@click.option("--suite", "-s", type=click.Choice(["ocr", "recipe_extraction"]), required=True, help="Suite to add case to")
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
    else:  # recipe_extraction
        input_dest = suite_dir / "html" / input_file.name
        expected_dest = suite_dir / "expected" / f"{case_id}.json" if expected else None

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


@cli.command("run-fixtures")
@click.option("--strategy", "-s", default="text_extractor", help="Extraction strategy to use")
@click.option(
    "--fixtures-dir", "-d", default=None,
    help="Path to fixtures directory (defaults to ./fixtures)",
)
@click.option("--compare", "-c", default=None, help="Comma-separated strategies to compare")
@click.option("--output", "-o", default=None, help="Output JSON file for results")
@click.pass_context
def run_fixtures(
    ctx: click.Context,
    strategy: str,
    fixtures_dir: str | None,
    compare: str | None,
    output: str | None,
) -> None:
    """Run fixture-based extraction eval.

    Discovers input/expected pairs in the fixtures directory and scores
    extraction results against ground truth.

    Examples:

        npx nx run eval:run-fixtures

        npx nx run eval:run-fixtures -- --strategy text_extractor

        npx nx run eval:run-fixtures -- --compare text_extractor,ocr_then_text
    """
    import json as json_mod

    from src.fixture_runner import run_comparison, run_eval
    from src.strategies import STRATEGIES

    # Determine fixtures directory
    if fixtures_dir:
        fdir = Path(fixtures_dir)
    else:
        fdir = Path("./fixtures")

    if not fdir.is_dir():
        console.print(f"[red]Error: Fixtures directory not found: {fdir}[/red]")
        sys.exit(1)

    if compare:
        # Compare mode: run multiple strategies
        strategy_list = [s.strip() for s in compare.split(",")]
        invalid = [s for s in strategy_list if s not in STRATEGIES]
        if invalid:
            console.print(f"[red]Unknown strategies: {invalid}[/red]")
            console.print(f"Available: {list(STRATEGIES.keys())}")
            sys.exit(1)

        results = run_comparison(str(fdir), strategy_list)
    else:
        # Single strategy mode
        if strategy not in STRATEGIES:
            console.print(f"[red]Unknown strategy: {strategy}[/red]")
            console.print(f"Available: {list(STRATEGIES.keys())}")
            sys.exit(1)

        results = run_eval(str(fdir), strategy=strategy)

    # Save results if output specified
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json_mod.dump(results, f, indent=2, default=str)
        console.print(f"\n[green]Results saved to: {output_path}[/green]")


if __name__ == "__main__":
    cli()
