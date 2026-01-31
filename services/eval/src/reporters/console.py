"""Console reporter for evaluation results."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.runner import EvalResults, SuiteResult


class ConsoleReporter:
    """Reports evaluation results to the console."""

    def __init__(self):
        self.console = Console()

    def report(self, results: EvalResults) -> None:
        """Print evaluation results to the console.

        Args:
            results: Evaluation results to report.
        """
        self.console.print()
        self._print_header(results)

        for suite_name, suite_result in results.suite_results.items():
            self._print_suite_summary(suite_result)

        self._print_footer(results)

    def _print_header(self, results: EvalResults) -> None:
        """Print report header."""
        self.console.print(Panel.fit(
            f"[bold]Evaluation Results[/bold]\n"
            f"Timestamp: {results.timestamp}\n"
            f"Total Duration: {results.total_duration_seconds:.2f}s",
            title="Palateful AI/OCR Evaluation",
            border_style="blue",
        ))

    def _print_suite_summary(self, suite: SuiteResult) -> None:
        """Print summary for a single suite."""
        # Status indicator
        if suite.passed_threshold:
            status = "[green]PASSED[/green]"
            border_style = "green"
        else:
            status = "[red]FAILED[/red]"
            border_style = "red"

        # Create summary table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Status", status)
        table.add_row("Total Cases", str(suite.total_cases))
        table.add_row("Passed", f"[green]{suite.passed_cases}[/green]")
        table.add_row("Failed", f"[red]{suite.failed_cases}[/red]" if suite.failed_cases > 0 else "0")
        table.add_row("Skipped", str(suite.skipped_cases))
        table.add_row("Duration", f"{suite.duration_seconds:.2f}s")

        self.console.print(Panel(
            table,
            title=f"[bold]{suite.suite_name}[/bold]",
            border_style=border_style,
        ))

        # Print metrics summary
        if suite.metrics_summary:
            self._print_metrics_table(suite.metrics_summary)

        # Print failed cases
        failed_results = [r for r in suite.results if not r.passed and not r.skipped]
        if failed_results:
            self._print_failed_cases(failed_results)

    def _print_metrics_table(self, metrics: dict) -> None:
        """Print metrics summary table."""
        table = Table(show_header=True, header_style="bold dim")
        table.add_column("Metric", style="cyan")
        table.add_column("Avg", justify="right")
        table.add_column("Min", justify="right")
        table.add_column("Max", justify="right")

        # Group metrics by base name
        metric_names = set()
        for key in metrics:
            if key.endswith("_avg"):
                metric_names.add(key[:-4])

        for name in sorted(metric_names):
            avg = metrics.get(f"{name}_avg", 0)
            min_val = metrics.get(f"{name}_min", 0)
            max_val = metrics.get(f"{name}_max", 0)

            # Color based on value (assuming higher is better for accuracy metrics)
            if "accuracy" in name or "rate" in name:
                color = "green" if avg >= 0.9 else "yellow" if avg >= 0.7 else "red"
            else:
                color = "white"

            table.add_row(
                name,
                f"[{color}]{avg:.4f}[/{color}]",
                f"{min_val:.4f}",
                f"{max_val:.4f}",
            )

        self.console.print(table)

    def _print_failed_cases(self, failed: list) -> None:
        """Print details of failed cases."""
        self.console.print("\n[bold red]Failed Cases:[/bold red]")

        for result in failed[:5]:  # Show first 5 failures
            error_text = result.error or "Threshold not met"
            self.console.print(f"  - {result.case_id}: {error_text}")

            # Show key metrics
            if result.metrics:
                for key, value in list(result.metrics.items())[:3]:
                    if isinstance(value, float):
                        self.console.print(f"      {key}: {value:.4f}")

        if len(failed) > 5:
            self.console.print(f"  ... and {len(failed) - 5} more")

    def _print_footer(self, results: EvalResults) -> None:
        """Print report footer."""
        all_passed = all(s.passed_threshold for s in results.suite_results.values())

        if all_passed:
            self.console.print("\n[bold green]All evaluation suites PASSED[/bold green]")
        else:
            failed_suites = [name for name, s in results.suite_results.items() if not s.passed_threshold]
            self.console.print(f"\n[bold red]FAILED suites: {', '.join(failed_suites)}[/bold red]")

        # Cost summary if any
        total_cost = sum(
            sum(r.cost_cents for r in suite.results)
            for suite in results.suite_results.values()
        )
        if total_cost > 0:
            self.console.print(f"\n[dim]Total AI cost: ${total_cost / 100:.2f}[/dim]")
