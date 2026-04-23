"""Synthetic load test for `POST /v1/client-latencies` (cla-14).

Spawns N concurrent async "fake clients" that each post batches of
client-latency events for M minutes, and reports latency + success-rate
statistics at the end.

Default profile matches the epic's AC (50 concurrent × 100 events/batch
× 5 minutes), which models the expected steady-state fleet — 50 active
users × ~500 events/day × ~5 sessions/day ≈ 125k events/day overall,
or ~1.5 events/sec steady, which a 50×100-batch burst dwarfs.

Usage:
    # Stock profile — 50 workers × 100 events × 5 min, localhost API.
    python services/api/scripts/load_test_client_latencies.py \\
        --jwt "$(curl ... get token)"

    # Tighter sanity check — 10 workers × 50 events × 30 s.
    python services/api/scripts/load_test_client_latencies.py \\
        --concurrency 10 --batch-size 50 --duration-s 30 --jwt "$JWT"

    # Anonymous path (watch out for the 10 events/IP/min rate-limit in
    # services/api/src/api/v1/client_latency/ingest.py — this will 429
    # out almost immediately on a single-IP run).
    python services/api/scripts/load_test_client_latencies.py --concurrency 1

Rate-limit note:
    The anonymous ingest path enforces 10 events/IP/rolling-minute.
    50 × 100 batches/min from one IP is ~500× over that, so an
    authenticated JWT is required for the stock profile. Pass one via
    `--jwt`. If you're load-testing a local docker-compose stack, you
    can temporarily bump `_ANON_RATE_LIMIT_MAX_EVENTS` in the ingest
    module to a large number and run without a JWT — faster than
    minting real tokens.

Reports:
    - Per-request latency p50/p95/p99/max.
    - Success rate (2xx / total), non-2xx breakdown by status.
    - Total events posted, events/sec.

Exit codes:
    0 — ran to completion; whether it met the AC threshold (p95<100ms,
        100% success) is printed but not encoded in the exit code so
        CI doesn't gate on it.
    2 — usage / invalid args.
    1 — other runtime error.

Read-only against the DB (only goes through the HTTP endpoint). Writes
~N×B×T rows to `client_latencies` where N=concurrency, B=batch size,
T=time — purge via `services/api/src/jobs/prune_latencies.py` or delete
by `app_version='loadtest-*'` after the run.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import httpx  # type: ignore
except ModuleNotFoundError:  # pragma: no cover — ops script dep hint
    print(
        "httpx is required. Install with `poetry add httpx --group dev` "
        "or `pip install httpx` in the venv you're running this from.",
        file=sys.stderr,
    )
    sys.exit(2)


@dataclass
class WorkerResult:
    worker_id: int
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    exceptions: int = 0


def _make_event(worker_id: int, seq: int, app_version: str) -> dict[str, Any]:
    """Mint one synthetic `network_request`-type event.

    Route strings are pre-redacted (no raw UUIDs) so the server-side
    redaction guard accepts them.
    """
    return {
        "type": "network_request",
        "platform": "ios",
        "app_version": app_version,
        "duration_ms": random.randint(10, 400),
        "route": "/home",
        "endpoint": "/v1/health",
        "metric_name": "GET",
    }


async def _worker(
    worker_id: int,
    url: str,
    jwt: str | None,
    batch_size: int,
    deadline_monotonic: float,
    app_version: str,
) -> WorkerResult:
    result = WorkerResult(worker_id=worker_id)
    headers: dict[str, str] = {"User-Agent": "palateful-loadtest/1.0"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    seq = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        while True:
            now = time.monotonic()
            if now >= deadline_monotonic:
                break
            events = [_make_event(worker_id, seq + i, app_version) for i in range(batch_size)]
            seq += batch_size
            t0 = time.monotonic()
            try:
                resp = await client.post(url, json={"events": events}, headers=headers)
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                result.latencies_ms.append(elapsed_ms)
                result.status_counts[resp.status_code] = (
                    result.status_counts.get(resp.status_code, 0) + 1
                )
            except Exception:
                # Network-level error (timeout, connection reset).
                result.exceptions += 1

    return result


def _percentile(xs: list[float], pct: float) -> float:
    if not xs:
        return 0.0
    sorted_xs = sorted(xs)
    idx = int(round(pct / 100.0 * (len(sorted_xs) - 1)))
    return sorted_xs[idx]


def _print_report(
    results: list[WorkerResult],
    wall_seconds: float,
    batch_size: int,
) -> None:
    all_latencies = [x for r in results for x in r.latencies_ms]
    total_requests = len(all_latencies) + sum(r.exceptions for r in results)
    total_exceptions = sum(r.exceptions for r in results)
    status_totals: dict[int, int] = {}
    for r in results:
        for status, count in r.status_counts.items():
            status_totals[status] = status_totals.get(status, 0) + count

    success_count = sum(
        count for status, count in status_totals.items() if 200 <= status < 300
    )
    success_rate = (success_count / total_requests * 100) if total_requests else 0.0
    events_total = success_count * batch_size
    events_per_sec = events_total / wall_seconds if wall_seconds > 0 else 0.0

    print()
    print("=" * 64)
    print("cla-14 synthetic load-test report")
    print("=" * 64)
    print(f"Wall time:        {wall_seconds:.1f} s")
    print(f"Workers:          {len(results)}")
    print(f"Total requests:   {total_requests}")
    print(f"Successful (2xx): {success_count} ({success_rate:.2f} %)")
    print(f"Exceptions:       {total_exceptions}")
    if status_totals:
        status_line = ", ".join(
            f"{status}: {count}" for status, count in sorted(status_totals.items())
        )
        print(f"Status codes:     {status_line}")
    print(f"Events posted:    {events_total}")
    print(f"Events / sec:     {events_per_sec:,.0f}")
    print()
    if all_latencies:
        print("Per-request latency (ms):")
        print(f"  min:   {min(all_latencies):.1f}")
        print(f"  p50:   {_percentile(all_latencies, 50):.1f}")
        print(f"  mean:  {statistics.mean(all_latencies):.1f}")
        print(f"  p95:   {_percentile(all_latencies, 95):.1f}")
        print(f"  p99:   {_percentile(all_latencies, 99):.1f}")
        print(f"  max:   {max(all_latencies):.1f}")
    else:
        print("No latencies captured — all requests errored.")
    print()
    p95 = _percentile(all_latencies, 95) if all_latencies else float("inf")
    ac_p95 = p95 < 100.0
    ac_success = success_rate >= 100.0 - 1e-9
    print("AC check:")
    print(f"  p95 < 100 ms:          {'PASS' if ac_p95 else 'FAIL'} ({p95:.1f} ms)")
    print(f"  success rate == 100 %: {'PASS' if ac_success else 'FAIL'} ({success_rate:.2f} %)")
    print()
    print(
        "Paste the above numbers into docs/PERFORMANCE_OPS.md under the "
        "cla-14 baseline section. Don't forget to also eyeball "
        "`SELECT * FROM pg_stat_activity WHERE state='active'` during "
        "the run for DB-side contention."
    )


async def _run_load_test(args: argparse.Namespace) -> int:
    print(
        f"Starting load test — {args.concurrency} workers × "
        f"{args.batch_size} events × {args.duration_s}s against {args.url}"
    )
    if not args.jwt:
        print(
            "WARNING: no --jwt provided — the anonymous path is rate-limited "
            "at 10 events/IP/min. Expect 429s unless the server's rate-limit "
            "constant has been loosened for this test."
        )
    deadline = time.monotonic() + args.duration_s
    app_version = f"loadtest-{int(time.time())}"

    t0 = time.monotonic()
    results = await asyncio.gather(
        *(
            _worker(
                worker_id=i,
                url=args.url,
                jwt=args.jwt,
                batch_size=args.batch_size,
                deadline_monotonic=deadline,
                app_version=app_version,
            )
            for i in range(args.concurrency)
        )
    )
    wall = time.monotonic() - t0
    _print_report(results, wall, args.batch_size)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthetic load test for POST /v1/client-latencies (cla-14).",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/v1/client-latencies",
        help="Target URL (default: http://localhost:8000/v1/client-latencies).",
    )
    parser.add_argument(
        "--jwt",
        default=None,
        help=(
            "Bearer token to send with each request. Required in practice "
            "because the anonymous path rate-limits at 10 events/IP/min."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Number of concurrent async workers (default 50).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Events per POST body (default 100; server caps at 100).",
    )
    parser.add_argument(
        "--duration-s",
        type=int,
        default=300,
        help="How long to run, in seconds (default 300 = 5 min).",
    )
    args = parser.parse_args()
    if args.concurrency < 1 or args.batch_size < 1 or args.duration_s < 1:
        print("All of --concurrency, --batch-size, --duration-s must be >= 1.", file=sys.stderr)
        sys.exit(2)
    if args.batch_size > 100:
        print(
            "Batch size clamped at 100 (server-side MAX_EVENTS_PER_REQUEST).",
            file=sys.stderr,
        )
        args.batch_size = 100
    return args


def main() -> None:
    args = _parse_args()
    try:
        rc = asyncio.run(_run_load_test(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(1)
    sys.exit(rc)


if __name__ == "__main__":
    main()
