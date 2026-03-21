"""Results output for eval runs — CSV export and summary statistics."""

import csv
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class TrialRecord:
    """Record for a single trial in an eval run."""

    case_id: str
    trial_number: int
    query_type: str
    passed: bool
    reasoning: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0
    error: str | None = None


@dataclass
class CaseSummary:
    """Summary statistics for a single eval case across all trials."""

    case_id: str
    query_type: str
    total_trials: int = 0
    passed_trials: int = 0
    pass_rate: float = 0.0
    avg_duration_ms: float = 0.0
    avg_tokens: float = 0.0
    trials: list[TrialRecord] = field(default_factory=list)

    def compute(self) -> None:
        """Compute summary statistics from trial records."""
        if not self.trials:
            return
        self.total_trials = len(self.trials)
        self.passed_trials = sum(1 for t in self.trials if t.passed)
        self.pass_rate = self.passed_trials / self.total_trials if self.total_trials > 0 else 0.0

        durations = [t.duration_ms for t in self.trials if t.duration_ms > 0]
        self.avg_duration_ms = statistics.mean(durations) if durations else 0.0

        tokens = [t.tokens_used for t in self.trials if t.tokens_used > 0]
        self.avg_tokens = statistics.mean(tokens) if tokens else 0.0


@dataclass
class EvalRunSummary:
    """Overall summary for an eval run."""

    suite_name: str
    cases: list[CaseSummary] = field(default_factory=list)
    overall_pass_rate: float = 0.0
    total_trials: int = 0
    passed_trials: int = 0
    avg_duration_ms: float = 0.0
    avg_tokens: float = 0.0

    def compute(self) -> None:
        """Compute overall summary from case summaries."""
        for case in self.cases:
            case.compute()

        self.total_trials = sum(c.total_trials for c in self.cases)
        self.passed_trials = sum(c.passed_trials for c in self.cases)
        self.overall_pass_rate = self.passed_trials / self.total_trials if self.total_trials > 0 else 0.0

        all_durations = [t.duration_ms for c in self.cases for t in c.trials if t.duration_ms > 0]
        self.avg_duration_ms = statistics.mean(all_durations) if all_durations else 0.0

        all_tokens = [t.tokens_used for c in self.cases for t in c.trials if t.tokens_used > 0]
        self.avg_tokens = statistics.mean(all_tokens) if all_tokens else 0.0


def write_csv(summary: EvalRunSummary, output_path: Path) -> None:
    """Write trial-level results to CSV.

    Args:
        summary: The eval run summary with all trial records.
        output_path: Path to write the CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id",
            "trial",
            "query_type",
            "passed",
            "duration_ms",
            "tokens_used",
            "reasoning",
            "error",
        ])

        for case in summary.cases:
            for trial in case.trials:
                writer.writerow([
                    trial.case_id,
                    trial.trial_number,
                    trial.query_type,
                    trial.passed,
                    f"{trial.duration_ms:.1f}",
                    trial.tokens_used,
                    trial.reasoning[:200],
                    trial.error or "",
                ])


def print_summary(summary: EvalRunSummary, detail: bool = False) -> None:
    """Print a rich summary table to the console.

    Args:
        summary: The eval run summary.
        detail: If True, show per-case breakdown.
    """
    console.print(f"\n[bold blue]{summary.suite_name} — Eval Summary[/bold blue]")
    console.print(f"Overall pass rate: [{'green' if summary.overall_pass_rate >= 0.8 else 'red'}]"
                  f"{summary.overall_pass_rate:.1%}[/] "
                  f"({summary.passed_trials}/{summary.total_trials} trials)")
    console.print(f"Avg latency: {summary.avg_duration_ms:.0f}ms | Avg tokens: {summary.avg_tokens:.0f}")

    if detail and summary.cases:
        table = Table(title="Per-Case Results")
        table.add_column("Case ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Pass Rate", justify="right")
        table.add_column("Trials", justify="right")
        table.add_column("Avg Latency", justify="right")
        table.add_column("Avg Tokens", justify="right")

        for case in summary.cases:
            rate_color = "green" if case.pass_rate >= 0.8 else "yellow" if case.pass_rate >= 0.5 else "red"
            table.add_row(
                case.case_id,
                case.query_type,
                f"[{rate_color}]{case.pass_rate:.0%}[/{rate_color}]",
                f"{case.passed_trials}/{case.total_trials}",
                f"{case.avg_duration_ms:.0f}ms",
                f"{case.avg_tokens:.0f}",
            )

        console.print(table)
