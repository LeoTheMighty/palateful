"""HTML reporter for evaluation results."""

from pathlib import Path

from jinja2 import Template

from src.runner import EvalResults

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Palateful Evaluation Report</title>
    <style>
        :root {
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --text-color: #eee;
            --text-muted: #888;
            --success: #00d26a;
            --error: #ff6b6b;
            --warning: #feca57;
            --primary: #4a90d9;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            margin-bottom: 3rem;
        }
        header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        header .timestamp {
            color: var(--text-muted);
        }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        .card h3 {
            font-size: 0.875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        .card .value {
            font-size: 2rem;
            font-weight: bold;
        }
        .card .value.success { color: var(--success); }
        .card .value.error { color: var(--error); }
        .card .value.warning { color: var(--warning); }
        .suite {
            background: var(--card-bg);
            border-radius: 8px;
            margin-bottom: 2rem;
            overflow: hidden;
        }
        .suite-header {
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .suite-header h2 {
            font-size: 1.25rem;
        }
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.875rem;
            font-weight: bold;
        }
        .status-badge.passed {
            background: var(--success);
            color: #000;
        }
        .status-badge.failed {
            background: var(--error);
            color: #fff;
        }
        .suite-content {
            padding: 1.5rem;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .metric {
            text-align: center;
        }
        .metric .label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }
        .metric .value {
            font-size: 1.5rem;
            font-weight: bold;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            color: var(--text-muted);
            font-weight: normal;
            text-transform: uppercase;
            font-size: 0.75rem;
        }
        tr.passed td:first-child { border-left: 3px solid var(--success); }
        tr.failed td:first-child { border-left: 3px solid var(--error); }
        tr.skipped td:first-child { border-left: 3px solid var(--warning); }
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-bar .fill {
            height: 100%;
            background: var(--primary);
            transition: width 0.3s ease;
        }
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Palateful Evaluation Report</h1>
            <p class="timestamp">Generated: {{ timestamp }}</p>
        </header>

        <div class="summary-cards">
            <div class="card">
                <h3>Total Duration</h3>
                <div class="value">{{ "%.2f"|format(total_duration) }}s</div>
            </div>
            <div class="card">
                <h3>Suites Run</h3>
                <div class="value">{{ suites|length }}</div>
            </div>
            <div class="card">
                <h3>Total Cases</h3>
                <div class="value">{{ total_cases }}</div>
            </div>
            <div class="card">
                <h3>Pass Rate</h3>
                <div class="value {% if pass_rate >= 0.9 %}success{% elif pass_rate >= 0.7 %}warning{% else %}error{% endif %}">
                    {{ "%.1f"|format(pass_rate * 100) }}%
                </div>
            </div>
        </div>

        {% for suite in suites %}
        <div class="suite">
            <div class="suite-header">
                <h2>{{ suite.name }}</h2>
                <span class="status-badge {% if suite.passed %}passed{% else %}failed{% endif %}">
                    {% if suite.passed %}PASSED{% else %}FAILED{% endif %}
                </span>
            </div>
            <div class="suite-content">
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="value">{{ suite.total_cases }}</div>
                        <div class="label">Total Cases</div>
                    </div>
                    <div class="metric">
                        <div class="value" style="color: var(--success)">{{ suite.passed_cases }}</div>
                        <div class="label">Passed</div>
                    </div>
                    <div class="metric">
                        <div class="value" style="color: var(--error)">{{ suite.failed_cases }}</div>
                        <div class="label">Failed</div>
                    </div>
                    <div class="metric">
                        <div class="value">{{ "%.2f"|format(suite.duration) }}s</div>
                        <div class="label">Duration</div>
                    </div>
                    {% for metric_name, metric_value in suite.key_metrics.items() %}
                    <div class="metric">
                        <div class="value">{{ "%.2f"|format(metric_value * 100) }}%</div>
                        <div class="label">{{ metric_name }}</div>
                    </div>
                    {% endfor %}
                </div>

                {% if suite.results %}
                <h3 style="margin-bottom: 1rem; font-size: 1rem;">Case Results</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Case ID</th>
                            <th>Status</th>
                            <th>Duration</th>
                            <th>Key Metrics</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for result in suite.results %}
                        <tr class="{% if result.skipped %}skipped{% elif result.passed %}passed{% else %}failed{% endif %}">
                            <td>{{ result.case_id }}</td>
                            <td>
                                {% if result.skipped %}Skipped
                                {% elif result.passed %}Passed
                                {% else %}Failed{% endif %}
                            </td>
                            <td>{{ "%.0f"|format(result.duration_ms) }}ms</td>
                            <td>
                                {% for key, value in result.metrics.items() %}
                                {% if value is number and value <= 1 %}
                                {{ key }}: {{ "%.2f"|format(value * 100) }}%
                                {% endif %}
                                {% endfor %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% endif %}
            </div>
        </div>
        {% endfor %}

        <footer>
            <p>Palateful AI/OCR Evaluation Suite</p>
        </footer>
    </div>
</body>
</html>
"""


class HTMLReporter:
    """Reports evaluation results as an HTML dashboard."""

    def __init__(self):
        self.template = Template(HTML_TEMPLATE)

    def save(self, results: EvalResults, output_path: Path) -> None:
        """Save evaluation results to an HTML file.

        Args:
            results: Evaluation results to save.
            output_path: Path to output HTML file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self.render(results)
        with open(output_path, "w") as f:
            f.write(html_content)

    def render(self, results: EvalResults) -> str:
        """Render evaluation results to HTML string.

        Args:
            results: Evaluation results to render.

        Returns:
            HTML string.
        """
        # Prepare suite data
        suites = []
        total_cases = 0
        total_passed = 0

        for name, suite in results.suite_results.items():
            total_cases += suite.total_cases
            total_passed += suite.passed_cases

            # Extract key metrics
            key_metrics = {}
            for key, value in suite.metrics_summary.items():
                if key.endswith("_avg") and ("accuracy" in key or "rate" in key):
                    display_name = key.replace("_avg", "").replace("_", " ").title()
                    key_metrics[display_name] = value

            suites.append({
                "name": name,
                "passed": suite.passed_threshold,
                "total_cases": suite.total_cases,
                "passed_cases": suite.passed_cases,
                "failed_cases": suite.failed_cases,
                "skipped_cases": suite.skipped_cases,
                "duration": suite.duration_seconds,
                "key_metrics": key_metrics,
                "results": [
                    {
                        "case_id": r.case_id,
                        "passed": r.passed,
                        "skipped": r.skipped,
                        "duration_ms": r.duration_ms,
                        "metrics": r.metrics,
                    }
                    for r in suite.results
                ],
            })

        pass_rate = total_passed / total_cases if total_cases > 0 else 1.0

        return self.template.render(
            timestamp=results.timestamp,
            total_duration=results.total_duration_seconds,
            suites=suites,
            total_cases=total_cases,
            pass_rate=pass_rate,
        )
